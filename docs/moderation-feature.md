# Feature: photo flagging & moderation (v1.1.0)

Built test-first in Phase 3.

## Endpoints

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| `POST` | `/photos/{photo_id}/flag` | photo **owner** | Raise a flag against a photo |
| `GET` | `/moderation/queue` | **admin** | List unresolved flags, newest first, paginated |
| `POST` | `/moderation/{flag_id}/decision` | **admin** | Resolve a flag: `dismiss` or `action` (remove the photo) |

RBAC, deliberately asymmetric to exercise both directions:

- **Flagging requires ownership.** A non-owner gets `404` — the same "no
  existence oracle" rule the rest of the photo routes follow. (Product-wise this
  models "ask for your own photo to be re-reviewed"; the point here is the
  owner-only gate.)
- **Moderating requires `is_admin`.** A non-admin authenticated user gets `403`.

## Data model

```
flags                              moderation_actions   (immutable audit)
  id                                 id
  photo_id      FK photos ON DELETE CASCADE     photo_id     plain int  (no FK)
  reporter_id   FK users                        flag_id      plain int  (no FK)
  reason        enum                            moderator_id FK users
  note          text?                           decision     enum  (dismiss|action)
  status        enum (pending|resolved)         note         text?
  resolution    enum? (dismissed|actioned)      created_at
  resolved_by_id FK users?
  resolved_at   timestamptz?
  created_at    timestamptz
  UNIQUE (photo_id, reporter_id)   ← duplicate protection
```

`reason ∈ {spam, nudity, violence, copyright, other}`.

**Why a separate audit table with no FK to `photos`:** an `action` decision
deletes the photo, which cascade-deletes its `flags`. `moderation_actions` holds
plain integer references so the record of *"a moderator removed photo N on date
D"* survives the content it removed.

## Decision semantics (`POST /moderation/{flag_id}/decision`)

Body: `{ "decision": "dismiss" | "action", "note": "<optional>" }`

1. Flag must exist (`404`) and be `pending` (`409` if already resolved).
2. Write a `moderation_actions` row (the audit).
3. `dismiss` → this flag: `status=resolved`, `resolution=dismissed`.
4. `action` → mark **every** pending flag on that photo `resolved / actioned`,
   then delete the photo + its blobs (cascades the flag rows away; the audit
   row remains). One bad photo, one delete, all its flags closed.
5. Response: the resolved flag (`dismiss`) or the `moderation_actions` row
   (`action`).

## Caching

`GET /photos/{id}` already caches the serialised photo. An `action` decision
deletes the photo, and `photo_service.delete_photo` already invalidates
`photo:{id}` — no new cache rules needed. The moderation queue is not cached
(admin-only, low traffic, must be fresh).

## Versioning

Additive only — new paths, new schemas, one new `reason`/`decision` enum, no
changes to existing operations. `oasdiff` reports **no breaking changes**
(`docs/openapi-diff-v1.1.0.md`), so `v1.0.0 → v1.1.0` is the correct semver bump.
