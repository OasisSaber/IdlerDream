# Dashboard Page Override

## Goal

Compare projects quickly while preserving the distinction between verified judgment and live runtime activity.

## Hierarchy

1. Large title and short explanation
2. Attention summary + aggregate metrics
3. Pinned/current projects
4. Active projects
5. Collapsed inactive/completed/archive groups

## Project card rules

- Two-column grid above 1080 px.
- Card must remain readable at 510 px width.
- Next action occupies more width than runtime resource data.
- User-attention styling is an orange leading rail and border, not a full red card.
- “Inspect” can appear on hover but must remain keyboard reachable.
- Expired state removes the old next action from authoritative presentation in production data.

## Empty dashboard

Show an “Add workspace” action and explain that no Agent is started or controlled by IdlerDream.
