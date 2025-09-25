import asyncio
from pathlib import Path
from uuid import uuid4

import air
from air.responses import JSONResponse
from fastapi.responses import StreamingResponse
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from eventcloud.auth.routes import router as auth_router
from eventcloud.auth.session_backend import SessionAuthBackend
from eventcloud.event_broker import broker
from eventcloud.r2 import generate_presigned_upload_url
from eventcloud.routes.events import router as event_router
from eventcloud.routes.messages import router as message_router
from eventcloud.settings import settings
from eventcloud.utils import jinja

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


app = air.Air()

app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
app.include_router(auth_router)
app.include_router(event_router)
app.include_router(message_router)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


SESSION_SECRET = settings.session_secret

# Cookie/session tuning
COOKIE_NAME = "sessionid"
COOKIE_SECURE = False  # set True behind HTTPS
COOKIE_SAMESITE = "strict"  # 'strict' or 'none' (with Secure) if you need cross-site
COOKIE_MAX_AGE = 60 * 60 * 24 * 14  # 14 days

app.add_middleware(AuthenticationMiddleware, backend=SessionAuthBackend())

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie=COOKIE_NAME,
    same_site=COOKIE_SAMESITE,
    https_only=COOKIE_SECURE,
    max_age=COOKIE_MAX_AGE,
)


@app.get("/")
def index(request: air.Request):
    return jinja(request, name="index.html")


@app.post("/r2/presign-upload")
async def get_presigned_upload_url(request: air.Request):
    form_data = await request.json()
    extension = form_data.get("extension")
    content_type = str(form_data.get("content_type"))

    file_id = str(uuid4())
    key = f"uploads/{file_id}.{extension}"

    presigned_url = generate_presigned_upload_url(key=key, content_type=content_type)
    return JSONResponse(
        {
            "upload_url": presigned_url,
            "key": key,
        }
    )


@app.get("/events/{code}/stream")
async def event_stream(request: air.Request, code: str):
    queue = await broker.connect(code)

    async def generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield data
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            await broker.disconnect(code, queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
        },
    )


@app.get("/healthz")
def healthz():
    return JSONResponse({"ok": True})
