from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

protected_routes = [
    "/events/",
    "/events/new/",
]


class AuthRequiredMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path in protected_routes:
            uid = request.session.get("uid")
            if not uid:
                return RedirectResponse(url="/auth/login", status_code=303)
        return await call_next(request)
