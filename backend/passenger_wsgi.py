"""Entry point for cPanel / CloudLinux "Setup Python App" (Phusion Passenger).

Passenger speaks WSGI; FastAPI is ASGI, so a2wsgi bridges the two. The ASGI
lifespan does not run here, so the minute-by-minute housekeeping is a cron job
(`python -m app.cli housekeeping`) - see docs/DEPLOY-CPANEL.md.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from a2wsgi import ASGIMiddleware  # noqa: E402

from app.main import app as asgi_app  # noqa: E402

application = ASGIMiddleware(asgi_app)
