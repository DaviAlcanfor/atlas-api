"""Write v1.2 part A response samples from the LOCAL dev DB (run from atlas-api, PYTHONPATH=src)."""
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from atlas_api.config import get_settings
from atlas_api.main import create_app

out = Path(sys.argv[1])
paths = {}
for iso in ("BR", "JP", "DE"):
    paths[f"{iso} profile"] = f"/v1/countries/{iso}/profile"
    paths[f"{iso} economy"] = f"/v1/countries/{iso}/economy"
paths["compare BR,AR,MX"] = "/v1/economy/compare?countries=BR,AR,MX"
paths["currency BRL"] = "/v1/currencies/BRL"
paths["currency history BRL vs USD,EUR 1y"] = "/v1/currencies/BRL/history?vs=USD,EUR"
samples: dict[str, object] = {"_note": "Generated from the LOCAL dev DB (contract v1.2 part A, CR-003). "
                                       "Real data, not production. `languages_spoken` is a field of "
                                       "GET /v1/countries/{iso2}; only that field is shown."}
with TestClient(create_app(get_settings().database_url)) as c:
    for name, path in paths.items():
        r = c.get(path)
        assert r.status_code == 200, (path, r.status_code, r.text)
        samples[name] = {"GET": path, "body": r.json()}
    for iso in ("BR", "JP", "DE"):
        path = f"/v1/countries/{iso}"
        samples[f"{iso} languages_spoken"] = {"GET": path + " (field languages_spoken)",
                                              "body": c.get(path).json()["languages_spoken"]}
out.write_text(json.dumps(samples, ensure_ascii=False, indent=1), encoding="utf-8")
print("wrote", out, out.stat().st_size, "bytes")
