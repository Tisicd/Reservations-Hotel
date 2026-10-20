import json
import pathlib

from app.main import create_app


def test_openapi_snapshot():
    here = pathlib.Path(__file__).parent
    snapshot = here / "openapi.json"
    current = json.dumps(create_app().openapi(), indent=2, sort_keys=True, default=str) + "\n"
    saved = snapshot.read_text()
    assert current == saved, "el contrato cambió; ejecuta `make snapshot-availability`"
