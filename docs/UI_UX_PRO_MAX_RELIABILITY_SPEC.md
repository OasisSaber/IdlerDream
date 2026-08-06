# UI/UX Pro Max Reliability Surface Specification

## Experience goal

Inspection reliability must be visible without turning the project page into a security console. The surface should answer:

1. Is this result complete, partially repaired or unverified?
2. Did the model inspect a filtered snapshot rather than the real workspace?
3. Are warnings semantic blockers or only formatting repairs?

## Apple-inspired application

- System font stack only; no redistributed Apple fonts.
- Moderate 18 px card radius and one-pixel separator.
- Materials used only for the reliability card and floating inspection panel.
- Green/yellow/red are paired with text, icon and border strip.
- 44 px minimum interactive rows.
- No decorative neon, charts or animated security theater.
- Reduced motion disables live pulse animation.
- Forced-colors adds explicit CanvasText borders.

## States

### Full

- green leading strip
- check icon
- `FULL` badge
- copy explains identity/fingerprint/Schema validation

### Partial

- yellow leading strip
- activity icon
- `PARTIAL` badge
- expandable normalization notes
- confidence is capped by Sidecar, not visually altered in the renderer

### Failed

- red leading strip
- alert icon
- `UNVERIFIED` badge
- error presented as status, not a destructive notification
- old expired next action remains hidden by existing state logic

## Inspection panel changes

The old panel displayed fictional values such as `12 / 40` and `28 / 100`. The replacement:

- shows actual job budget fields when supplied
- otherwise shows configured ceilings, not fake usage
- adds a compact snapshot-isolation strip
- maps machine stage keys to readable labels
- displays the latest normalization/snapshot warning

## Accessibility checklist

- card has an `aria-labelledby` title
- warning details use native `details/summary`
- error uses `role=status`
- color is never the sole signal
- keyboard focus remains provided by global design tokens
- no essential content appears only on hover
- Chinese text has normal line wrapping and no forced vertical layout
