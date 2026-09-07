def test_healthz_is_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_readyz_reports_dependency_checks(client):
    resp = client.get("/readyz")
    body = resp.json()
    # fakeredis answers ping(); sqlite answers SELECT 1 -> both healthy in tests.
    assert resp.status_code == 200
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["redis"] == "ok"


def test_metrics_endpoint_exposed(client):
    client.get("/healthz")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "http_request" in resp.text


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == "snaptrack-api"
