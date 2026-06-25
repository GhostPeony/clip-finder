import json

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import billing, server


class Result:
    def __init__(self, data=None):
        self.data = data


class Query:
    def __init__(self, supabase, table_name):
        self.supabase = supabase
        self.table_name = table_name
        self.action = "select"
        self.payload = None
        self.filters = []
        self.conflict_keys = []

    def select(self, *_args, **_kwargs):
        self.action = "select"
        return self

    def insert(self, payload):
        self.action = "insert"
        self.payload = payload
        return self

    def update(self, payload):
        self.action = "update"
        self.payload = payload
        return self

    def upsert(self, payload, on_conflict=None):
        self.action = "upsert"
        self.payload = payload
        self.conflict_keys = [key.strip() for key in (on_conflict or "").split(",") if key]
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def maybe_single(self):
        return self

    def single(self):
        return self

    def execute(self):
        rows = self.supabase.tables.setdefault(self.table_name, [])
        if self.action == "insert":
            rows.append(dict(self.payload))
            self.supabase.inserts.append((self.table_name, dict(self.payload)))
            return Result(self.payload)
        if self.action == "update":
            updated = []
            for row in rows:
                if self._matches(row):
                    row.update(self.payload)
                    updated.append(dict(row))
            self.supabase.updates.append((self.table_name, dict(self.payload), self.filters))
            return Result(updated)
        if self.action == "upsert":
            existing = None
            if self.conflict_keys:
                for row in rows:
                    if all(row.get(key) == self.payload.get(key) for key in self.conflict_keys):
                        existing = row
                        break
            if existing is None:
                rows.append(dict(self.payload))
                result = self.payload
            else:
                existing.update(self.payload)
                result = existing
            self.supabase.upserts.append((self.table_name, dict(self.payload), self.conflict_keys))
            return Result(result)
        matched = [dict(row) for row in rows if self._matches(row)]
        return Result(matched[0] if matched else None)

    def _matches(self, row):
        return all(row.get(column) == value for column, value in self.filters)


class Supabase:
    def __init__(self, tables=None):
        self.tables = tables or {}
        self.inserts = []
        self.updates = []
        self.upserts = []

    def table(self, table_name):
        return Query(self, table_name)


class FakeStripe:
    api_key = None
    created_customers = []
    checkout_sessions = []
    missing_customers = set()
    portal_sessions = []

    class Price:
        @staticmethod
        def list(lookup_keys, active=True, limit=1):
            return {"data": [{"id": f"price_{lookup_keys[0]}", "lookup_key": lookup_keys[0]}]}

    class Customer:
        @staticmethod
        def create(email=None, metadata=None):
            customer = {
                "id": f"cus_test_{len(FakeStripe.created_customers) + 1}",
                "email": email,
                "metadata": metadata or {},
            }
            FakeStripe.created_customers.append(customer)
            return customer

        @staticmethod
        def retrieve(customer_id):
            if customer_id in FakeStripe.missing_customers:
                raise Exception(f"No such customer: '{customer_id}'")
            return {"id": customer_id}

    class checkout:
        class Session:
            @staticmethod
            def create(**kwargs):
                FakeStripe.checkout_sessions.append(kwargs)
                return {"id": "cs_test", "url": "https://checkout.stripe.com/test"}

    class billing_portal:
        class Session:
            @staticmethod
            def create(**kwargs):
                FakeStripe.portal_sessions.append(kwargs)
                return {"id": "bps_test", "url": "https://billing.stripe.com/test"}

    class Webhook:
        @staticmethod
        def construct_event(payload, signature, secret):
            if signature == "bad":
                raise ValueError("bad signature")
            return json.loads(payload.decode("utf-8"))

    class Subscription:
        @staticmethod
        def retrieve(subscription_id, expand=None):
            return fake_subscription(subscription_id=subscription_id)


def fake_subscription(subscription_id="sub_test", lookup_key="memexai_plus_monthly_v1"):
    return {
        "id": subscription_id,
        "object": "subscription",
        "customer": "cus_test",
        "status": "active",
        "current_period_start": 1780272000,
        "current_period_end": 1782864000,
        "cancel_at_period_end": False,
        "metadata": {"user_id": "user-1"},
        "items": {
            "data": [
                {
                    "price": {
                        "id": f"price_{lookup_key}",
                        "lookup_key": lookup_key,
                    }
                }
            ]
        },
    }


def test_resolve_user_entitlements_returns_active_pro_limits():
    supabase = Supabase(
        {
            "billing_profiles": [
                {
                    "user_id": "user-1",
                    "plan_key": "pro",
                    "billing_status": "active",
                    "current_period_start": "2026-06-01T00:00:00+00:00",
                    "current_period_end": "2026-07-01T00:00:00+00:00",
                    "usage_pack_seconds_balance": 0,
                }
            ],
            "billing_period_usage": [
                {
                    "user_id": "user-1",
                    "period_start": "2026-06-01T00:00:00+00:00",
                    "period_end": "2026-07-01T00:00:00+00:00",
                    "retrieval_calls": 12,
                    "indexed_transcript_seconds": 3600,
                }
            ],
        }
    )

    resolved = billing.resolve_user_entitlements(
        supabase,
        "user-1",
        {"free_searches_this_month": 0, "free_indexed_seconds_total": 0},
    )

    assert resolved["entitlements"]["planKey"] == "pro"
    assert resolved["entitlements"]["monthlyIndexedTranscriptSeconds"] == 720000
    assert resolved["entitlements"]["maxSearchResults"] == 20
    assert resolved["usage"]["retrievalCalls"] == 12


def test_create_checkout_session_uses_approved_lookup_key(monkeypatch):
    supabase = Supabase()
    FakeStripe.created_customers = []
    FakeStripe.checkout_sessions = []
    FakeStripe.missing_customers = set()
    monkeypatch.setattr(billing, "stripe", FakeStripe)
    monkeypatch.setattr(billing, "get_stripe_secret_key", lambda: "sk_test")

    result = billing.create_checkout_session(
        supabase,
        {"sub": "user-1", "email": "cade@example.com"},
        "memexai_plus_monthly_v1",
    )

    assert result["url"] == "https://checkout.stripe.com/test"
    assert FakeStripe.created_customers[0]["metadata"] == {"user_id": "user-1"}
    assert FakeStripe.checkout_sessions[0]["mode"] == "subscription"
    assert FakeStripe.checkout_sessions[0]["line_items"][0]["price"].startswith("price_")
    assert supabase.tables["billing_profiles"][0]["stripe_customer_id"] == "cus_test_1"


def test_create_checkout_session_replaces_missing_stored_customer(monkeypatch):
    supabase = Supabase(
        {
            "billing_profiles": [
                {
                    "user_id": "user-1",
                    "stripe_customer_id": "cus_old_sandbox",
                    "stripe_subscription_id": "sub_old_sandbox",
                    "plan_key": "plus",
                    "billing_status": "active",
                }
            ]
        }
    )
    FakeStripe.created_customers = []
    FakeStripe.checkout_sessions = []
    FakeStripe.missing_customers = {"cus_old_sandbox"}
    monkeypatch.setattr(billing, "stripe", FakeStripe)
    monkeypatch.setattr(billing, "get_stripe_secret_key", lambda: "sk_live")

    result = billing.create_checkout_session(
        supabase,
        {"sub": "user-1", "email": "cade@example.com"},
        "memexai_plus_monthly_v1",
    )

    profile = supabase.tables["billing_profiles"][0]
    assert result["url"] == "https://checkout.stripe.com/test"
    assert profile["stripe_customer_id"] == "cus_test_1"
    assert profile["stripe_subscription_id"] is None
    assert profile["plan_key"] == "free"
    assert profile["billing_status"] == "free"
    assert FakeStripe.checkout_sessions[0]["customer"] == "cus_test_1"


def test_process_subscription_event_is_idempotent(monkeypatch):
    supabase = Supabase()
    monkeypatch.setattr(billing, "stripe", FakeStripe)
    event = {
        "id": "evt_1",
        "type": "customer.subscription.updated",
        "data": {"object": fake_subscription(lookup_key="memexai_pro_annual_v1")},
    }

    first = billing.process_stripe_event(supabase, event)
    duplicate = billing.process_stripe_event(supabase, event)

    assert first["duplicate"] is False
    assert duplicate["duplicate"] is True
    profile = supabase.tables["billing_profiles"][0]
    assert profile["plan_key"] == "pro"
    assert profile["billing_status"] == "active"
    assert len(supabase.tables["billing_events"]) == 1


def test_construct_stripe_event_rejects_invalid_signature(monkeypatch):
    monkeypatch.setattr(billing, "stripe", FakeStripe)
    monkeypatch.setattr(billing, "get_stripe_secret_key", lambda: "sk_test")
    monkeypatch.setattr(billing, "get_stripe_webhook_secret", lambda: "whsec_test")

    try:
        billing.construct_stripe_event(b"{}", "bad")
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("bad signature should fail")


def test_billing_checkout_endpoint_delegates_to_checkout_creator(monkeypatch):
    app = server.app
    app.dependency_overrides[server.get_request_user] = lambda: {
        "sub": "user-1",
        "email": "cade@example.com",
    }
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(server, "get_supabase", lambda: object())
    monkeypatch.setattr(
        server,
        "create_checkout_session",
        lambda supabase, user, lookup_key: {"url": f"https://checkout.test/{lookup_key}"},
    )

    try:
        response = TestClient(app).post(
            "/api/billing/checkout",
            json={"lookupKey": "memexai_plus_monthly_v1"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["url"] == "https://checkout.test/memexai_plus_monthly_v1"
