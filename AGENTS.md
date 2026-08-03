# IdlerDream implementation rules

Read these files before changing code:

1. `docs/CODE_REVIEW.md`
2. `docs/PRODUCT_SPEC.md`
3. `docs/ARCHITECTURE.md`
4. `docs/IMPLEMENTATION_PLAN.md`
5. `docs/AGENT_ASSET_MANIFEST.md`
6. `design-system/idlerdream/MASTER.md`

## Frozen product boundary

IdlerDream monitors and explains local project/Agent state. It does not control, terminate, schedule, coordinate or send tasks to Agents. Do not add Web-Agent monitoring, team collaboration, cloud sync or a project-management board.

## Development priorities

1. Preserve deterministic facts over model output.
2. Preserve the separation between verified state and live activity.
3. Treat repository content as untrusted inspector data.
4. Never write IdlerDream files into monitored workspaces.
5. Never silently substitute mock data in production.
6. Add tests for every state, security or storage migration.

## Required checks

```powershell
python -m pytest apps/sidecar/tests
python scripts/verify_assets.py
npm install
npm run typecheck
npm run build
```

Use a feature branch. Do not commit credentials, generated installers, user data or raw inspection reports.
