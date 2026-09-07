"""HTTP + RBAC tests for the moderation feature."""

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Flag, ModerationAction, Photo


def _upload(client, headers, make_image):
    files = {"file": ("p.png", make_image(), "image/png")}
    return client.post("/photos", headers=headers, files=files).json()["id"]


def _flag(client, headers, photo_id, reason="spam", note=None):
    body = {"reason": reason}
    if note is not None:
        body["note"] = note
    return client.post(f"/photos/{photo_id}/flag", headers=headers, json=body)


# --- POST /photos/{id}/flag -------------------------------------------------

def test_owner_can_flag_their_photo(client, auth_headers, make_image):
    h = auth_headers()
    pid = _upload(client, h, make_image)
    resp = _flag(client, h, pid, note="test")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["reason"] == "spam"


def test_non_owner_cannot_flag(client, auth_headers, make_image):
    owner = auth_headers("owner@example.com")
    other = auth_headers("other@example.com")
    pid = _upload(client, owner, make_image)
    assert _flag(client, other, pid).status_code == 404


def test_flag_missing_photo_is_404(client, auth_headers):
    assert _flag(client, auth_headers(), 999999).status_code == 404


def test_flag_requires_auth(client, auth_headers, make_image):
    pid = _upload(client, auth_headers(), make_image)
    assert client.post(f"/photos/{pid}/flag", json={"reason": "spam"}).status_code == 401


def test_duplicate_flag_is_409(client, auth_headers, make_image):
    h = auth_headers()
    pid = _upload(client, h, make_image)
    assert _flag(client, h, pid).status_code == 201
    assert _flag(client, h, pid, reason="other").status_code == 409


def test_flag_invalid_reason_is_422(client, auth_headers, make_image):
    h = auth_headers()
    pid = _upload(client, h, make_image)
    assert _flag(client, h, pid, reason="not-real").status_code == 422


# --- GET /moderation/queue -------------------------------------------------

def test_queue_requires_admin(client, auth_headers, admin_headers, make_image):
    user = auth_headers("u@example.com")
    pid = _upload(client, user, make_image)
    _flag(client, user, pid)

    assert client.get("/moderation/queue").status_code == 401
    assert client.get("/moderation/queue", headers=user).status_code == 403

    resp = client.get("/moderation/queue", headers=admin_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["photo_id"] == pid
    assert body["items"][0]["photo"]["owner_id"] is not None
    assert body["items"][0]["reporter_email"] == "u@example.com"


def test_queue_only_shows_pending(client, auth_headers, admin_headers, make_image):
    admin = admin_headers()
    user = auth_headers("u@example.com")
    pid = _upload(client, user, make_image)
    flag_id = _flag(client, user, pid).json()["id"]
    client.post(f"/moderation/{flag_id}/decision", headers=admin, json={"decision": "dismiss"})

    assert client.get("/moderation/queue", headers=admin).json()["total"] == 0


# --- POST /moderation/{flag_id}/decision ----------------------------------

def test_decision_requires_admin(client, auth_headers, make_image):
    user = auth_headers("u@example.com")
    pid = _upload(client, user, make_image)
    flag_id = _flag(client, user, pid).json()["id"]
    resp = client.post(f"/moderation/{flag_id}/decision", headers=user, json={"decision": "dismiss"})
    assert resp.status_code == 403


def test_dismiss_keeps_photo_and_resolves_flag(client, auth_headers, admin_headers, make_image):
    admin = admin_headers()
    user = auth_headers("u@example.com")
    pid = _upload(client, user, make_image)
    flag_id = _flag(client, user, pid).json()["id"]

    resp = client.post(
        f"/moderation/{flag_id}/decision", headers=admin, json={"decision": "dismiss", "note": "ok"}
    )
    assert resp.status_code == 200
    assert resp.json()["resolution"] == "dismissed"
    assert client.get(f"/photos/{pid}", headers=user).status_code == 200


def test_action_deletes_photo(client, auth_headers, admin_headers, make_image):
    admin = admin_headers()
    owner = auth_headers("owner@example.com")
    pid = _upload(client, owner, make_image)
    flag_id = _flag(client, owner, pid).json()["id"]

    resp = client.post(
        f"/moderation/{flag_id}/decision", headers=admin, json={"decision": "action"}
    )
    assert resp.status_code == 200
    assert resp.json()["decision"] == "action"
    assert client.get(f"/photos/{pid}", headers=owner).status_code == 404
    with SessionLocal() as s:
        assert s.get(Photo, pid) is None
        assert s.scalar(select(ModerationAction).where(ModerationAction.photo_id == pid)) is not None


def test_decision_on_missing_flag_is_404(client, admin_headers):
    assert client.post(
        "/moderation/999999/decision", headers=admin_headers(), json={"decision": "dismiss"}
    ).status_code == 404


def test_decision_twice_is_409(client, auth_headers, admin_headers, make_image):
    admin = admin_headers()
    user = auth_headers("u@example.com")
    pid = _upload(client, user, make_image)
    flag_id = _flag(client, user, pid).json()["id"]
    client.post(f"/moderation/{flag_id}/decision", headers=admin, json={"decision": "dismiss"})

    resp = client.post(f"/moderation/{flag_id}/decision", headers=admin, json={"decision": "action"})
    assert resp.status_code == 409


def test_decision_invalid_value_is_422(client, auth_headers, admin_headers, make_image):
    admin = admin_headers()
    user = auth_headers("u@example.com")
    pid = _upload(client, user, make_image)
    flag_id = _flag(client, user, pid).json()["id"]
    resp = client.post(f"/moderation/{flag_id}/decision", headers=admin, json={"decision": "nuke"})
    assert resp.status_code == 422


def test_full_flow(client, auth_headers, admin_headers, make_image):
    admin = admin_headers()
    owner = auth_headers("owner@example.com")
    pid = _upload(client, owner, make_image)

    flag_id = _flag(client, owner, pid, note="spammy").json()["id"]
    queue = client.get("/moderation/queue", headers=admin).json()
    assert [i["id"] for i in queue["items"]] == [flag_id]

    client.post(f"/moderation/{flag_id}/decision", headers=admin, json={"decision": "action"})
    assert client.get("/moderation/queue", headers=admin).json()["total"] == 0
    with SessionLocal() as s:
        assert s.scalars(select(Flag)).all() == []  # cascaded with the photo
