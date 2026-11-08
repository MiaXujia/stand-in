# Mauve Chat UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a responsive, dynamic React chat UI with a gentle mauve theme.

**Architecture:** Keep the existing API and `useChat` state. Rework the App shell and the presentational components; define the visual system in CSS tokens. Do not add dependencies.

**Tech Stack:** React 18, TypeScript, Vite, CSS.

**Spec:** `docs/superpowers/specs/2026-11-07-mauve-chat-ui.md`

## Global Constraints

- Preserve real message history, SSE streaming, typing, retry, and control actions.
- Keep the AI/owner disclosure clear.
- Use a mauve-led, gentle and elegant theme.
- Support mobile and desktop, keyboard access, readable contrast, and reduced motion.

## Review Focus

- Long Chinese messages wrap and remain readable.
- A 375px phone and landscape viewport do not scroll horizontally or hide the composer.
- Settings open, close, and return focus predictably.
- Async states remain visible and the send button stays correctly disabled while busy.
- Existing disclosure and error feedback remain accessible.

### Task 1: Responsive visual shell

**Files:** `web/src/App.tsx`, `web/src/styles.css`, `web/index.html`, `web/vite.config.ts`

- [ ] Add a desktop side panel and keep mobile focused on the chat.
- [ ] Define semantic mauve color, spacing, and motion tokens; style all app states.
- [ ] Update browser and PWA theme colors.
- [ ] Run `pnpm build`.

### Task 2: Interaction details

**Files:** `web/src/components/ChatView.tsx`, `web/src/components/Composer.tsx`, `web/src/components/SettingsSheet.tsx`, `web/src/components/DisclosureBanner.tsx`

- [ ] Make the empty state and labels clear.
- [ ] Improve settings dialog focus and keyboard dismissal.
- [ ] Preserve streaming, retry, disclosure, and control behavior.
- [ ] Run build and inspect desktop/mobile UI.

### Task 3: Visual verification

**Files:** `web/public/favicon.svg`, `scripts/make_icons.py`, `web/public/icons/`

- [ ] Align app icons with the new palette.
- [ ] Run build and relevant backend tests, then check the final interface.
