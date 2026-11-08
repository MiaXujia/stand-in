# Conversation Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add separate, persistent conversations with a left-side React session list and isolated reply context.

**Architecture:** SQLite sessions own messages and turns. API routes address a session explicitly. React keeps the selected session in the URL and stores pending streaming state per session.

**Tech Stack:** Python 3.12, FastAPI, SQLite/SQLAlchemy Core, React 18, TypeScript, Vite.

**Spec:** `docs/superpowers/specs/2026-11-07-conversation-management.md`

## Global Constraints

- Keep the existing single-token authorization and CSRF header.
- Preserve SSE event delivery, idempotent retry, and interrupted-turn recovery.
- Existing messages must be migrated without data loss.
- Short-term prompt history must be scoped to one session; persona and allowed long-term memory remain shared.
- No hardcoded demo conversation may appear in a fresh installation.

## Review Focus

- A client ID reused in another session must fail without leaking the prior turn.
- A session switch during a pending stream must not append bubbles to the newly selected session.
- An invalid session ID must return 404 without creating a session.
- A migration with legacy messages must preserve order, parts, and turn links.
- A migration with an empty database must leave the session list empty.

### Task 1: Data model and migration

**Files:** `app/adapters/sqlite/migrations/004_sessions.sql`, `app/adapters/sqlite/tables.py`, `app/adapters/sqlite/repositories.py`, `app/core/models.py`, `app/ports.py`, `test/test_sessions.py`, `test/test_delivery_migration.py`

- [ ] Write failing migration tests for empty and legacy databases.
- [ ] Add `sessions` table and `session_id` to messages/turns; backfill legacy data.
- [ ] Add a session repository plus scoped message/turn methods and cross-session idempotency check.
- [ ] Run migration and repository tests.

### Task 2: API and reply isolation

**Files:** `app/api/chat.py`, `app/api/schemas.py`, `app/services/reply.py`, `app/context.py`, `app/services/proactive.py` (or its actual scheduler owner), `test/test_sessions.py`, `test/test_turns.py`, `test/test_stream.py`

- [ ] Write failing API tests: create/list, per-session history, invalid ID, isolated prompt history, retry/stream recovery.
- [ ] Implement session-addressed routes and pass `session_id` through `ReplyService` and repositories.
- [ ] Route proactive messages to the dedicated daily session.
- [ ] Run the focused API, turn, and stream tests.

### Task 3: React session navigation

**Files:** `web/src/api/client.ts`, `web/src/api/types.ts`, `web/src/hooks/useChat.ts`, `web/src/hooks/useSessions.ts`, `web/src/components/SessionSidebar.tsx`, `web/src/App.tsx`, `web/src/theme.css`

- [ ] Add session API types and client calls.
- [ ] Build list, new-chat draft, selection, and mobile drawer in the existing mauve design.
- [ ] Scope chat state and pending-turn recovery by selected session; protect against stream output after switching.
- [ ] Verify keyboard, loading, error, desktop, 375px mobile, and landscape behavior.

### Task 4: Integration and migration verification

**Files:** `README.md`, `docs/superpowers/specs/2026-11-07-conversation-management.md`

- [ ] Run the complete backend test suite and `pnpm build`.
- [ ] Back up the real database before migration; verify empty and populated migration paths.
- [ ] Exercise create, send, switch, refresh, and mobile drawer against the running app.
- [ ] Document how sessions differ from shared memory and where proactive messages appear.
