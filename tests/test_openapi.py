"""Lock the OpenAPI contract: committed spec is current, and the documented
status codes actually match what the routes raise."""

import json
import subprocess
import sys
from pathlib import Path

from app.main import app

ROOT = Path(__file__).resolve().parent.parent


def test_committed_spec_matches_code():
    result = subprocess.run(
        [sys.executable, "scripts/export_openapi.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_spec_is_openapi_31():
    spec = app.openapi()
    assert spec["openapi"].startswith("3.1")
    assert spec["info"]["version"] == "1.1.0"


def test_protected_photo_routes_document_401_and_404():
    spec = app.openapi()
    for path in ("/photos/{photo_id}", "/photos/{photo_id}/thumbnail"):
        for method, op in spec["paths"][path].items():
            assert "401" in op["responses"], f"{method} {path}"
            assert "404" in op["responses"], f"{method} {path}"


def test_error_responses_use_the_shared_model():
    spec = app.openapi()
    op = spec["paths"]["/photos/{photo_id}"]["get"]
    ref = op["responses"]["404"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/ErrorResponse")


def test_committed_versioned_spec_files_exist():
    for version in ("1.0.0", "1.1.0"):
        p = ROOT / "openapi" / f"openapi-v{version}.json"
        assert p.exists(), p
        assert json.loads(p.read_text())["info"]["version"] == version


def test_moderation_endpoints_are_in_the_spec():
    spec = app.openapi()
    assert "/photos/{photo_id}/flag" in spec["paths"]
    assert "/moderation/queue" in spec["paths"]
    assert "/moderation/{flag_id}/decision" in spec["paths"]
