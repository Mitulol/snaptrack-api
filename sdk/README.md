# SnapTrack Python SDK

`snaptrack-api-client/` is a typed Python client for the SnapTrack API,
**generated** from [`openapi/openapi.json`](../openapi/openapi.json) with
[`openapi-python-client`](https://github.com/openapi-generators/openapi-python-client)
(httpx + attrs, `py.typed`). It is not hand-edited.

## Regenerating

```bash
python -m venv .venv-sdk && .venv-sdk/bin/pip install openapi-python-client ruff build
.venv-sdk/bin/openapi-python-client generate \
  --path openapi/openapi.json --meta setup \
  --output-path sdk/snaptrack-api-client --overwrite
```

`.github/workflows/sdk-gen.yml` does exactly this on every release (and dry-runs
it on PRs that touch the spec), builds the sdist + wheel, and uploads them to
the GitHub Release.

Two endpoints that return raw image bytes (`GET /photos/{id}/file`,
`GET /photos/{id}/thumbnail/file`) generate with a warning — the client exposes
them but types the body as bytes.

## Using it

```python
from snap_track_api_client import Client
from snap_track_api_client.api.auth import login_auth_login_post
from snap_track_api_client.models import UserLogin

client = Client(base_url="http://localhost:8000")
token = login_auth_login_post.sync(client=client, body=UserLogin(email="a@b.com", password="…"))

from snap_track_api_client import AuthenticatedClient
from snap_track_api_client.api.photos import list_photos_photos_get

auth = AuthenticatedClient(base_url="http://localhost:8000", token=token.access_token)
page = list_photos_photos_get.sync(client=auth, limit=20)
```

Install the built wheel from a release:

```bash
pip install snap_track_api_client-1.1.0-py3-none-any.whl
```
