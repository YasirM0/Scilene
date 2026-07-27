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


def attach_session_cookie(response, session: dict):
    """
    Call on whatever response object a route is about to return. Always
    re-sets the cookie (even for an already-existing session) — this is
    idempotent and has the nice side effect of refreshing the cookie's
    expiry on every visit, so an active user's session doesn't expire
    out from under them.
    """
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session["_session_id"],
        httponly=True,
        samesite="lax",
        max_age=SESSION_COOKIE_MAX_AGE,
    )
    return response
