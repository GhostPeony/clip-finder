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
    """Stripe API 2025-03-31.basil+ shape: the billing period lives on items."""
    return {
        "id": subscription_id,
        "object": "subscription",
        "customer": "cus_test",
        "status": "active",
        "cancel_at_period_end": False,
        "metadata": {"user_id": "user-1"},
        "items": {
            "data": [
                {
                    "current_period_start": 1780272000,
                    "current_period_end": 1782864000,
                    "price": {
                        "id": f"price_{lookup_key}",
                        "lookup_key": lookup_key,
                    },
                }
            ]
        },
    }


def fake_subscription_legacy(subscription_id="sub_test", lookup_key="memexai_plus_monthly_v1"):
    """Pre-basil shape: the billing period sits on the subscription itself."""
    subscription = fake_subscription(subscription_id, lookup_key)
    item = subscription["items"]["data"][0]
    del item["current_period_start"]
    del item["current_period_end"]
    subscription["current_period_start"] = 1780272000
    subscription["current_period_end"] = 1782864000
    return subscription


PERIOD_START_ISO = "2026-06-01T00:00:00+00:00"
PERIOD_END_ISO = "2026-07-01T00:00:00+00:00"


def test_apply_subscription_state_reads_period_from_items():
    supabase = Supabase()

    billing.apply_subscription_state(supabase, fake_subscription())

    profile = supabase.tables["billing_profiles"][0]
    assert profile["current_period_start"] == PERIOD_START_ISO
    assert profile["current_period_end"] == PERIOD_END_ISO


def test_apply_subscription_state_reads_legacy_top_level_period():
    supabase = Supabase()

    billing.apply_subscription_state(supabase, fake_subscription_legacy())

    profile = supabase.tables["billing_profiles"][0]
    assert profile["current_period_start"] == PERIOD_START_ISO
    assert profile["current_period_end"] == PERIOD_END_ISO


def test_invoice_event_resolves_subscription_via_parent_details(monkeypatch):
    supabase = Supabase()
    monkeypatch.setattr(billing, "stripe", FakeStripe)
    monkeypatch.setattr(billing, "get_stripe_secret_key", lambda: "sk_test")
    event = {
        "id": "evt_inv_parent",
        "type": "invoice.payment_succeeded",
        "data": {
            "object": {
                "object": "invoice",
                "customer": "cus_test",
                "parent": {"subscription_details": {"subscription": "sub_test"}},
            }
        },
    }

    result = billing.process_stripe_event(supabase, event)

    assert result["duplicate"] is False
    profile = supabase.tables["billing_profiles"][0]
    assert profile["billing_status"] == "active"
    assert profile["current_period_start"] == PERIOD_START_ISO
    events = supabase.tables["billing_events"]
    assert events[0]["stripe_subscription_id"] == "sub_test"


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
        lambda supabase, user, lookup_key, promo_code=None: {
            "url": f"https://checkout.test/{lookup_key}"
        },
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


def test_get_promo_trial_codes_parses_and_skips_malformed(monkeypatch):
    from backend import config

    monkeypatch.setenv(
        "PROMO_TRIAL_CODES",
        "ProductHunt:plus:14, bad-entry, foo:teams:9, bar:pro:abc, zero:pro:0, launch:pro:7",
    )

    assert config.get_promo_trial_codes() == {
        "producthunt": {"code": "producthunt", "plan_key": "plus", "trial_days": 14},
        "launch": {"code": "launch", "plan_key": "pro", "trial_days": 7},
    }


def test_create_checkout_session_with_promo_adds_card_optional_trial(monkeypatch):
    supabase = Supabase()
    FakeStripe.created_customers = []
    FakeStripe.checkout_sessions = []
    FakeStripe.missing_customers = set()
    monkeypatch.setattr(billing, "stripe", FakeStripe)
    monkeypatch.setattr(billing, "get_stripe_secret_key", lambda: "sk_test")
    monkeypatch.setenv("PROMO_TRIAL_CODES", "producthunt:plus:14")

    billing.create_checkout_session(
        supabase,
        {"sub": "user-1", "email": "cade@example.com"},
        "memexai_plus_monthly_v1",
        "ProductHunt",
    )

    session = FakeStripe.checkout_sessions[0]
    assert session["payment_method_collection"] == "if_required"
    assert session["subscription_data"]["trial_period_days"] == 14
    assert session["subscription_data"]["trial_settings"] == {
        "end_behavior": {"missing_payment_method": "cancel"}
    }
    assert session["metadata"]["promo_code"] == "producthunt"
    assert session["subscription_data"]["metadata"]["promo_code"] == "producthunt"


def test_create_checkout_session_without_promo_has_no_trial(monkeypatch):
    supabase = Supabase()
    FakeStripe.created_customers = []
    FakeStripe.checkout_sessions = []
    FakeStripe.missing_customers = set()
    monkeypatch.setattr(billing, "stripe", FakeStripe)
    monkeypatch.setattr(billing, "get_stripe_secret_key", lambda: "sk_test")

    billing.create_checkout_session(
        supabase,
        {"sub": "user-1", "email": "cade@example.com"},
        "memexai_plus_monthly_v1",
    )

    session = FakeStripe.checkout_sessions[0]
    assert "payment_method_collection" not in session
    assert "trial_period_days" not in session["subscription_data"]


def test_create_checkout_session_rejects_unknown_promo_code(monkeypatch):
    monkeypatch.setenv("PROMO_TRIAL_CODES", "producthunt:plus:14")

    try:
        billing.create_checkout_session(
            Supabase(),
            {"sub": "user-1"},
            "memexai_plus_monthly_v1",
            "notacode",
        )
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("unknown promo code should fail")


def test_create_checkout_session_rejects_promo_plan_mismatch(monkeypatch):
    monkeypatch.setenv("PROMO_TRIAL_CODES", "producthunt:plus:14")

    try:
        billing.create_checkout_session(
            Supabase(),
            {"sub": "user-1"},
            "memexai_pro_monthly_v1",
            "producthunt",
        )
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "Plus" in exc.detail
    else:
        raise AssertionError("plan mismatch should fail")


def test_create_checkout_session_rejects_repeat_promo_redemption(monkeypatch):
    monkeypatch.setenv("PROMO_TRIAL_CODES", "producthunt:plus:14")
    supabase = Supabase(
        {
            "billing_profiles": [
                {
                    "user_id": "user-1",
                    "plan_key": "free",
                    "billing_status": "free",
                    "promo_trial_redeemed_at": "2026-06-20T00:00:00+00:00",
                }
            ]
        }
    )

    try:
        billing.create_checkout_session(
            supabase,
            {"sub": "user-1"},
            "memexai_plus_monthly_v1",
            "producthunt",
        )
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("repeat redemption should fail")


def test_create_checkout_session_rejects_promo_with_prior_subscription(monkeypatch):
    monkeypatch.setenv("PROMO_TRIAL_CODES", "producthunt:plus:14")
    supabase = Supabase(
        {
            "billing_profiles": [
                {
                    "user_id": "user-1",
                    "plan_key": "free",
                    "billing_status": "canceled",
                    "stripe_subscription_id": "sub_prior",
                }
            ]
        }
    )

    try:
        billing.create_checkout_session(
            supabase,
            {"sub": "user-1"},
            "memexai_plus_monthly_v1",
            "producthunt",
        )
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("prior subscription should fail")


def test_checkout_completed_with_promo_stamps_redemption(monkeypatch):
    supabase = Supabase()
    monkeypatch.setattr(billing, "stripe", FakeStripe)
    monkeypatch.setattr(billing, "get_stripe_secret_key", lambda: "sk_test")
    event = {
        "id": "evt_promo",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "object": "checkout.session",
                "customer": "cus_test",
                "client_reference_id": "user-1",
                "subscription": "sub_test",
                "metadata": {
                    "user_id": "user-1",
                    "lookup_key": "memexai_plus_monthly_v1",
                    "promo_code": "producthunt",
                },
            }
        },
    }

    billing.process_stripe_event(supabase, event)

    profile = supabase.tables["billing_profiles"][0]
    assert profile["promo_trial_code"] == "producthunt"
    assert profile["promo_trial_redeemed_at"]
    assert profile["plan_key"] == "plus"
    assert profile["current_period_start"] == PERIOD_START_ISO


def test_billing_promo_endpoint_describes_offer(monkeypatch):
    monkeypatch.setattr(server, "is_supabase_mode", lambda: True)
    monkeypatch.setenv("PROMO_TRIAL_CODES", "producthunt:plus:14")

    client = TestClient(server.app)
    response = client.get("/api/billing/promo/PRODUCTHUNT")
    missing = client.get("/api/billing/promo/notacode")

    assert response.status_code == 200
    assert response.json() == {
        "code": "producthunt",
        "planKey": "plus",
        "trialDays": 14,
        "lookupKey": "memexai_plus_monthly_v1",
    }
    assert missing.status_code == 404
