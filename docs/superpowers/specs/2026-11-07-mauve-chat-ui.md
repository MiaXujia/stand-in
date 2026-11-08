# Mauve chat UI

## Goal

Give the existing private companion chat a gentle, elegant mauve visual identity while retaining its live React/API behavior.

## Approaches

- Recolor the current narrow dark layout: least work, but too plain on desktop.
- Add a decorative marketing page: more visual space, but distracts from the private conversation.
- **Chosen:** a responsive conversation shell. Desktop gets a quiet side panel and a focused chat surface; mobile keeps an edge-to-edge chat. This preserves the existing conversation flow.

## Design

- Warm ivory canvas, muted mauve primary, rose accents, ink-colored text, subtle paper surfaces, soft shadows.
- Main conversation stays driven by `useChat`: history, live streaming, typing, retry, state, and settings remain functional.
- Existing disclosure stays visible until dismissed. No fabricated messages or testimonials.
- Header shows the actual display name and current status. Composer remains available at the bottom.
- Settings use a clear modal hierarchy; focus and keyboard dismissal work on desktop.
- Responsive at small phones, landscape phones, and desktop. Visible focus, readable contrast, touch-size controls, reduced motion.

## Verification

Run the frontend build, inspect rendered desktop/mobile layouts, and exercise the real settings and chat controls when the local backend allows it.
