import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from atlas_api.main import app

Path("openapi.generated.json").write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
