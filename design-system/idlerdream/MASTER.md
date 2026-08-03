# IdlerDream Design System — MASTER

**Status:** v0.1 source of truth  
**Product:** Windows local operations dashboard for multiple coding workspaces and Agents  
**Stack:** Electron + React + TypeScript  
**Design direction:** Apple-inspired desktop utility, adapted to Windows behavior  
**UI/UX Pro Max dials:** variance 4/10 · motion 3/10 · density 7/10

Page-specific files may refine layout, but must not override accessibility, interaction size, semantic status or token rules in this document.

---

## 1. Product experience thesis

IdlerDream must answer two questions faster than the user can inspect multiple terminals:

1. Where is each project now?
2. What is the single next action, and who owns it?

The UI is therefore a **project state instrument**, not a generic monitoring wall and not a task manager.

### Primary experience qualities

- **Quiet confidence:** calm surfaces, restrained accent color, no gaming-style glow.
- **Evidence before decoration:** verified state and deterministic facts are visually dominant.
- **Layered clarity:** separate live runtime activity from verified project judgment.
- **Desktop efficiency:** sidebar navigation, persistent search, dense but readable project cards.
- **Reversible actions:** no destructive or high-impact action is hidden behind a single ambiguous icon.

### Explicit anti-patterns

- Generic “card wall” with equal visual weight for every metric.
- Tiny 8–10 px body text.
- Excessive neon gradients, bloom, animated particles or cyberpunk styling.
- Color-only state communication.
- Icons represented by emoji.
- Percentage progress without confirmed weighting.
- Live activity silently replacing verified status.
- Hover-only access to essential controls.
- Full-screen modal for routine project inspection.

---

## 2. Apple-inspired interpretation

The product runs on Windows. “Apple style” means applying transferable interaction and visual principles, not imitating macOS controls in ways that conflict with Windows.

### Applied principles

- Use the system font stack and dynamic system appearance.
- Keep a stable leading sidebar for top-level areas and project shortcuts.
- Integrate global search and window-level actions into a translucent toolbar.
- Use materials sparingly to separate sidebar, toolbar, cards and floating inspection panels.
- Prefer semantic system-like colors with high contrast and dark-mode equivalents.
- Use large titles for page identity, compact labels for metadata, and clear hierarchy.
- Preserve Windows title-bar buttons and native folder opening behavior.
- Use rounded rectangles with moderate radii; avoid making every item a pill.
- Animate state changes subtly and respect reduced-motion settings.

### Source references

- Apple Human Interface Guidelines: https://developer.apple.com/design/human-interface-guidelines
- Sidebars: https://developer.apple.com/design/human-interface-guidelines/sidebars
- Materials: https://developer.apple.com/design/human-interface-guidelines/materials
- Typography: https://developer.apple.com/design/human-interface-guidelines/typography
- Accessibility: https://developer.apple.com/design/human-interface-guidelines/accessibility
- Toolbars: https://developer.apple.com/design/human-interface-guidelines/toolbars

---

## 3. Information architecture

### Level 1

- Overview
- Settings

### Persistent project shortcuts

The sidebar may list up to six recent or pinned projects. This is navigation, not another project status panel. Show only:

- monogram
- project name
- phase or “not inspected”
- attention dot when needed

### Overview groups

1. Pinned / current primary projects
2. Active projects
3. Inactive projects
4. Completed projects
5. Archived projects

“Needs action” is a visual priority and sorting signal, not a separate destination.

---

## 4. Layout system

### Window

- Recommended default: 1480 × 940
- Minimum: 1100 × 720
- Desktop-only v0.1; no mobile layout required
- No horizontal scrolling at 1100 px minimum width

### Shell

- Sidebar: 260 px; compresses to 232 px below 1260 px
- Toolbar: 52 px
- Content maximum: 1560 px
- Content padding: 36 px; 26 px below 1260 px

### Grid

- Base spacing unit: 4 px
- Primary spacing values: 4, 8, 12, 14, 16, 20, 24, 28, 32, 36, 48, 60
- Project grid: two columns; one column below 1080 px
- Detail layout: main content + 330 px supporting column; one column below 1260 px

### Density rules

This is a dense dashboard, but density must come from grouping, not tiny typography.

- Body text never below 11 px in production UI.
- Metadata may use 9–10 px only when nonessential and paired with adequate contrast.
- Main action controls are at least 44 px tall.
- Dense process tables may use 10 px labels but retain 60 px rows.

---

## 5. Typography

### Font families

```css
--font-display: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI Variable Display", "Segoe UI", sans-serif;
--font-text: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI Variable Text", "Segoe UI", sans-serif;
--font-mono: "SFMono-Regular", "Cascadia Code", "Cascadia Mono", Consolas, monospace;
```

Do not bundle or redistribute Apple font files. Use installed/system fallbacks only.

### Type scale

| Role | Size | Weight | Line height | Usage |
|---|---:|---:|---:|---|
| Large title | 38 px responsive | 700 | 1.08 | Overview page title |
| Title 1 | 28 px | 700 | 1.15 | Project title |
| Title 2 | 21 px | 680 | 1.25 | Priority summary |
| Title 3 | 17–18 px | 680 | 1.3 | Panels and sections |
| Headline | 14 px | 650 | 1.4 | Project names |
| Body | 13 px | 400–600 | 1.55–1.65 | Summaries and guidance |
| Subheadline | 11–12 px | 500–620 | 1.5 | Controls and secondary content |
| Caption | 9–10 px | 500–700 | 1.4 | Metadata, timestamps, badges |

### Typography rules

- Use sentence case, not all caps, except short eyebrow labels.
- Avoid vertical Chinese wrapping.
- Do not truncate the unique next action before two lines.
- Paths and commands use monospaced font and always ellipsize in the middle or end.
- Use tabular numbers for CPU, memory and durations where possible.

---

## 6. Color system

### Neutral semantic tokens

Light appearance:

```text
Canvas              #F3F4F7
Elevated canvas     #F8F8FA
Primary surface     #FFFFFF
Secondary surface   #F6F7FA
Tertiary surface    #EFF1F5
Primary text        #1D1D1F
Secondary text      rgba(60,60,67,.78)
Tertiary text       rgba(60,60,67,.58)
Separator           rgba(60,60,67,.16)
```

Dark appearance:

```text
Canvas              #111216
Elevated canvas     #17181D
Primary surface     #222328
Secondary surface   #292A30
Tertiary surface    #303138
Primary text        #F5F5F7
Secondary text      rgba(235,235,245,.76)
Tertiary text       rgba(235,235,245,.55)
Separator           rgba(255,255,255,.105)
```

### Semantic accents

| Meaning | Light | Dark | Use |
|---|---|---|---|
| Accent / active | #007AFF | #0A84FF | selected nav, primary action, in progress |
| Success | #248A3D | #30D158 | completed, current, pass |
| Caution | #B77900 | #FFD60A | possibly stale |
| User attention | #C93400 | #FF9F0A | waiting user, attention highlight |
| Destructive / blocked | #D70015 | #FF453A | blocked, conflict, failed |
| Inference | #8944AB | #BF5AF2 | model inference evidence |
| Runtime data | #008C91 | #64D2FF | CPU/memory/process accents |

### State communication

Every state must use at least two of:

- text label
- icon
- color
- border or shape

Do not use green/red dots without labels in the main content.

---

## 7. Materials, elevation and shape

### Materials

- Sidebar: thick translucent material, 28 px blur.
- Toolbar: regular translucent material, 26 px blur.
- Cards: regular material with one-pixel separator and low shadow.
- Inspection panel: thick material and elevated shadow.
- Avoid backdrop-filter on every nested panel; use solid secondary surfaces inside cards.

### Corner radii

- Small controls: 10–11 px
- Standard cards: 18 px
- Hero or floating panel: 24 px
- Badges: pill only for compact status labels

### Elevation

- Flat sections: separator only
- Project card: low shadow
- Hovered card: medium shadow and 2 px translation
- Floating inspection panel: high shadow

No heavy inner shadows or thick gradients.

---

## 8. Core components

### Sidebar item

- Minimum height 44 px
- Icon 18 px
- Selected state uses material fill and blue icon
- Project attention uses 7 px orange dot with halo

### Project card

Must include:

- identity and status badges
- verified next action
- actor and confidence
- live Agent count and aggregate CPU/memory
- acceptance count or phase
- changed files and last verification time

Attention cards receive an orange leading bar and stronger border. Do not paint the entire card orange or red.

### Status badge

- Height 25–28 px
- Icon 11–12 px
- Short localized label
- Semantic tint background

### Process tree

- 60 px row height
- Maximum two levels expanded by default
- Name, command summary, CPU, memory and association confidence
- Complete command line never shown unredacted
- Keyboard-operable disclosure button

### Inspection panel

- Nonmodal floating panel
- Shows safe, simplified progress only
- Includes elapsed time and budget counters
- Cancel is visible and labeled
- Source code and hidden reasoning never appear

### Settings row

- Label and description on left
- control on right
- 68 px minimum row height
- destructive actions isolated from ordinary settings

---

## 9. Interaction rules

### Interaction size

- Primary and secondary buttons: 44 px minimum height
- Icon buttons: visual size 38 px; interactive hit target should be 44 px via padding or parent spacing
- Sidebar rows: 44 px minimum
- Disclosure controls: at least 26 px inside a 44 px row

### Hover and press

- Hover is supplemental only.
- Essential actions must remain keyboard accessible.
- Press state uses slight scale and stronger surface fill.
- Avoid instantaneous changes; 140–220 ms is standard.

### Focus

All interactive elements must show a 3 px blue translucent focus ring using `:focus-visible`.

### Loading

- Preserve layout dimensions.
- Use inline spinner or progress state; never blank the whole window after initial connection.
- During inspection, display last activity and elapsed time.

### Empty states

State the missing information and next valid action. Avoid illustrations in v0.1.

### Destructive actions

- Cancel inspection: immediate but clearly labeled; it does not destroy project data.
- Delete snapshots/projects: future flows require confirmation and scope summary.

---

## 10. Motion

Motion level is intentionally low.

Allowed:

- page entrance: 220 ms, 5 px vertical
- card hover: 2 px vertical
- inspection panel entrance: 12 px horizontal
- progress orbit: slow and decorative, hidden under reduced motion
- toast entrance: 8 px vertical

Forbidden:

- continuous background particles
- bouncing cards
- elastic layout motion
- animated CPU graphs on overview cards
- motion that blocks reading or control

Respect `prefers-reduced-motion: reduce` by effectively disabling all transitions and animations.

---

## 11. Accessibility quality gate

The following are release blockers:

- Text contrast below WCAG AA for normal body text.
- Icon-only button without `aria-label`.
- Keyboard cannot reach or activate a visible control.
- Focus indicator is removed or clipped.
- State is encoded by color alone.
- Search or navigation causes horizontal scroll at minimum window size.
- Text overlaps, truncates critical action copy, or wraps Chinese vertically.
- Dynamic updates are not announced where they materially affect the user.
- Reduced-motion mode continues nonessential continuous animation.

Recommended automated checks:

- axe-core in renderer tests
- eslint-plugin-jsx-a11y
- keyboard smoke test for sidebar, search, project card and inspection cancel
- screenshots at 1920×1080, 1440×900, 1280×720 and minimum 1100×720

---

## 12. Content design

### Tone

- Direct and factual
- No anthropomorphic claims about what the model “knows”
- Distinguish “detected”, “verified”, “inferred” and “reported”

### Preferred labels

- “已验证状态” instead of “真实状态”
- “模型推断” instead of “AI 事实”
- “可能过时” instead of “大概没更新”
- “状态冲突” instead of silently selecting a winner
- “当前无可执行动作” instead of inventing work

### Error construction

```text
What happened
Why it matters
What the user can do next
```

Example:

> 本次巡检未更新状态。巡检期间工作区发生了新的提交，报告已保留为失效记录。请在工作区稳定后重新巡检。

---

## 13. Responsive and window behavior

- 1560 px and above: full two-column project grid and detail side rail.
- 1260–1559 px: narrower sidebar and single-column detail body.
- 1100–1259 px: one-column project grid; overview metrics move below attention summary.
- Below 1100 px: unsupported; Electron enforces minimum width.

No mobile navigation drawer is required in v0.1.

---

## 14. Implementation checklist

Before accepting any frontend PR:

- [ ] Uses tokens from `styles.css`; no arbitrary duplicate colors.
- [ ] 44 px interaction target satisfied.
- [ ] Uses inline SVG icon component, not emoji.
- [ ] Supports system light and dark appearance.
- [ ] Critical copy is not truncated.
- [ ] Verified state and live activity are visually distinct.
- [ ] CPU/memory remain supporting data, not project progress.
- [ ] Keyboard and focus behavior verified.
- [ ] Reduced-motion behavior verified.
- [ ] Minimum window size checked.
- [ ] No action outside the frozen v0.1 scope is introduced.
