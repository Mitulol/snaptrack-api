# OpenAPI diff — v1.0.0 → v1.1.0-rc1

Generated with [oasdiff](https://github.com/oasdiff/oasdiff):

```
$ oasdiff breaking openapi/openapi-v1.0.0.json openapi/openapi-v1.1.0-rc1.json
No breaking changes to report, but the specs are different.
Run 'oasdiff diff' to see structural differences.

$ oasdiff changelog openapi/openapi-v1.0.0.json openapi/openapi-v1.1.0-rc1.json
3 changes: 0 error, 0 warning, 3 info
info	[endpoint-added] at /specs/openapi-v1.1.0-rc1.json
	in API GET /moderation/queue
		endpoint added

info	[endpoint-added] at /specs/openapi-v1.1.0-rc1.json
	in API POST /moderation/{flag_id}/decision
		endpoint added

info	[endpoint-added] at /specs/openapi-v1.1.0-rc1.json
	in API POST /photos/{photo_id}/flag
		endpoint added


```

## Verdict: minor bump is correct

`oasdiff breaking` reports **no breaking changes**. The only differences are
**three added endpoints** (`POST /photos/{photo_id}/flag`, `GET /moderation/queue`,
`POST /moderation/{flag_id}/decision`) plus their new schemas and one new value
each in the `reason` / `decision` enums — all additive.

Per SemVer, backward-compatible additions are a **minor** version bump:
`1.0.0 → 1.1.0`. The `-rc1` pre-release tag is dropped when the feature ships
(Phase 4 tags `v1.1.0`).

The check is enforced in CI (`contract-test.yml`): the job fails if
`oasdiff breaking` finds anything between the last released spec and `HEAD`.
