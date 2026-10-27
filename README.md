# BookBridge

BookBridge finds books that can bridge two readers' explicit cultural tastes. It is an original FastAPI application and official MCP SDK 2 stdio tool server. Qloo is essential to live results: each member generates 20 book candidates, their union (maximum 40) is rescored separately for both members, and shared books use deterministic rank-based maximin ordering. Missing evidence remains unknown.

The included **invented sample** uses the exact same ranking pipeline and no network. It is not a live Qloo integration, and live failures never fall back to it.

Public preview: https://bookbridge.agencytech.app/ — the invented sample is available; live Qloo access is pending as of October 27, 2026. Deployment templates and rollback steps are in [deploy/README.md](deploy/README.md).

## Run locally

Python 3.12 is recommended.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export QLOO_API_KEY='issued-key'  # omit to use only the explicit sample mode
uvicorn bookbridge.app:app --host 127.0.0.1 --port 7860 --no-access-log --no-proxy-headers
```

Only `QLOO_API_KEY` is read. It is sent as `X-Api-Key` solely to the fixed `https://hackathon.api.qloo.com` origin. Redirects are refused, responses and timeouts are bounded, and the key is never sent to the browser or logged by this code.

## MCP

With `mcp==2.3.0` installed and `QLOO_API_KEY` set:

```bash
python -m bookbridge.mcp_server
```

The read-only tools are `search_taste_anchors` and `find_shared_read`. They use the same live adapter and core; there is deliberately no automatic sample behavior on the MCP path.

## Test

```bash
pytest -q
```

Tests use invented fixtures and `httpx.MockTransport`; they make no live API/model calls and store no Qloo responses. Before claiming live success, validate both `/search` and `/v2/insights` response shapes with an issued key outside the repository.

## License

Original code and synthetic examples are MIT licensed. See `LICENSE`.

Privacy and limits: a single process caches at most256 upstream responses privately in RAM for600seconds, with400 actual upstream attempts per rolling24hours. Run one worker/instance to preserve that limit. API requests allow30/client/minute and300 globally/minute, a16KiB body and10second body-receive deadline. Do not enable access logs or trust arbitrary proxy headers. When using an owned trusted reverse proxy, configure forwarding explicitly. Restarting the process resets its cache and budget. MCP and web servers have separate process budgets; do not run both as public services under one key.

Upstream misses are intentionally serialized in this small single-process demo. Cache hits are reused; an8second complete network deadline and20second cache/queue deadline fail safely under contention. The four-call recommendation pipeline can take roughly32seconds in the worst case without contention. This is a low-volume prototype, not a scalable service. Stretch specifically means an evidenced, uneven-rank alternative; equal-rank books remain eligible for the shared shelf.
