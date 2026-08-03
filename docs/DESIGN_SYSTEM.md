# Frontend Design System Summary

The complete source of truth is `design-system/idlerdream/MASTER.md`.

## Direction

IdlerDream uses an Apple-inspired desktop utility language adapted to Windows Electron:

- system typography rather than bundled brand fonts
- leading sidebar and integrated toolbar
- restrained semantic blue accent
- translucent materials only for structural layers
- white/neutral card surfaces with fine separators
- clear verified/live information separation
- system light/dark appearance
- minimal, functional motion

## UI/UX Pro Max workflow used

The frontend was designed using the skill workflow:

1. Detect product and stack: local operations dashboard, React/Electron.
2. Create and persist a global design system.
3. Add page-level overrides for dashboard, detail, onboarding, settings and inspection.
4. Apply priority checks in order: accessibility, interaction, performance, style, layout/responsiveness.
5. Implement with shared tokens in `apps/desktop/src/styles.css`.
6. Provide a static preview and frontend quality checklist.

The skill’s current public description and workflow are available in the official project:

- https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
- https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/main/.claude/skills/ui-ux-pro-max/SKILL.md

## Token implementation

The production tokens live in `apps/desktop/src/styles.css`. Key groups:

- neutral canvas/surface/material tokens
- semantic status colors
- typography families and hierarchy
- 4 px spacing rhythm
- 10–24 px radius hierarchy
- 140/220 ms motion timings
- system dark appearance overrides

## Accessibility baseline

- normal text targets WCAG AA contrast
- 44 px main interaction targets
- visible `:focus-visible` ring
- icon buttons require accessible names
- state uses label + icon + tint
- reduced motion supported
- forced colors supported
- no critical hover-only action
- minimum window size prevents compressed/unreadable layout

## Apple design references

- https://developer.apple.com/design/human-interface-guidelines
- https://developer.apple.com/design/human-interface-guidelines/sidebars
- https://developer.apple.com/design/human-interface-guidelines/materials
- https://developer.apple.com/design/human-interface-guidelines/typography
- https://developer.apple.com/design/human-interface-guidelines/accessibility
- https://developer.apple.com/design/human-interface-guidelines/toolbars
