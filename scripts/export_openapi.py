import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
os.environ.setdefault("CHAT_ENABLED", "true")  # keep /v1/chat in the contract file even while the router is off by default
from atlas_api.main import app

Path("openapi.generated.json").write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
