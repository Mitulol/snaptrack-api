"""Redis cache-aside behaviour for the hot photo-metadata read path."""

import fakeredis
import pytest
import redis

from app import cache
from app.services import photo_service


def _upload(client, headers, make_image):
    files = {"file": ("pic.png", make_image(), "image/png")}
    return client.post("/photos", headers=headers, files=files).json()["id"]


def test_get_photo_populates_cache(client, auth_headers, make_image):
    headers = auth_headers()
    pid = _upload(client, headers, make_image)

    assert cache.get_cache_client().get(cache.photo_cache_key(pid)) is None
    client.get(f"/photos/{pid}", headers=headers)
    assert cache.get_cache_client().get(cache.photo_cache_key(pid)) is not None


def test_second_read_served_from_cache_without_db(client, auth_headers, make_image, monkeypatch):
    headers = auth_headers()
    pid = _upload(client, headers, make_image)
    client.get(f"/photos/{pid}", headers=headers)  # warm

    def _boom(*args, **kwargs):
        raise AssertionError("DB was hit on a cache hit")

    monkeypatch.setattr(photo_service, "get_photo", _boom)
    resp = client.get(f"/photos/{pid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == pid


def test_patch_invalidates_cache(client, auth_headers, make_image):
    headers = auth_headers()
    pid = _upload(client, headers, make_image)
    client.get(f"/photos/{pid}", headers=headers)  # warm

    client.patch(f"/photos/{pid}", headers=headers, json={"caption": "updated"})
    assert cache.get_cache_client().get(cache.photo_cache_key(pid)) is None

    body = client.get(f"/photos/{pid}", headers=headers).json()
    assert body["caption"] == "updated"


def test_cache_hit_for_other_user_does_not_leak(client, auth_headers, make_image):
    alice = auth_headers("alice@example.com")
    bob = auth_headers("bob@example.com")
    pid = _upload(client, alice, make_image)
    client.get(f"/photos/{pid}", headers=alice)  # warm alice's photo into cache
    assert client.get(f"/photos/{pid}", headers=bob).status_code == 404


def test_cache_degrades_gracefully_when_redis_down(client, auth_headers, make_image):
    class BrokenRedis(fakeredis.FakeRedis):
        def get(self, *a, **k):
            raise redis.ConnectionError("down")

        def set(self, *a, **k):
            raise redis.ConnectionError("down")

    cache.set_cache_client(BrokenRedis(decode_responses=True))
    headers = auth_headers()
    pid = _upload(client, headers, make_image)

    resp = client.get(f"/photos/{pid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == pid


@pytest.mark.parametrize("bad", ["not-json", ""])
def test_cache_get_json_tolerates_corrupt_payload(bad):
    cache.get_cache_client().set("photo:1", bad)
    assert cache.cache_get_json("photo:1") is None
