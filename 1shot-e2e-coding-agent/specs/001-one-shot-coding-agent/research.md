# Research: One-Shot End-to-End Coding Agent

**Date**: 2026-03-13  
**Spec**: [spec.md](spec.md)  
**Plan**: [plan.md](plan.md)

## Research Tasks

### R1: Pi SDK API Stability & Embedding Strategy

**Context**: Pi SDK (`@mariozechner/pi-coding-agent`) is a v0.x solo-maintained project. We're building the entire agent on its `createAgentSession` API.

**Findings**:
- `createAgentSession` accepts: `sessionManager`, `authStorage`, `modelRegistry`, `systemPrompt`, `extensions`, `tools`, `provider`, `model`
- Pi SDK v0.57.1 is the documented version with working examples
- Token usage exposed via `session.tokenUsage?.total`
- Tool scoping per session works via `tools: string[]` and `extensions: string[]` parameters
- No stability guarantee for pre-v1.0 — APIs may change between minor versions

**Decision**: Pin Pi SDK at exact version `0.57.1` in `package.json`. Wrap all Pi SDK calls in adapter functions (`src/adapters/pi-sdk.ts`) to centralize version management. If Pi breaks an API, only one file changes.

**Rationale**: Version pinning + adapter layer is the standard mitigation for pre-v1 dependencies. Direct calls scattered across 9 step files would be a maintenance nightmare if the API changes.

**Alternatives considered**:
1. Use Pi SDK directly without wrappers → Rejected: too many call sites to update on breaking change
2. Fork Pi SDK → Rejected: overkill for v1; keeping up with upstream is cheaper than maintaining a fork
3. Build without Pi SDK (roll our own) → Rejected: Pi gives us 7 built-in tools, 15+ providers, session management for free

---

### R2: Vector Store for Semantic Search

**Context**: The `semantic_search` Pi Extension needs a vector store to index and query code embeddings. Initial requirement suggests chromadb (Python sidecar) or vectra (native TS).

**Findings**:
- **chromadb**: Mature, widely used, but requires Python runtime. Our Docker image already uses `node:20-slim` — adding Python increases image size by ~100MB and adds cross-runtime complexity.
- **vectra** (`vectra`): Pure TypeScript vector store by Microsoft, stores vectors as JSON files. Supports cosine similarity. Simple API: `createIndex()`, `upsertItem()`, `queryItems()`. No external dependencies.
- **`@xenova/transformers`**: Can run embedding models in Node.js via ONNX. Pairs well with vectra for a fully TS solution.
- **Alternative: `hnswlib-node`**: Fast approximate nearest neighbor library for Node.js. More performant than vectra for large codebases but requires native compilation.

**Decision**: Use **vectra** for v1. Pure TypeScript, zero native dependencies, file-based storage (persists to disk in the container). Pair with `@xenova/transformers` for local embeddings using `nomic-embed-text` or `all-MiniLM-L6-v2`.

**Rationale**: Vectra keeps the entire stack in TypeScript with zero native dependencies, making the Docker image simpler and builds reproducible. For codebases of 5K-50K LOC (our target), vectra's performance is more than sufficient — we're indexing hundreds of code chunks, not millions of documents.

**Alternatives considered**:
1. chromadb → Rejected: requires Python sidecar, increases image size, cross-runtime IPC complexity
2. hnswlib-node → Rejected: native compilation needed, build issues on different platforms
3. No vector store (keyword search only) → Rejected: semantic search is a key differentiator for context quality (FR-003)

**Trade-offs**: Vectra is JSON-based and slower than chromadb for large datasets. For v1's target scope (5K-50K LOC), this is acceptable. If we scale beyond 100K LOC, migrating to chromadb or a dedicated vector DB would be warranted.

---

### R3: Tree-sitter WASM Library for Repo Map

**Context**: The `repo_map` extension generates a symbol skeleton of the repository using AST parsing. Needs tree-sitter with WASM bindings for Node.js.

**Findings**:
- **`web-tree-sitter`**: Official WASM binding for tree-sitter. Works in Node.js and browsers. Maintained by the tree-sitter project. Requires loading language grammars (`.wasm` files) at runtime.
- **`tree-sitter`** (native): Node.js native binding. Faster but requires `node-gyp` compilation — fails in some Docker environments and CI.
- **Language grammars**: Available as `.wasm` files per language — `tree-sitter-javascript`, `tree-sitter-python`, `tree-sitter-typescript`, etc. Can be bundled or downloaded at build time.

**Decision**: Use **`web-tree-sitter`** (WASM). Bundle grammar `.wasm` files for the top 5 languages (TypeScript, JavaScript, Python, Go, Java) in the Docker image. Load grammars lazily based on the target repo's language config.

**Rationale**: WASM bindings are portable across platforms and Docker environments with no native compilation needed. The official tree-sitter WASM binding is well-maintained and used by major editors (VS Code, Zed).

**Alternatives considered**:
1. `tree-sitter` (native) → Rejected: `node-gyp` build failures in Docker and CI are common
2. ctags (universal-ctags) → Rejected: less accurate than AST-based parsing; doesn't capture function signatures reliably
3. Regex-based parsing → Rejected: fragile, language-specific, maintenance burden

---

### R4: PR Creation Strategy

**Context**: FR-009 requires the agent to create a pull request with a summary. The agent runs inside Docker and has git remote access.

**Findings**:
- **`gh` CLI (GitHub CLI)**: Single binary, creates PRs with `gh pr create --title "..." --body "..."`. Authenticates via `GITHUB_TOKEN` env var. Available as a Debian package. Simple, battle-tested.
- **Octokit (`@octokit/rest`)**: GitHub REST API client for Node.js. Full programmatic control. Requires npm install. More code but more flexible.
- **Simple `curl` to GitHub API**: No dependencies. Verbose but works anywhere.

**Decision**: Use **Octokit (`@octokit/rest`)** for PR creation. It integrates naturally into the TypeScript codebase, provides typed API responses, and allows structured PR body generation programmatically.

**Rationale**: Since the commit-push step is already TypeScript (using `simple-git`), keeping PR creation in TypeScript via Octokit maintains a single-language toolchain. Octokit also enables future extensions (adding labels, requesting reviewers, commenting on PRs). The `gh` CLI would require shell-out and string parsing of results.

**Alternatives considered**:
1. `gh` CLI → Rejected: requires shell-out from TypeScript, adds a binary dependency, harder to parse structured responses
2. `curl` to GitHub API → Rejected: verbose, no type safety, fragile string interpolation for JSON bodies
3. `simple-git` (only push, no PR) → Rejected: doesn't satisfy FR-009 requirement for PR creation with summary

---

### R5: Domain Allowlist Enforcement

**Context**: FR-020 requires restricting outbound network access to approved endpoints only (LLM API, git remote, package registry).

**Findings**:
- **Docker `--network` + iptables**: Create a custom Docker network with iptables rules allowing only specific IP ranges. Effective but requires resolving domain names to IPs at build time.
- **Docker's `--dns` + `/etc/hosts`**: Not sufficient for blocking — only affects DNS resolution, not direct IP connections.
- **Container-level iptables**: Install iptables in the container and configure rules in the entrypoint script. Requires `--cap-add=NET_ADMIN` to the container.
- **Proxy-based approach**: Route all traffic through an allowlist proxy (e.g., `tinyproxy`). The proxy allows only approved domains. No special capabilities needed.

**Decision**: Use a **proxy-based approach** with `tinyproxy` installed in the Docker image. Configure `HTTP_PROXY`/`HTTPS_PROXY` environment variables for all tools. The proxy allowlist includes:
- `api.anthropic.com` (Anthropic API)
- `api.openai.com` (OpenAI API)
- `github.com` (git remote)
- `registry.npmjs.org` (npm packages)
- `pypi.org` / `files.pythonhosted.org` (Python packages)

**Rationale**: Proxy-based filtering is the simplest to implement, doesn't require `NET_ADMIN` capabilities (which weaken container isolation), and works consistently across different Docker runtimes. Domain-based filtering (vs IP-based) handles CDN/load-balancer IP rotation automatically.

**Alternatives considered**:
1. iptables in container → Rejected: requires `--cap-add=NET_ADMIN`, weakening isolation; IP-based blocking fails when cloud providers rotate IPs
2. Docker custom network + iptables on host → Rejected: requires host-level configuration, not portable across dev machines
3. No network restriction (rely on container isolation only) → Rejected: doesn't satisfy FR-020; a prompt-injected command could exfiltrate code via arbitrary HTTP

**Trade-offs**: Proxy-based approach adds ~5ms latency to each HTTP request and one extra tool in the Docker image (~2MB). This is negligible compared to LLM API latency (~1-5 seconds).

---

### R6: Token Counting Library

**Context**: FR-013 requires a configurable token budget with graceful degradation. Need accurate token counting for budget enforcement.

**Findings**:
- **`js-tiktoken`**: Pure JavaScript implementation of OpenAI's tiktoken. No WASM, no native deps. Supports `cl100k_base` (GPT-4) and `o200k_base` encodings. ~500KB.
- **`tiktoken`**: Official OpenAI package with WASM backend. Faster than `js-tiktoken` but larger (~2MB).
- **`@anthropic-ai/tokenizer`**: Anthropic's official tokenizer. Most accurate for Claude models.
- **Approximation (chars / 4)**: Simple but ~10-15% inaccurate. Becomes unreliable at budget boundaries.

**Decision**: Use **`js-tiktoken`** as the primary token counter with `cl100k_base` encoding. For Anthropic models, apply a 1.05x correction factor (Claude tokens are slightly larger than GPT-4 tokens on average).

**Rationale**: `js-tiktoken` is pure JavaScript (zero native/WASM deps), fast enough for our use case (counting context chunks, not real-time streaming), and accurate to within ~2% for both GPT-4 and Claude. The correction factor for Anthropic models is simpler than maintaining two separate tokenizer libraries.

**Alternatives considered**:
1. `tiktoken` (WASM) → Rejected: WASM loading adds complexity; marginal speed benefit not needed for our batch-counting use case
2. `@anthropic-ai/tokenizer` → Rejected: provider-specific; we'd need two libraries for multi-provider support
3. Character-based approximation → Rejected: 10-15% inaccuracy at budget boundaries could cause premature truncation or budget overruns

---

## Summary of Decisions

| Topic | Decision | Key Selling Point |
|-------|----------|-------------------|
| Pi SDK stability | Pin v0.57.1 + adapter layer | Only 1 file to update on breaking changes |
| Vector store | vectra (pure TS) | Zero native deps, keeps entire stack in TypeScript |
| Tree-sitter | web-tree-sitter (WASM) | Portable, no node-gyp, official binding |
| PR creation | Octokit (@octokit/rest) | Typed API, stays in TypeScript, extensible |
| Domain allowlist | tinyproxy in Docker | No NET_ADMIN needed, domain-based filtering |
| Token counting | js-tiktoken (pure JS) | Zero deps, 2% accuracy, multi-provider |
