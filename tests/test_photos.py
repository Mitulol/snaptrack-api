def _upload(client, headers, image_bytes, filename="pic.png", caption=None):
    files = {"file": (filename, image_bytes, "image/png")}
    data = {"caption": caption} if caption is not None else None
    return client.post("/photos", headers=headers, files=files, data=data)


def test_upload_creates_photo_with_pending_thumbnail(client, auth_headers, make_image):
    headers = auth_headers()
    resp = _upload(client, headers, make_image(800, 600))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["width"] == 800 and body["height"] == 600
    assert body["original_filename"] == "pic.png"
    assert body["thumbnail"]["status"] in {"pending", "processing", "ready"}


def test_upload_rejects_non_image(client, auth_headers):
    headers = auth_headers()
    files = {"file": ("notes.txt", b"just some text", "text/plain")}
    resp = client.post("/photos", headers=headers, files=files)
    # 400 (not 422): 422 is reserved for request-model validation, this is a
    # business rejection of the uploaded bytes.
    assert resp.status_code == 400
    assert resp.json()["detail"]


def test_upload_requires_auth(client, make_image):
    files = {"file": ("pic.png", make_image(), "image/png")}
    assert client.post("/photos", files=files).status_code == 401


def test_list_only_returns_own_photos(client, auth_headers, make_image):
    alice = auth_headers("alice@example.com")
    bob = auth_headers("bob@example.com")
    _upload(client, alice, make_image())
    _upload(client, alice, make_image())
    _upload(client, bob, make_image())

    resp = client.get("/photos", headers=alice)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert {i["owner_id"] for i in body["items"]} == {body["items"][0]["owner_id"]}


def test_list_pagination(client, auth_headers, make_image):
    headers = auth_headers()
    for _ in range(3):
        _upload(client, headers, make_image())
    resp = client.get("/photos?limit=2&offset=0", headers=headers)
    assert resp.json()["total"] == 3
    assert len(resp.json()["items"]) == 2


def test_get_photo_by_id(client, auth_headers, make_image):
    headers = auth_headers()
    pid = _upload(client, headers, make_image()).json()["id"]
    resp = client.get(f"/photos/{pid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == pid


def test_get_photo_not_owned_is_404(client, auth_headers, make_image):
    alice = auth_headers("alice@example.com")
    bob = auth_headers("bob@example.com")
    pid = _upload(client, alice, make_image()).json()["id"]
    assert client.get(f"/photos/{pid}", headers=bob).status_code == 404


def test_get_missing_photo_is_404(client, auth_headers):
    assert client.get("/photos/999999", headers=auth_headers()).status_code == 404


def test_patch_caption_owner_only(client, auth_headers, make_image):
    alice = auth_headers("alice@example.com")
    bob = auth_headers("bob@example.com")
    pid = _upload(client, alice, make_image()).json()["id"]

    ok = client.patch(f"/photos/{pid}", headers=alice, json={"caption": "sunset"})
    assert ok.status_code == 200 and ok.json()["caption"] == "sunset"

    denied = client.patch(f"/photos/{pid}", headers=bob, json={"caption": "hijack"})
    assert denied.status_code == 404


def test_delete_photo_owner_only(client, auth_headers, make_image):
    alice = auth_headers("alice@example.com")
    bob = auth_headers("bob@example.com")
    pid = _upload(client, alice, make_image()).json()["id"]

    assert client.delete(f"/photos/{pid}", headers=bob).status_code == 404
    assert client.delete(f"/photos/{pid}", headers=alice).status_code == 204
    assert client.get(f"/photos/{pid}", headers=alice).status_code == 404


def test_upload_with_caption(client, auth_headers, make_image):
    headers = auth_headers()
    resp = _upload(client, headers, make_image(), caption="my trip")
    assert resp.status_code == 201
    assert resp.json()["caption"] == "my trip"


def test_serve_original_file(client, auth_headers, make_image):
    headers = auth_headers()
    pid = _upload(client, headers, make_image()).json()["id"]
    resp = client.get(f"/photos/{pid}/file", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/")
