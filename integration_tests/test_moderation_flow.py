"""The moderation feature end to end against real Postgres + Redis.

Exercises behaviour the SQLite/fakeredis suite can only approximate:
real FK cascade, the audit row outliving the cascade, and the Redis
cache-aside key actually being written and invalidated.
"""


def _upload(client, headers, make_png):
    files = {"file": ("p.png", make_png(), "image/png")}
    return client.post("/photos", headers=headers, files=files).json()["id"]


def test_action_cascades_flags_but_keeps_audit_in_postgres(client, db, register, make_png):
    from sqlalchemy import select

    from app.models import Flag, ModerationAction, Photo

    admin = register("admin@itest.dev", admin=True)
    owner = register("owner@itest.dev")
    reporter2 = register("r2@itest.dev")

    pid = _upload(client, owner, make_png)
    fid = client.post(
        f"/photos/{pid}/flag", headers=owner, json={"reason": "spam"}
    ).json()["id"]
    # a second reporter also flags it
    client.post(f"/photos/{pid}/flag", headers=reporter2, json={"reason": "nudity"})

    resp = client.post(f"/moderation/{fid}/decision", headers=admin, json={"decision": "action"})
    assert resp.status_code == 200

    # real ON DELETE CASCADE removed the photo and both flags...
    assert db.get(Photo, pid) is None
    assert db.scalars(select(Flag).where(Flag.photo_id == pid)).all() == []
    # ...but the immutable audit row (plain int refs) survived
    actions = db.scalars(select(ModerationAction).where(ModerationAction.photo_id == pid)).all()
    assert len(actions) == 1
    assert actions[0].decision.value == "action"


def test_cache_aside_key_lives_in_real_redis(client, register, make_png):
    from app.cache import get_cache_client, photo_cache_key

    headers = register("cache@itest.dev")
    pid = _upload(client, headers, make_png)
    redis = get_cache_client()

    assert redis.get(photo_cache_key(pid)) is None
    client.get(f"/photos/{pid}", headers=headers)
    assert redis.get(photo_cache_key(pid)) is not None          # warmed

    client.patch(f"/photos/{pid}", headers=headers, json={"caption": "x"})
    assert redis.get(photo_cache_key(pid)) is None              # invalidated by the write


def test_moderation_action_invalidates_the_photo_cache(client, register, make_png):
    from app.cache import get_cache_client, photo_cache_key

    admin = register("admin2@itest.dev", admin=True)
    owner = register("owner2@itest.dev")
    pid = _upload(client, owner, make_png)
    fid = client.post(f"/photos/{pid}/flag", headers=owner, json={"reason": "spam"}).json()["id"]

    client.get(f"/photos/{pid}", headers=owner)  # warm the cache
    assert get_cache_client().get(photo_cache_key(pid)) is not None

    client.post(f"/moderation/{fid}/decision", headers=admin, json={"decision": "action"})
    assert get_cache_client().get(photo_cache_key(pid)) is None
    assert client.get(f"/photos/{pid}", headers=owner).status_code == 404


def test_action_decision_persists_a_sent_notification_in_postgres(client, db, register, make_png):
    from sqlalchemy import select

    from app.models import Notification, NotificationStatus, Photo

    admin = register("admin4@itest.dev", admin=True)
    owner = register("owner4@itest.dev")

    pid = _upload(client, owner, make_png)
    fid = client.post(f"/photos/{pid}/flag", headers=owner, json={"reason": "spam"}).json()["id"]

    client.post(f"/moderation/{fid}/decision", headers=admin, json={"decision": "action"})

    rows = db.scalars(select(Notification)).all()
    assert [r.recipient_email for r in rows] == ["owner4@itest.dev"]
    # the eager Celery task delivered it (console backend) before the request returned
    assert rows[0].status is NotificationStatus.SENT and rows[0].sent_at is not None
    # plain-int refs — the row outlives the photo (and flag) it is about
    assert rows[0].photo_id == pid
    assert db.get(Photo, pid) is None


def test_duplicate_flag_hits_the_real_unique_constraint(client, register, make_png):
    headers = register("dup@itest.dev")
    pid = _upload(client, headers, make_png)
    assert client.post(f"/photos/{pid}/flag", headers=headers, json={"reason": "spam"}).status_code == 201
    # the DB UNIQUE(photo_id, reporter_id) — not app logic — is what rejects this
    assert client.post(f"/photos/{pid}/flag", headers=headers, json={"reason": "other"}).status_code == 409


def test_full_flow_over_http(client, register, make_png):
    admin = register("admin3@itest.dev", admin=True)
    owner = register("owner3@itest.dev")
    pid = _upload(client, owner, make_png)

    fid = client.post(
        f"/photos/{pid}/flag", headers=owner, json={"reason": "copyright", "note": "mine"}
    ).json()["id"]

    queue = client.get("/moderation/queue", headers=admin).json()
    assert queue["total"] == 1 and queue["items"][0]["id"] == fid
    assert queue["items"][0]["reporter_email"] == "owner3@itest.dev"

    client.post(f"/moderation/{fid}/decision", headers=admin, json={"decision": "dismiss"})
    assert client.get("/moderation/queue", headers=admin).json()["total"] == 0
    assert client.get(f"/photos/{pid}", headers=owner).status_code == 200  # dismiss keeps it
