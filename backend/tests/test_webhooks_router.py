"""Smoke tests for the Stripe webhook router mount path.

Regression: 2026-04-13 — F&M Accesorios paid via the public payment link but
never received the CFDI email because the Stripe webhook was misrouted to the
Eva backend. The fix points Stripe at `https://erp.goeva.ai/api/v1/webhooks/stripe`,
which only works because `eva-erp/frontend/next.config.ts` proxies `/api/v1/*`
to the backend. These tests assert the webhook handler is mounted at that path
on the FastAPI app (not at the legacy root `/webhooks/stripe`).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src.webhooks.router import router as webhooks_router


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(webhooks_router, prefix="/api/v1")
    return app


def test_stripe_webhook_mounted_under_api_v1():
    """The Stripe webhook must be reachable at /api/v1/webhooks/stripe.

    Required so Stripe can POST through the Vercel proxy at
    `https://erp.goeva.ai/api/v1/webhooks/stripe`.
    """
    app = _build_app()
    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
    assert "/api/v1/webhooks/stripe" in paths
    assert "/webhooks/stripe" not in paths  # legacy mount removed


def test_stripe_webhook_only_accepts_post():
    app = _build_app()
    client = TestClient(app)
    # GET should 405 (method not allowed) — the route exists, just rejects GET.
    response = client.get("/api/v1/webhooks/stripe")
    assert response.status_code == 405


def test_stripe_webhook_rejects_missing_signature(monkeypatch):
    """Without a configured secret the handler must return 503; never 200."""
    from src.common.config import settings

    monkeypatch.setattr(settings, "stripe_webhook_secret_erp", "")
    app = _build_app()
    client = TestClient(app)
    response = client.post("/api/v1/webhooks/stripe", json={})
    assert response.status_code == 503


def test_webhook_router_uses_configured_session_not_fresh_sessionmaker():
    """Regression: don't create fresh sessionmakers per request.

    The original bug (fmaccesorios 2026-04-13): handler did
    `async with async_sessionmaker(engine)() as db: ...` which builds a NEW
    sessionmaker with default `expire_on_commit=True`. After `db.commit()`,
    every ORM attribute is expired; the next access (e.g. logging
    `empresa.name` on the success path) triggers a lazy reload outside the
    async greenlet → MissingGreenlet, success log line crashes, and the
    monitoring helper that runs in the except block sees `empresa` in a
    broken state too.

    The fix imports the configured `async_session` (expire_on_commit=False)
    from src.common.database. This test asserts the wrong import doesn't
    sneak back in.
    """
    import inspect
    from src import webhooks

    source = inspect.getsource(webhooks.router)
    assert "from src.common.database import async_session" in source, (
        "webhooks.router must import the configured async_session "
        "(not async_sessionmaker) — see MissingGreenlet regression on 2026-04-13"
    )
    assert "async_sessionmaker(engine)()" not in source, (
        "webhooks.router must NOT build fresh sessionmakers per request — "
        "those default to expire_on_commit=True and break ORM access after commit"
    )
