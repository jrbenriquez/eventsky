from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import RedirectResponse

protected_routes = [
    "/event/"
    "/event/new/"
]
class AuthRequiredMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path in protected_routes:
            uid = request.session.get("uid")
            if not uid:
                return RedirectResponse(url="/auth/login", status_code=303)
        return await call_next(request)

