"""
Shared FastAPI dependencies and session-cookie handling.

Important gotcha this module works around: a dependency that receives
`response: Response` and calls response.set_cookie(...) on it only
takes effect if the route handler lets FastAPI build the final response
itself. Every route in web/routers/search.py explicitly constructs and
returns its own TemplateResponse/StreamingResponse — a DIFFERENT object
— so anything set on a dependency-injected Response is silently
discarded. Verified directly: without the fix below, the session
cookie was never actually sent, so every single request (including
"pagination" clicks immediately after a search) silently got a brand
new, empty session.

The fix: resolve the session id here (from the request's cookies, or a
new one if missing), but only ATTACH the cookie in attach_session_cookie(),
which every route calls on the actual object it returns, right before
returning it.
"""

from fastapi import Request

from web.session_store import get_session, new_session_id

SESSION_COOKIE_NAME = "ji_session"
SESSION_COOKIE_MAX_AGE = 60 * 60 * 4  # matches session_store's TTL


def get_session_state(request: Request) -> dict:
    """
    Returns this browser's session state dict (see session_store.py).
    The cookie only ever holds an opaque, meaningless-if-tampered-with
    id — it's a lookup key into server-side memory, not a security
    boundary, so it isn't cryptographically signed. There's nothing
    sensitive in the session (search results and search history only).
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME) or new_session_id()
    session = get_session(session_id)
    session["_session_id"] = session_id
    return session


def _request_is_https(request: Request) -> bool:
    """
    True once the request genuinely arrived over TLS -- checked two
    ways, not just request.url.scheme. docs/DEPLOYMENT.md is explicit
    that "no hosting platform has been chosen yet" (Render, Railway,
    Fly.io, a plain VPS, or Heroku are all named as options), and
    neither the Procfile nor the Dockerfile passes uvicorn
    --proxy-headers/--forwarded-allow-ips -- so request.url.scheme
    alone would only read "https" if TLS terminated INSIDE this same
    uvicorn process, which none of those options do (they all put a
    TLS-terminating proxy/load balancer in front and forward plain
    HTTP to the app). Reading X-Forwarded-Proto ourselves works
    regardless of uvicorn's own proxy-trust configuration -- virtually
    every such proxy sets it, and the only thing a forged header could
    do here is cause a client bypassing the proxy entirely to get a
    Secure cookie it can't send back (the same "session doesn't
    persist" symptom this function exists to fix, narrowed to that
    bypass case) -- not a security hole, since the cookie itself holds
    no secret (see get_session_state()'s own docstring).
    """
    if request.url.scheme == "https":
        return True
    return request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower() == "https"


def attach_session_cookie(response, session: dict, request: Request):
    """
    Call on whatever response object a route is about to return. Always
    re-sets the cookie (even for an already-existing session) — this is
    idempotent and has the nice side effect of refreshing the cookie's
    expiry on every visit, so an active user's session doesn't expire
    out from under them.

    `secure` follows the request's own scheme rather than being
    hardcoded True: a browser silently refuses to ever send a Secure
    cookie back over plain HTTP, and this app's own documented local
    dev setup (`uvicorn web.main:app --reload` -> http://127.0.0.1:8000)
    is plain HTTP -- hardcoding True there meant the cookie was set but
    never returned, so every request got a brand-new, empty session
    (the exact failure mode this module's docstring already describes
    fixing once, for a different reason). See _request_is_https() for
    why that check isn't simply `request.url.scheme == "https"`.
    """
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session["_session_id"],
        httponly=True,
        samesite="lax",
        secure=_request_is_https(request),
        max_age=SESSION_COOKIE_MAX_AGE,
    )
    return response
