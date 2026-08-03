from __future__ import annotations

import compileall
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
required = [
    "README.md",
    "GITHUB_REPOSITORY_SETUP.md",
    "AGENTS.md",
    "ASSET_INDEX.md",
    "docs/CODE_REVIEW.md",
    "docs/PRODUCT_SPEC.md",
    "docs/ARCHITECTURE.md",
    "docs/DESIGN_SYSTEM.md",
    "docs/FRONTEND_SPEC.md",
    "docs/AGENT_ASSET_MANIFEST.md",
    "prompts/MASTER_IMPLEMENTATION_PROMPT.md",
    "prompts/GITHUB_REPOSITORY_SETUP_PROMPT.md",
    "prompts/FRONTEND_IMPLEMENTATION_PROMPT.md",
    "design-system/idlerdream/MASTER.md",
    "design-system/idlerdream/tokens.json",
    "preview/apple-dashboard.html",
    "docs/IMPLEMENTATION_PLAN.md",
    "docs/TEST_PLAN.md",
    "docs/VALIDATION_REPORT.md",
    "apps/desktop/src/App.tsx",
    "apps/desktop/src/styles.css",
    "apps/sidecar/idlerdream/main.py",
    "packages/protocol/report-schema.json",
]
missing = [item for item in required if not (ROOT / item).exists()]
if missing:
    raise SystemExit(f"Missing required assets: {missing}")
if not compileall.compile_dir(ROOT / "apps" / "sidecar" / "idlerdream", quiet=1):
    raise SystemExit("Python compilation failed")
json.loads((ROOT / "packages" / "protocol" / "report-schema.json").read_text(encoding="utf-8"))
print("asset verification passed")
