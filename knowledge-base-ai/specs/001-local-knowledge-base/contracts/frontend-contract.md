# Frontend Interface Contract: React Web Application

**Feature**: 001-local-knowledge-base  
**Date**: 2026-03-02

---

## 1. Pages / Routes

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | `Dashboard` | Landing page — quick stats, recent conversations, ingestion status |
| `/chat` | `ChatView` | Main conversational interface |
| `/chat/:conversationId` | `ChatView` | Continue existing conversation |
| `/documents` | `DocumentList` | Browse ingested documents, trigger ingestion |
| `/documents/:documentId` | `DocumentDetail` | Document details + summary |
| `/settings` | `Settings` | Configuration (model provider, chunk size, etc.) |

---

## 2. Core UI Components

### 2.1 Chat Interface

```
┌─────────────────────────────────────────────┐
│  ┌──────────┐                    ┌────────┐ │
│  │Sidebar   │  Chat Area         │ Sources│ │
│  │          │                    │ Panel  │ │
│  │ + New    │  ┌───────────────┐ │        │ │
│  │ 🗑 Clear  │  │ Message #1    │ │ doc1   │ │
│  │ Conv 1 ◄─│  │ (user)        │ │ p.12   │ │
│  │ Conv 2   │  └───────────────┘ │        │ │
│  │ Conv 3   │  ┌───────────────┐ │ doc2   │ │
│  │          │  │ Message #2    │ │ p.5    │ │
│  │          │  │ (assistant)   │ │        │ │
│  │          │  │ [citations]   │ │        │ │
│  │          │  └───────────────┘ │        │ │
│  │          │                    │        │ │
│  │          │  ┌───────────────┐ │        │ │
│  │          │  │ Input box   ▶ │ │        │ │
│  │          │  └───────────────┘ │        │ │
│  └──────────┘                    └────────┘ │
└─────────────────────────────────────────────┘
```

**Behaviors**:
- Conversation sidebar: scrollable list sorted by `updated_at` DESC
- "New Chat" button at top of sidebar
- "Clear All" button in sidebar: shows confirmation dialog before calling DELETE /conversations (FR-024)
- Individual conversation: swipe-to-delete or context menu with "Delete" option; shows confirmation
- After clearing all or deleting the active conversation: redirect to a new empty chat session
- Message area: auto-scrolls to latest message
- Assistant messages: render markdown, show clickable source citations
- Source panel: shows relevant documents when a citation is clicked
- Input box: submit on Enter, Shift+Enter for newline
- Streaming: tokens appear incrementally via WebSocket

### 2.2 Document Management

```
┌─────────────────────────────────────────────┐
│ Documents                    [▶ Run Ingest ] │
│ ─────────────────────────────────────────── │
│ ┌─────────────────────────────────────────┐ │
│ │ Progress Bar (if ingesting)             │ │
│ │ █████████░░░░░░░░ 12/25 files          │ │
│ │ Current: architecture-guide.pdf         │ │
│ │ Est. remaining: 3 min                   │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ ┌──────────┬──────┬────────┬─────────────┐ │
│ │ Name     │ Type │ Chunks │ Actions     │ │
│ ├──────────┼──────┼────────┼─────────────┤ │
│ │ arch.pdf │ PDF  │ 42     │ 📄 Summary  │ │
│ │ api.md   │ MD   │ 15     │ 📄 Summary  │ │
│ │ spec.docx│ DOCX │ 28     │ 📄 Summary  │ │
│ └──────────┴──────┴────────┴─────────────┘ │
└─────────────────────────────────────────────┘
```

**Behaviors**:
- "Run Ingest" button triggers POST /ingestion/start
- Progress bar appears during ingestion via WebSocket
- Each document row shows summary button
- Click document name → DocumentDetail page
- Summary button → triggers POST /documents/{id}/summary

### 2.3 Dashboard

```
┌─────────────────────────────────────────────┐
│ Knowledge Base                              │
│ ─────────────────────────────────────────── │
│ ┌──────────┐ ┌──────────┐ ┌──────────────┐ │
│ │ 25 Docs  │ │ 5 Chats  │ │ Models: OK ✓│ │
│ └──────────┘ └──────────┘ └──────────────┘ │
│                                             │
│ Recent Conversations          Quick Actions │
│ ├─ Architecture Q&A (2h ago)  [+ New Chat]  │
│ ├─ API Design (1d ago)        [Ingest Docs] │
│ └─ Setup Guide (3d ago)       [Settings]    │
└─────────────────────────────────────────────┘
```

---

## 3. State Management

| State Slice | Contents | Persistence |
|-------------|----------|-------------|
| `conversations` | List of conversations, current conversation messages | Server (API calls) |
| `documents` | List of documents, ingestion status | Server (API calls) |
| `chat` | Current input, streaming state, pending message | In-memory |
| `ingestion` | Active job status, progress | WebSocket + polling |
| `ui` | Sidebar open/closed, active panel, theme | localStorage |

---

## 4. Real-Time Communication

| Channel | Type | Purpose |
|---------|------|---------|
| `/api/v1/ingestion/progress/{job_id}` | WebSocket | Ingestion progress updates |
| `/api/v1/conversations/{id}/stream` | WebSocket | Streaming LLM responses |

---

## 5. Responsive Breakpoints

| Breakpoint | Layout |
|------------|--------|
| Desktop (≥1024px) | 3-column: sidebar + chat + sources |
| Tablet (768-1023px) | 2-column: sidebar collapses to icons + chat |
| Mobile (<768px) | 1-column: tabs for sidebar/chat/sources |

---

## 6. Error Handling & Boundaries

Per Constitution Principle I (Production-Grade Architecture), every error MUST be surfaced appropriately:

| Scenario | UI Behavior |
|----------|-------------|
| API request fails (network) | Toast notification with retry option; no silent failures |
| API returns 4xx/5xx | Display error message from `error.message` field; include `request_id` for support |
| WebSocket disconnects | Auto-reconnect with exponential backoff; show "Reconnecting..." banner |
| LLM unavailable (503) | Disable chat input; show "Model unavailable" status with retry |
| Ingestion file error | Show inline error in progress list; continue processing remaining files |
| Auto re-embedding (FR-021) | Show persistent info banner: "Re-embedding documents due to model update..." with progress; link to ingestion progress page |
| Unhandled exception | React Error Boundary catches and renders fallback UI with "Report Issue" option |

**React Error Boundary**: Wrap each route-level component in an Error Boundary. Log caught errors to console with `request_id` context when available.

---

## 7. Loading & Empty States

### 7.1 Loading States

Every page that fetches server data shows a loading indicator while the initial request is in flight:

| Page | Loading UI |
|------|-----------|
| Dashboard | Skeleton cards for stat tiles + skeleton list rows for recent conversations |
| DocumentList | Skeleton table rows (5 rows) while GET /documents in flight |
| ChatView | Skeleton message bubbles (3 alternating user/assistant) while loading conversation history |
| DocumentDetail | Skeleton text blocks for metadata + summary area |
| Settings | Skeleton form fields while GET /config in flight |

Use `<LoadingSpinner />` for full-page initial loads; skeleton CSS (gray animated blocks) for content areas. Show stale data with a subtle "Refreshing…" indicator on re-fetches.

### 7.2 Empty States

| Scenario | UI Behavior |
|----------|-------------|
| No documents ingested (DocumentList) | Centered illustration + "No documents yet" heading + "Run Ingest to get started" subtext + "Run Ingest" CTA button |
| No conversations (sidebar) | "No conversations yet" text + "Start a new chat" link → `/chat` |
| No messages in new chat (ChatView) | Centered welcome message: "Ask anything about your documents" with 3 example prompt suggestions |
| No summary yet (DocumentDetail) | "No summary generated yet" placeholder + "Generate Summary" button |
| DocumentList with status filter — no results | "No documents match this filter" with "Clear filter" link |

---

## 8. UX Interaction Details

### 8.1 Settings Page

**Fields displayed** (read from GET /config, editable where noted):

| Field | Label | Editable | Validation |
|-------|-------|----------|------------|
| `knowledge_folder` | Knowledge Folder Path | Yes | Required; non-empty string |
| `embedding_model` | Embedding Model | Read-only | — |
| `llm_model` | LLM Model | Read-only | — |
| `chunk_size` | Chunk Size | Yes | Integer 100–4000 |
| `chunk_overlap` | Chunk Overlap | Yes | Integer 0–(chunk_size − 1) |
| `retrieval_top_k` | Retrieval Top-K | Yes | Integer 1–20 |
| `retrieval_similarity_threshold` | Similarity Threshold | Yes | Float 0.0–1.0 |
| `sliding_window_messages` | Conversation Window | Yes | Integer 1–50 |

**Save behavior**: "Save" button submits changed fields. Show success toast "Settings saved" on success; error toast on failure. Read-only fields display as plain text with a lock icon.

### 8.2 Document Deletion

- Each row in DocumentTable has a delete icon (🗑) in the Actions column.
- Clicking opens a confirmation dialog: "Delete [filename]? This will remove the document and all its indexed chunks. This cannot be undone." with "Cancel" / "Delete" buttons.
- On confirm: call DELETE /documents/{id}, remove row, show success toast "Document deleted".
- On 404 error: toast "Document not found" and refresh the list.

### 8.3 Conversation Deletion (supplement to §2.1)

- Confirmation text: "Delete this conversation? All messages will be permanently removed."
- After delete of active conversation: navigate to `/chat`.
- "Clear All" confirmation: "Delete all conversations? This cannot be undone." with a checkbox "I understand" that must be checked before the button is enabled.

### 8.4 Conversation Title

- Titles are **auto-generated only** — first 60 chars of the first user message (server-assigned).
- Manual rename is **not supported** in this version.

### 8.5 Pagination & Scroll

- DocumentList: single scrollable table (scope ≤ 200 docs). If API returns `next_cursor`, show "Load More" button at the bottom; no page numbers.
- Conversation sidebar: single scrollable list; same "Load More" pattern if needed.

### 8.6 DocumentDetail Page

```
┌─────────────────────────────────────────────┐
│ ← Back to Documents                         │
│                                             │
│ architecture-guide.pdf                      │
│ ─────────────────────────────────────────── │
│ Type: PDF  │  Size: 2.3 MB  │  Chunks: 42  │
│ Ingested: 2026-03-02 14:22                  │
│                                             │
│ ┌─────────────────────────────────────────┐ │
│ │ Summary                  [↻ Regenerate] │ │
│ │                                         │ │
│ │ This document covers ...                │ │
│ │                                         │ │
│ │ Sections referenced:                    │ │
│ │ • §3.1 Architecture Overview (p. 12)    │ │
│ │ • §4.2 API Design (p. 28)              │ │
│ └─────────────────────────────────────────┘ │
│                          [Generate Summary]  │
└─────────────────────────────────────────────┘
```

**Behaviors**:
- "Generate Summary" when `has_summary = false`; calls POST /documents/{id}/summary.
- While generating: spinner + "Generating summary…"; poll GET /documents/{id}/summary every 2s.
- "Regenerate" when summary exists; same flow.
- Error: inline "Summary generation failed. Try again." with retry button.

### 8.7 Run Ingest Button

- `knowledge_folder` configured: "Run Ingest" calls POST /ingestion/start directly.
- `knowledge_folder` empty: toast "Please set a Knowledge Folder in Settings before ingesting." with link to Settings.
- While job active: button disabled, label "Ingesting…".
- On 409 Conflict: toast "An ingestion job is already in progress."

### 8.8 Source Citations Format

- Inline numbered badges: **[1]**, **[2]** inserted at the referenced point in the assistant message.
- Clicking a badge opens/highlights the corresponding source in the SourcePanel.
- SourcePanel shows: document filename, page number (if available), relevance score as percentage ("87% match").

### 8.9 Markdown Rendering

Supported in assistant messages: headings (H1–H4), bold, italic, inline code, fenced code blocks with syntax highlighting, ordered/unordered lists, blockquotes, horizontal rules, links, GFM tables.

Not supported: LaTeX/math, images, raw HTML (stripped).

### 8.10 Auto-Scroll Behavior

- Auto-scrolls to latest message on: new user message submitted, streaming tokens arriving.
- Pauses if user manually scrolls up (≥ 100px from bottom).
- "⬇ Jump to latest" button appears when paused; clicking resumes auto-scroll.

### 8.11 Dashboard Quick Actions

| Button | Action |
|--------|--------|
| "+ New Chat" | Navigate to `/chat` |
| "Ingest Docs" | Navigate to `/documents` |
| "Settings" | Navigate to `/settings` |

Stat card data sources (loaded on page mount; refresh via "↻" icon):
- **Docs**: GET /documents total count
- **Chats**: GET /conversations total count
- **Models**: GET /health `status` field ("ok" → ✓ green, "degraded" → ⚠ yellow, "error" → ✗ red)

### 8.12 Estimated Time Remaining (ETR)

- Formula: `ETR = (elapsed_ms / processed_files) × remaining_files`
- Display: "~X min Y sec remaining"
- Fallback: "Calculating…" until ≥ 2 files processed; "~X hr remaining" if ETR > 60 min.

### 8.13 Chat When No Documents Ingested

- Chat input is not blocked; submissions are allowed.
- Assistant returns: "No documents have been indexed yet. Please ingest documents first, then ask your question."

### 8.14 Deleted Conversation Navigation

- `/chat/:id` with non-existent ID → API returns 404.
- Show toast "Conversation not found" then redirect to `/chat` within 1 second.

### 8.15 Reconnection Banner (supplement to §6)

- Position: fixed top of viewport, full-width, yellow/warning background.
- Text: "Connection lost — reconnecting…" with spinner.
- No auto-dismiss; disappears only on successful reconnection.
- After 5 failed retries: text changes to "Unable to reconnect. Please refresh the page." + "Refresh" button; spinner stops.

### 8.16 Re-Embedding Progress UI (FR-021, supplement to §6)

- Same progress bar component as manual ingestion is shown on `/documents`.
- Persistent info banner on all pages: "Re-embedding documents due to model update…" with "View Progress" link to `/documents`.
- Banner dismissed automatically when GET /health returns `reembedding.in_progress = false`.

---

## 9. Accessibility Baseline (WCAG 2.1 AA)

### 9.1 Keyboard Navigation

- All interactive elements reachable via `Tab` in logical DOM order.
- Enter/Space activate buttons and links; Escape closes modals.
- Document table row: pressing Enter on a filename navigates to DocumentDetail.

### 9.2 ARIA & Screen Reader

| Element | ARIA Requirement |
|---------|-----------------|
| Chat message list | `role="log"`, `aria-live="polite"` |
| Streaming response area | `aria-live="polite"` during streaming; `aria-live="off"` when complete |
| Progress bar | `role="progressbar"`, `aria-valuenow`, `aria-valuemin="0"`, `aria-valuemax="100"` |
| "Reconnecting" banner | `role="alert"`, `aria-live="assertive"` |
| Active sidebar nav item | `aria-current="page"` |
| Icon-only buttons | `aria-label` (e.g., `aria-label="Delete conversation"`) |
| Confirmation dialogs | `role="dialog"`, `aria-modal="true"`, `aria-labelledby` → dialog title |

### 9.3 Focus Management

- Modal open: focus moves to first focusable element inside the dialog.
- Modal close: focus returns to the triggering element.
- After sending a message: focus returns to the chat input box.
- After route change: focus moves to the page `<h1>`.

### 9.4 Color Contrast

- Body text on background: ≥ 4.5:1.
- Large text (18pt+ or 14pt bold): ≥ 3:1.
- UI component boundaries: ≥ 3:1.
- Status colors (red/yellow/green) paired with icon or text label — never color-only.

### 9.5 Skip Navigation

- Visually-hidden "Skip to main content" link as first focusable element on every page.
- ChatView additional skip links: "Skip to chat" and "Skip to sources".

---

## 10. Responsive Interaction Details

### 10.1 Tablet Sidebar (768–1023px)

- Collapses to 48px-wide icon-only strip.
- Tapping an icon expands the sidebar as a full-width overlay (does not push content).
- Tap outside or press Escape to close.

### 10.2 Mobile Tab Navigation (<768px)

- Bottom tab bar: **Chat** (💬), **Documents** (📄), **Settings** (⚙).
- Default active tab on load: **Chat**.
- Active tab: filled/colored icon; others outlined/grey.
- Supports both tap and left/right swipe to switch tabs.

### 10.3 Source Panel on Mobile

- Hidden by default during mobile browsing.
- Appears as a bottom-sheet modal (60% viewport height, draggable to dismiss) when a citation badge is tapped.
- Close via drag-down, backdrop tap, or "✕" button.
