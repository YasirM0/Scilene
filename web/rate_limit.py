"""
Rate limiting (#146 — Security Assessment).

Centralised here rather than in web/main.py so web/routers/search.py
can import the `limiter` instance without creating a circular import
(main.py imports routers, routers can't import back from main.py).

Key function uses get_remote_address, which reads X-Forwarded-For first
(correct for Heroku / reverse-proxy deployments) before falling back to
the direct TCP client address. Limits are per IP; in-memory storage is
appropriate for single-process deployments (the default Heroku/Railway
setup) and degrades gracefully under multi-worker setups (each worker
maintains its own counter, so the effective limit is relaxed by a factor
equal to the worker count -- still blocks runaway scripted abuse).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])
