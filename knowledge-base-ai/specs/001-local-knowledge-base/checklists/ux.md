# UX Requirements Quality Checklist: Local Knowledge Base Application

**Purpose**: Validate completeness, clarity, and coverage of frontend/UI requirements in the spec and frontend-contract  
**Created**: 2026-03-02  
**Feature**: [spec.md](../spec.md) | [frontend-contract.md](../contracts/frontend-contract.md)  
**Depth**: Standard | **Focus**: Completeness, Accessibility, Error States  
**Constitution Ref**: Principle V (Lightweight & User-Friendly UI)

---

## Requirement Completeness

- [x] CHK001 — Are loading/skeleton states defined for all pages that fetch server data (Dashboard, DocumentList, ChatView, DocumentDetail, Settings)? [Completeness, Gap]
- [x] CHK002 — Are empty states specified for zero-data scenarios (no documents ingested, no conversations yet, no messages in new chat)? [Completeness, Gap]
- [x] CHK003 — Is the Settings page's content defined — which configuration fields are editable, what validation rules apply, and what happens on save? [Completeness, Gap — §1 Routes lists Settings but §2 has no wireframe or behavior spec]
- [x] CHK004 — Are document deletion requirements specified in the frontend (e.g., can users remove a document from the UI, and what confirmation is shown)? [Completeness, Gap — DELETE endpoint exists in api-contracts but no UI behavior defined]
- [x] CHK005 — Are conversation deletion requirements specified in the frontend (delete button, confirmation dialog, list update after deletion)? [Completeness, Gap — DELETE endpoint exists but no UI behavior defined]
- [x] CHK006 — Is the conversation rename/title-edit interaction defined (inline edit, modal, or auto-generated only)? [Completeness, Gap — Conversation.title field exists but no edit flow specified]
- [x] CHK007 — Are pagination or infinite-scroll requirements defined for the document list and conversation sidebar when data exceeds one screen? [Completeness, Gap — API supports pagination but frontend scroll/load-more behavior unspecified]
- [x] CHK008 — Is the DocumentDetail page content specified — what information is displayed, how the summary is shown, and what actions are available? [Completeness, Gap — §1 Routes lists it but §2 has no wireframe]
- [x] CHK009 — Are requirements defined for how the "Run Ingest" button behaves when source_folder is not configured or needs user input? [Completeness, Gap — POST body has optional source_folder but UI interaction unspecified]
- [x] CHK010 — Is the summary generation feedback defined — loading state while LLM processes, streaming vs. full-response display, error if document not yet ingested? [Completeness, Spec §FR-017]

## Requirement Clarity

- [x] CHK011 — Is "auto-scrolls to latest message" behavior quantified — does it scroll during streaming tokens, only on new messages, or both? Does it respect user scroll-up? [Clarity, frontend-contract §2.1]
- [x] CHK012 — Is "clickable source citations" format defined — inline links, footnote-style numbers, expandable cards, or tooltip previews? [Clarity, frontend-contract §2.1]
- [x] CHK013 — Is "render markdown" specified with which Markdown features are supported (tables, code blocks, headings, images, LaTeX)? [Clarity, frontend-contract §2.1]
- [x] CHK014 — Are the "Quick Actions" on the Dashboard specified with exact behaviors — does "New Chat" navigate to /chat, does "Ingest Docs" navigate to /documents or open a modal? [Clarity, frontend-contract §2.3]
- [x] CHK015 — Is "estimated time remaining" calculation method defined or left to implementation? Is a fallback defined when estimation is unreliable (e.g., first file)? [Clarity, Spec §FR-019]
- [x] CHK016 — Are the stat cards on the Dashboard ("25 Docs", "5 Chats", "Models: OK") defined with data sources and update frequency (real-time, on-page-load, polling)? [Clarity, frontend-contract §2.3]

## Accessibility Requirements

- [x] CHK017 — Are keyboard navigation requirements defined for all interactive elements (chat input, sidebar navigation, document table, buttons)? [Coverage, Gap]
- [x] CHK018 — Are screen reader requirements specified — ARIA labels for the chat interface, document table, progress bar, and status indicators? [Coverage, Gap]
- [x] CHK019 — Are focus management requirements defined for dynamic content — focus moves to new message after send, focus on error toast, focus trap in modals? [Coverage, Gap]
- [x] CHK020 — Are color contrast requirements specified to meet WCAG 2.1 AA for all text, buttons, and status indicators? [Coverage, Gap]
- [x] CHK021 — Is a skip-navigation link defined for the 3-column chat layout (sidebar, chat, sources) to allow keyboard users to jump between regions? [Coverage, Gap]

## Error & Edge Case States

- [x] CHK022 — Are requirements consistent between the error handling table in §6 and the actual UI components — does each component know which error scenario applies to it? [Consistency, frontend-contract §6]
- [x] CHK023 — Is the "Reconnecting..." banner behavior fully specified — position (top banner, toast, inline), auto-dismiss timing, and what happens if reconnection fails permanently? [Clarity, frontend-contract §6]
- [x] CHK024 — Is the behavior defined when a user navigates to a conversation that has been deleted (e.g., /chat/:id with invalid ID) — 404 page, redirect, or error toast? [Edge Case, Gap]
- [x] CHK025 — Is the behavior defined when the user submits a chat message but no documents have been ingested yet — warning, blocked input, or allow with degraded response? [Edge Case, Gap]
- [x] CHK026 — Is the behavior defined for the ingestion progress UI when a re-embedding is triggered automatically on startup (FR-021) — does it show the same progress bar, a different indicator, or a system notification? [Edge Case, Gap — FR-021 specifies auto re-embed but no UI behavior defined]

## Responsive & Layout Consistency

- [x] CHK027 — Are tablet (768-1023px) interaction patterns specified beyond layout — how does the collapsed sidebar expand (tap icon, swipe gesture, hover)? [Clarity, frontend-contract §5]
- [x] CHK028 — Are mobile tab behaviors defined — which tab is default, is there a tab indicator, can users swipe between tabs? [Clarity, frontend-contract §5]
- [x] CHK029 — Are the Source Panel's responsive behaviors specified — is it hidden on mobile during streaming and shown only when a citation is tapped? [Completeness, Gap]

## Notes

- Check items off as completed: `[x]`
- Items referencing `[Gap]` indicate requirements that are missing entirely and need to be added
- Items referencing `[Clarity]` indicate existing requirements that need more precise specification
- Items referencing specific sections (e.g., `§2.1`) point to the frontend-contract.md section
- Items referencing `Spec §FR-XXX` point to spec.md functional requirements
