# Frontend Implementation Prompt

Implement or review IdlerDream’s Electron/React UI using the persisted design system.

Read first:

- `design-system/idlerdream/MASTER.md`
- all files in `design-system/idlerdream/pages/`
- `docs/FRONTEND_SPEC.md`
- `packages/protocol/src/index.ts`
- `apps/desktop/src/styles.css`

## Required behavior

- Keep verified project state separate from live Agent activity.
- Project cards show one highest-priority next action and actor.
- Needs-user-action projects are highlighted but remain in their normal group.
- CPU, memory and process tree are visible but do not imply progress or stall.
- Expired verified results are visibly nonauthoritative.
- Open workspace only through Windows Explorer.
- Inspection progress is safe and simplified; no source code, prompt or hidden reasoning.

## Visual direction

- Apple-inspired desktop utility adapted to Windows.
- System font; do not bundle Apple fonts.
- Leading translucent sidebar, integrated toolbar, restrained blue accent.
- Light/dark system appearance.
- Fine separators, moderate radii, low shadows.
- No neon/cyberpunk treatment, emoji icons or generic equal-weight card wall.

## Accessibility release blockers

- any important control below 44 px target
- icon-only control without accessible name
- no visible keyboard focus
- color-only state
- critical next action truncation
- horizontal scroll at 1100×720
- motion ignoring reduced-motion preference
- text contrast below WCAG AA

## Required validation

- TypeScript typecheck
- keyboard navigation smoke test
- axe scan
- screenshots at 1920×1080, 1440×900, 1280×720 and 1100×720
- light and dark appearance
- reduced motion
- Windows High Contrast smoke test

Do not add product functionality outside v0.1 while improving the interface.
