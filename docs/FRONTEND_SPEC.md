# IdlerDream Frontend Specification

## 1. Renderer responsibilities

The renderer displays data and collects explicit user intent. It does not infer project state and does not directly execute operating-system commands.

All privileged actions pass through the preload API and Electron main.

## 2. Application shell

### Sidebar

- App identity
- Overview and Settings
- Up to six project shortcuts
- Sidecar health

### Toolbar

- Search across project name and future indexed metadata
- Refresh
- Local profile display
- Windows title-bar control space reserved on the trailing side

### Content

Scrollable independently from the sidebar. Width is capped for large monitors.

## 3. Pages

### 3.1 First-run onboarding

Four-step flow:

1. OpenCode detection
2. API/model profile
3. read-only compatibility test
4. first workspace

Production form requirements:

- explicit validation state per step
- API Key reveal/hide, paste support and immediate clearing after storage
- permission-mode explanation before first inspection
- “local monitoring only” escape path when inspection cannot be configured

### 3.2 Overview

Top summary contains:

- count of projects that need user action
- active Agent count
- active project count
- expired-state count

Project groups remain stable. Attention affects styling and order within a group.

Project card content:

- identity and cycle/mode
- core status and freshness
- highest-priority next action
- actor and confidence
- live Agent count
- aggregate CPU/memory
- acceptance count or phase
- changed files and last verification

### 3.3 Project detail

Header actions:

- back
- open folder
- inspect now

Content:

- verified state hero
- live runtime summary
- deterministic facts
- model inferences
- process tree
- VCS/test facts
- cycle and acceptance criteria
- inspection permission/security status

### 3.4 Inspection panel

Floating, nonmodal and globally visible while a job runs.

Displays safe summaries only:

- stage
- last activity
- elapsed time
- file/tool budgets
- stage checklist
- cancel

### 3.5 Settings

v0.1 settings are intentionally narrow:

- OpenCode and model profile health
- rerun isolation test
- inactivity threshold
- raw report retention
- startup behavior

## 4. State rendering matrix

| Status | Color family | Icon | Attention |
|---|---|---|---|
| unknown | gray | activity | no |
| not_started | gray | activity | no |
| in_progress | blue | activity | no |
| waiting_user | orange | clock | yes |
| waiting_external | orange | clock | optional |
| blocked | red | alert | yes |
| conflict | red | alert | yes |
| completed | green | check | no |

Freshness is a separate badge:

- current: green
- possibly stale: yellow
- expired: red
- never inspected: gray

## 5. Data states

Every major surface needs:

- loading
- empty
- success
- partial data
- unavailable Sidecar
- unavailable OpenCode
- expired result
- conflict
- inspection running
- inspection cancelled/failed

Do not replace the entire app with a spinner after initial connection. Preserve last known data and show freshness/error state.

## 6. Keyboard flow

Recommended tab order:

1. sidebar navigation
2. project shortcuts
3. search
4. toolbar actions
5. page primary action
6. project cards in visual order
7. card secondary inspect action
8. detail controls/content disclosures
9. floating inspection cancel

Project cards use a native button or link-like semantic. Nested controls must stop propagation and remain separately focusable.

## 7. Responsive verification

Required manual screenshots:

- 1920 × 1080
- 1440 × 900
- 1280 × 720
- 1100 × 720 minimum

Check:

- no horizontal scrolling
- no Chinese vertical wrapping
- no critical next-action truncation
- no title-bar control overlap
- process tree columns remain legible
- inspection panel does not hide its cancel button

## 8. Frontend test plan

### Component tests

- StatusBadge maps every fixed state.
- ProjectCard highlights waiting/block/conflict.
- Expired project does not present old next action as current once production data logic is connected.
- ProcessTree disclosure works with keyboard.
- Inspection cancel calls the privileged control path.

### Accessibility

- axe on all pages
- keyboard smoke test
- reduced-motion screenshot
- light/dark appearance screenshots
- Windows High Contrast / forced-colors smoke test

### Visual regression

Capture the four required window sizes for:

- overview with mixed states
- project detail with process tree
- onboarding
- settings
- active inspection panel
