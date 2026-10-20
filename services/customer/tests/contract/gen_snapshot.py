import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.main import create_app  # noqa: E402

out = pathlib.Path(__file__).parent / "openapi.json"
schema = create_app().openapi()
out.write_text(json.dumps(schema, indent=2, sort_keys=True, default=str) + "\n")
print(f"snapshot escrito en {out}")
