from __future__ import annotations

import os
import asyncio
from collections import OrderedDict, deque
from pathlib import Path
from time import monotonic

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from .core import find_shared
from .models import RecommendationRequest, SearchRequest
from .qloo import QlooError
from .gateway import live_client
from .sample import SyntheticTransport

app = FastAPI(title="BookBridge", version="0.1.0", docs_url="/api/docs", redoc_url=None)
STATIC = Path(__file__).parent / "static"
hits: OrderedDict[str, deque[float]] = OrderedDict()
global_hits: deque[float] = deque()

def transport(mode: str):
    if mode == "sample": return SyntheticTransport()
    return live_client()

class RequestGuard:
    def __init__(self, app): self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            return await self.app(scope, receive, send)
        now, client_id = monotonic(), (scope.get("client") or ("unknown",))[0]
        while global_hits and global_hits[0] < now - 60: global_hits.popleft()
        if len(global_hits) >= 300:
            return await JSONResponse({"detail": "Service request limit reached; try again shortly."}, 429)(scope, receive, send)
        global_hits.append(now)
        if client_id not in hits:
            if len(hits) >= 512: hits.popitem(last=False)
            hits[client_id] = deque()
        hits.move_to_end(client_id)
        bucket = hits[client_id]
        while bucket and bucket[0] < now - 60: bucket.popleft()
        if len(bucket) >= 30:
            return await JSONResponse({"detail": "Request limit reached; try again shortly."}, 429)(scope, receive, send)
        bucket.append(now)
        chunks, total = [], 0
        try:
            async with asyncio.timeout(10):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect": return
                    chunk = message.get("body", b"")
                    total += len(chunk)
                    if total > 16384:
                        return await JSONResponse({"detail": "Request body too large."}, 413)(scope, receive, send)
                    chunks.append(chunk)
                    if not message.get("more_body", False): break
        except TimeoutError:
            return await JSONResponse({"detail": "Request body timed out."}, 408)(scope, receive, send)
        consumed = False
        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()
        await self.app(scope, replay, send)

app.add_middleware(RequestGuard)

@app.exception_handler(RequestValidationError)
async def invalid_request(_, exc):
    return JSONResponse({"detail": "Invalid request. Check anchor IDs, types and limits."}, status_code=422)

@app.exception_handler(QlooError)
async def qloo_error(_, exc: QlooError):
    return JSONResponse({"detail": str(exc)}, status_code=503)

@app.get("/")
async def index(): return FileResponse(STATIC / "index.html")

@app.get("/styles.css")
async def styles(): return FileResponse(STATIC / "styles.css", media_type="text/css")

@app.get("/app.js")
async def script(): return FileResponse(STATIC / "app.js", media_type="application/javascript")

@app.get("/api/status")
async def status(): return {"live_available": bool(os.environ.get("QLOO_API_KEY")), "sample_available": True}

@app.post("/api/search")
async def search(body: SearchRequest):
    rows = await transport(body.mode).search(body.query, body.kind)
    return {"mode": body.mode, "results": [{"id": e.id, "name": e.name, "kind": e.kind} for e in rows]}

@app.post("/api/shared")
async def shared(body: RecommendationRequest):
    result = await find_shared(transport(body.mode), body.members, body.top_k)
    return {"mode": body.mode, **result}
