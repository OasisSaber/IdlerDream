from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "sidecar"))

from idlerdream.models import InspectionReport  # noqa: E402

OUTPUT = ROOT / "packages" / "protocol" / "report-schema.json"
OUTPUT.write_text(
    json.dumps(InspectionReport.model_json_schema(), ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(OUTPUT)
