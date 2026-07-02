"""Stripe billing and hosted plan entitlement helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

try:
    import stripe
except ImportError:  # pragma: no cover - local dev can run without Stripe installed.
    stripe = None

try:
    from .config import (
        get_free_indexed_transcript_seconds_total,
        get_free_indexed_videos_total,
        get_free_max_active_ingestion_jobs,
        get_free_max_import_videos,
        get_free_max_search_results,
        get_free_searches_per_month,
        get_promo_trial_codes,
        get_stripe_cancel_url,
        get_stripe_portal_return_url,
        get_stripe_price_id_overrides,
        get_stripe_price_lookup_keys,
        get_stripe_secret_key,
        get_stripe_success_url,
        get_stripe_webhook_secret,
    )
except ImportError:
    from config import (
        get_free_indexed_transcript_seconds_total,
        get_free_indexed_videos_total,
        get_free_max_active_ingestion_jobs,
        get_free_max_import_videos,
        get_free_max_search_results,
        get_free_searches_per_month,
        get_promo_trial_codes,
        get_stripe_cancel_url,
        get_stripe_portal_return_url,
        get_stripe_price_id_overrides,
        get_stripe_price_lookup_keys,
        get_stripe_secret_key,
        get_stripe_success_url,
        get_stripe_webhook_secret,
    )


BILLING_PROFILE_TABLE = "billing_profiles"
BILLING_EVENTS_TABLE = "billing_events"
BILLING_PERIOD_USAGE_TABLE = "billing_period_usage"

ACTIVE_BILLING_STATUSES = frozenset({"active", "trialing"})
KNOWN_BILLING_STATUSES = frozenset(
    {
        "free",
        "trialing",
        "active",
        "past_due",
        "canceled",
        "incomplete",
        "incomplete_expired",
        "unpaid",
    }
)
PLAN_KEYS = frozenset({"free", "plus", "pro"})
SECONDS_PER_HOUR = 3600


@dataclass(frozen=True)
class PlanEntitlements:
    planKey: str
    billingStatus: str
    monthlyIndexedTranscriptSeconds: int
    libraryTranscriptSeconds: int
    indexedVideosTotal: int
    monthlyRetrievalCalls: int
    maxImportVideos: int
    maxSearchResults: int
    maxActiveIngestionJobs: int
    deepTranscriptSeconds: int
    priorityQueue: bool
    usagePackSecondsBalance: int = 0
    periodStart: str | None = None
    periodEnd: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _stripe_client():
    if stripe is None:
        raise HTTPException(
            status_code=500,
            detail="Stripe SDK is not installed. Install requirements.txt before enabling billing.",
        )
    secret_key = get_stripe_secret_key()
    if not secret_key:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY is not configured")
    stripe.api_key = secret_key
    return stripe


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _stripe_id(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value
    return _get(value, "id")


def _result_data(result: Any) -> Any:
    return getattr(result, "data", None)


def _rows(result: Any) -> list[dict]:
    data = _result_data(result)
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def _single_row(result: Any) -> dict | None:
    data = _result_data(result)
    if isinstance(data, list):
        return data[0] if data else None
    if isinstance(data, dict):
        return data
    return None


def _iso_from_timestamp(timestamp: Any) -> str | None:
    if timestamp in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return str(timestamp)


def _current_month_period() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start.isoformat(), end.isoformat()


def allowed_subscription_lookup_keys() -> set[str]:
    return {value for value in get_stripe_price_lookup_keys().values() if value}


def plan_key_for_lookup_key(lookup_key: str | None) -> str:
    lookup_keys = get_stripe_price_lookup_keys()
    if lookup_key in {lookup_keys["plus_monthly"], lookup_keys["plus_annual"]}:
        return "plus"
    if lookup_key in {lookup_keys["pro_monthly"], lookup_keys["pro_annual"]}:
        return "pro"
    return "free"


def free_entitlements() -> PlanEntitlements:
    start, end = _current_month_period()
    return PlanEntitlements(
        planKey="free",
        billingStatus="free",
        monthlyIndexedTranscriptSeconds=get_free_indexed_transcript_seconds_total(),
        libraryTranscriptSeconds=get_free_indexed_transcript_seconds_total(),
        indexedVideosTotal=get_free_indexed_videos_total(),
        monthlyRetrievalCalls=get_free_searches_per_month(),
        maxImportVideos=get_free_max_import_videos(),
        maxSearchResults=get_free_max_search_results(),
        maxActiveIngestionJobs=get_free_max_active_ingestion_jobs(),
        deepTranscriptSeconds=0,
        priorityQueue=False,
        periodStart=start,
        periodEnd=end,
    )


def paid_entitlements(
    plan_key: str,
    billing_status: str,
    period_start: str | None,
    period_end: str | None,
    usage_pack_seconds_balance: int = 0,
) -> PlanEntitlements:
    if plan_key == "pro":
        return PlanEntitlements(
            planKey="pro",
            billingStatus=billing_status,
            monthlyIndexedTranscriptSeconds=200 * SECONDS_PER_HOUR,
            libraryTranscriptSeconds=2000 * SECONDS_PER_HOUR,
            indexedVideosTotal=5000,
            monthlyRetrievalCalls=10000,
            maxImportVideos=100,
            maxSearchResults=20,
            maxActiveIngestionJobs=5,
            deepTranscriptSeconds=50 * SECONDS_PER_HOUR,
            priorityQueue=True,
            usagePackSecondsBalance=usage_pack_seconds_balance,
            periodStart=period_start,
            periodEnd=period_end,
        )

    return PlanEntitlements(
        planKey="plus",
        billingStatus=billing_status,
        monthlyIndexedTranscriptSeconds=50 * SECONDS_PER_HOUR,
        libraryTranscriptSeconds=500 * SECONDS_PER_HOUR,
        indexedVideosTotal=1000,
        monthlyRetrievalCalls=2000,
        maxImportVideos=25,
        maxSearchResults=10,
        maxActiveIngestionJobs=2,
        deepTranscriptSeconds=0,
        priorityQueue=False,
        usagePackSecondsBalance=usage_pack_seconds_balance,
        periodStart=period_start,
        periodEnd=period_end,
    )


def get_billing_profile(supabase: Any, user_id: str) -> dict | None:
    result = (
        supabase.table(BILLING_PROFILE_TABLE)
        .select("*")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    return _single_row(result)


def upsert_billing_profile(supabase: Any, user_id: str, values: dict) -> dict:
    payload = {"user_id": user_id, **values}
    result = supabase.table(BILLING_PROFILE_TABLE).upsert(payload, on_conflict="user_id").execute()
    return _single_row(result) or payload


def get_or_create_billing_profile(supabase: Any, user_id: str) -> dict:
    profile = get_billing_profile(supabase, user_id)
    if profile:
        return profile
    return upsert_billing_profile(
        supabase,
        user_id,
        {"plan_key": "free", "billing_status": "free", "cancel_at_period_end": False},
    )


def get_period_usage(
    supabase: Any,
    user_id: str,
    entitlements: PlanEntitlements,
    profile: dict | None = None,
) -> dict:
    if entitlements.planKey == "free":
        return {
            "retrievalCalls": int((profile or {}).get("free_searches_this_month", 0) or 0),
            "indexedTranscriptSeconds": int(
                (profile or {}).get("free_indexed_seconds_total", 0) or 0
            ),
            "deepIndexedTranscriptSeconds": 0,
            "ingestionJobsStarted": 0,
            "indexedVideosAdded": int((profile or {}).get("free_indexed_videos_total", 0) or 0),
        }

    if not entitlements.periodStart or not entitlements.periodEnd:
        return _empty_period_usage()

    result = (
        supabase.table(BILLING_PERIOD_USAGE_TABLE)
        .select("*")
        .eq("user_id", user_id)
        .eq("period_start", entitlements.periodStart)
        .eq("period_end", entitlements.periodEnd)
        .maybe_single()
        .execute()
    )
    usage = _single_row(result) or {}
    return {
        "retrievalCalls": int(usage.get("retrieval_calls", 0) or 0),
        "indexedTranscriptSeconds": int(usage.get("indexed_transcript_seconds", 0) or 0),
        "deepIndexedTranscriptSeconds": int(usage.get("deep_indexed_transcript_seconds", 0) or 0),
        "ingestionJobsStarted": int(usage.get("ingestion_jobs_started", 0) or 0),
        "indexedVideosAdded": int(usage.get("indexed_videos_added", 0) or 0),
    }


def _empty_period_usage() -> dict:
    return {
        "retrievalCalls": 0,
        "indexedTranscriptSeconds": 0,
        "deepIndexedTranscriptSeconds": 0,
        "ingestionJobsStarted": 0,
        "indexedVideosAdded": 0,
    }


def resolve_user_entitlements(
    supabase: Any,
    user_id: str,
    profile: dict | None = None,
) -> dict:
    billing_profile = get_billing_profile(supabase, user_id)
    billing_status = (billing_profile or {}).get("billing_status") or "free"
    plan_key = (billing_profile or {}).get("plan_key") or "free"

    if billing_status not in ACTIVE_BILLING_STATUSES or plan_key not in {"plus", "pro"}:
        entitlements = free_entitlements()
        entitlements = PlanEntitlements(
            **{**entitlements.to_dict(), "billingStatus": billing_status}
        )
    else:
        entitlements = paid_entitlements(
            plan_key,
            billing_status,
            (billing_profile or {}).get("current_period_start"),
            (billing_profile or {}).get("current_period_end"),
            int((billing_profile or {}).get("usage_pack_seconds_balance", 0) or 0),
        )

    usage = get_period_usage(supabase, user_id, entitlements, profile)
    return {
        "entitlements": entitlements.to_dict(),
        "usage": usage,
        "billingProfile": billing_profile,
    }


def increment_billing_period_usage(
    supabase: Any,
    user_id: str,
    *,
    retrieval_calls: int = 0,
    indexed_transcript_seconds: int = 0,
    deep_indexed_transcript_seconds: int = 0,
    ingestion_jobs_started: int = 0,
    indexed_videos_added: int = 0,
) -> None:
    resolved = resolve_user_entitlements(supabase, user_id)
    entitlements = PlanEntitlements(**resolved["entitlements"])
    if entitlements.planKey == "free" or not entitlements.periodStart or not entitlements.periodEnd:
        return

    current = (
        supabase.table(BILLING_PERIOD_USAGE_TABLE)
        .select("*")
        .eq("user_id", user_id)
        .eq("period_start", entitlements.periodStart)
        .eq("period_end", entitlements.periodEnd)
        .maybe_single()
        .execute()
    )
    row = _single_row(current) or {}
    payload = {
        "user_id": user_id,
        "period_start": entitlements.periodStart,
        "period_end": entitlements.periodEnd,
        "retrieval_calls": int(row.get("retrieval_calls", 0) or 0) + retrieval_calls,
        "indexed_transcript_seconds": int(row.get("indexed_transcript_seconds", 0) or 0)
        + indexed_transcript_seconds,
        "deep_indexed_transcript_seconds": int(row.get("deep_indexed_transcript_seconds", 0) or 0)
        + deep_indexed_transcript_seconds,
        "ingestion_jobs_started": int(row.get("ingestion_jobs_started", 0) or 0)
        + ingestion_jobs_started,
        "indexed_videos_added": int(row.get("indexed_videos_added", 0) or 0) + indexed_videos_added,
    }
    (
        supabase.table(BILLING_PERIOD_USAGE_TABLE)
        .upsert(payload, on_conflict="user_id,period_start,period_end")
        .execute()
    )


def _price_id_for_lookup_key(lookup_key: str) -> str:
    overrides = get_stripe_price_id_overrides()
    if lookup_key in overrides:
        return overrides[lookup_key]

    stripe_client = _stripe_client()
    prices = stripe_client.Price.list(lookup_keys=[lookup_key], active=True, limit=1)
    data = _get(prices, "data", [])
    if not data:
        raise HTTPException(
            status_code=500,
            detail=f"Stripe price lookup key is not configured: {lookup_key}",
        )
    price_id = _stripe_id(data[0])
    if not price_id:
        raise HTTPException(status_code=500, detail="Stripe price did not include an id")
    return price_id


def _success_url() -> str:
    success_url = get_stripe_success_url()
    if "{CHECKOUT_SESSION_ID}" in success_url:
        return success_url
    separator = "&" if "?" in success_url else "?"
    return f"{success_url}{separator}session_id={{CHECKOUT_SESSION_ID}}"


def _customer_email(user: dict | None) -> str | None:
    if not user:
        return None
    return user.get("email") or (user.get("user_metadata") or {}).get("email")


def _is_missing_stripe_customer_error(exc: Exception) -> bool:
    invalid_request_error = (
        getattr(stripe, "InvalidRequestError", None) if stripe is not None else None
    )
    if invalid_request_error is not None and isinstance(exc, invalid_request_error):
        code = getattr(exc, "code", None)
        if code == "resource_missing":
            return True
    return "No such customer" in str(exc)


def _create_billing_customer(supabase: Any, user_id: str, user: dict) -> str:
    stripe_client = _stripe_client()
    customer = stripe_client.Customer.create(
        email=_customer_email(user),
        metadata={"user_id": user_id},
    )
    customer_id = _stripe_id(customer)
    if not customer_id:
        raise HTTPException(status_code=500, detail="Stripe customer did not include an id")
    upsert_billing_profile(
        supabase,
        user_id,
        {
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": None,
            "stripe_price_id": None,
            "price_lookup_key": None,
            "plan_key": "free",
            "billing_status": "free",
            "current_period_start": None,
            "current_period_end": None,
            "cancel_at_period_end": False,
        },
    )
    return customer_id


def _ensure_current_stripe_customer(supabase: Any, user_id: str, user: dict) -> str:
    billing_profile = get_or_create_billing_profile(supabase, user_id)
    customer_id = billing_profile.get("stripe_customer_id")
    if not customer_id:
        return _create_billing_customer(supabase, user_id, user)

    stripe_client = _stripe_client()
    try:
        stripe_client.Customer.retrieve(customer_id)
        return customer_id
    except Exception as exc:
        if not _is_missing_stripe_customer_error(exc):
            raise

    return _create_billing_customer(supabase, user_id, user)


def get_promo_trial(promo_code: str | None) -> dict | None:
    if not promo_code:
        return None
    return get_promo_trial_codes().get(promo_code.strip().lower())


def describe_promo_trial(promo_code: str | None) -> dict | None:
    """Return the public shape of a promo trial offer, or None if unknown."""
    promo = get_promo_trial(promo_code)
    if not promo:
        return None
    lookup_keys = get_stripe_price_lookup_keys()
    return {
        "code": promo["code"],
        "planKey": promo["plan_key"],
        "trialDays": promo["trial_days"],
        "lookupKey": lookup_keys[f"{promo['plan_key']}_monthly"],
    }


def _ensure_promo_trial_eligible(supabase: Any, user_id: str) -> None:
    profile = get_or_create_billing_profile(supabase, user_id)
    if profile.get("promo_trial_redeemed_at"):
        raise HTTPException(
            status_code=400,
            detail="This account has already redeemed a promotional trial.",
        )
    if profile.get("stripe_subscription_id"):
        raise HTTPException(
            status_code=400,
            detail="Promotional trials are only available to accounts without a prior subscription.",
        )


def create_checkout_session(
    supabase: Any,
    user: dict,
    lookup_key: str,
    promo_code: str | None = None,
) -> dict:
    if lookup_key not in allowed_subscription_lookup_keys():
        raise HTTPException(status_code=400, detail="Unsupported billing plan lookup key")

    user_id = user["sub"]
    promo = None
    if promo_code:
        promo = get_promo_trial(promo_code)
        if not promo:
            raise HTTPException(status_code=400, detail="Unknown promo code")
        if plan_key_for_lookup_key(lookup_key) != promo["plan_key"]:
            raise HTTPException(
                status_code=400,
                detail=f"This promo code applies to the {promo['plan_key'].title()} plan.",
            )
        _ensure_promo_trial_eligible(supabase, user_id)

    customer_id = _ensure_current_stripe_customer(supabase, user_id, user)
    stripe_client = _stripe_client()
    price_id = _price_id_for_lookup_key(lookup_key)
    metadata = {"user_id": user_id, "lookup_key": lookup_key}
    subscription_data: dict = {"metadata": dict(metadata)}
    session_params: dict = {
        "customer": customer_id,
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": _success_url(),
        "cancel_url": get_stripe_cancel_url(),
        "client_reference_id": user_id,
        "allow_promotion_codes": True,
    }
    if promo:
        metadata["promo_code"] = promo["code"]
        subscription_data["metadata"]["promo_code"] = promo["code"]
        subscription_data["trial_period_days"] = promo["trial_days"]
        # Card-optional trial: if no payment method exists at trial end, Stripe
        # cancels the subscription instead of invoicing, so nobody is surprise-charged.
        subscription_data["trial_settings"] = {"end_behavior": {"missing_payment_method": "cancel"}}
        session_params["payment_method_collection"] = "if_required"
    session_params["metadata"] = metadata
    session_params["subscription_data"] = subscription_data
    session = stripe_client.checkout.Session.create(**session_params)
    return {"url": _get(session, "url"), "id": _stripe_id(session)}


def create_portal_session(supabase: Any, user_id: str) -> dict:
    billing_profile = get_billing_profile(supabase, user_id)
    customer_id = (billing_profile or {}).get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=404, detail="No Stripe customer exists for this user")

    stripe_client = _stripe_client()
    session = stripe_client.billing_portal.Session.create(
        customer=customer_id,
        return_url=get_stripe_portal_return_url(),
    )
    return {"url": _get(session, "url"), "id": _stripe_id(session)}


def construct_stripe_event(payload: bytes, signature: str | None) -> Any:
    webhook_secret = get_stripe_webhook_secret()
    if not webhook_secret:
        raise HTTPException(status_code=500, detail="STRIPE_WEBHOOK_SECRET is not configured")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    stripe_client = _stripe_client()
    try:
        return stripe_client.Webhook.construct_event(payload, signature, webhook_secret)
    except Exception as exc:  # noqa: BLE001 - Stripe raises multiple signature/value errors.
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature") from exc


def _event_object(event: Any) -> Any:
    return _get(_get(event, "data", {}), "object", {})


def _subscription_id_from_object(obj: Any) -> str | None:
    object_kind = _get(obj, "object")
    if object_kind == "subscription":
        return _stripe_id(obj)
    subscription_id = _stripe_id(_get(obj, "subscription"))
    if subscription_id:
        return subscription_id
    # Stripe API 2025-03-31.basil+ invoices reference their subscription under
    # parent.subscription_details instead of a top-level subscription field.
    parent = _get(obj, "parent", {}) or {}
    details = _get(parent, "subscription_details", {}) or {}
    return _stripe_id(_get(details, "subscription"))


def _mark_event(
    supabase: Any,
    stripe_event_id: str,
    processing_status: str,
    error_message: str | None = None,
) -> None:
    payload = {
        "processing_status": processing_status,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
    if error_message:
        payload["error_message"] = error_message
    supabase.table(BILLING_EVENTS_TABLE).update(payload).eq(
        "stripe_event_id", stripe_event_id
    ).execute()


def _insert_event(supabase: Any, event: Any) -> tuple[bool, str]:
    stripe_event_id = _get(event, "id")
    event_type = _get(event, "type")
    obj = _event_object(event)
    subscription_id = _subscription_id_from_object(obj)
    customer_id = _stripe_id(_get(obj, "customer"))

    existing = (
        supabase.table(BILLING_EVENTS_TABLE)
        .select("stripe_event_id, processing_status")
        .eq("stripe_event_id", stripe_event_id)
        .maybe_single()
        .execute()
    )
    if _single_row(existing):
        return False, stripe_event_id

    supabase.table(BILLING_EVENTS_TABLE).insert(
        {
            "stripe_event_id": stripe_event_id,
            "event_type": event_type,
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
            "processing_status": "processing",
        }
    ).execute()
    return True, stripe_event_id


def _subscription_items(subscription: Any) -> list:
    items = _get(subscription, "items", {}) or {}
    return _get(items, "data", []) or []


def _subscription_price(subscription: Any) -> tuple[str | None, str | None]:
    item_data = _subscription_items(subscription)
    if not item_data:
        return None, None
    price = _get(item_data[0], "price", {})
    return _stripe_id(price), _get(price, "lookup_key")


def _subscription_period(subscription: Any) -> tuple[str | None, str | None]:
    """Return the current billing period across Stripe API shape changes.

    API versions before 2025-03-31.basil expose current_period_start/end on the
    subscription itself; newer versions moved them onto each subscription item.
    """
    start = _get(subscription, "current_period_start")
    end = _get(subscription, "current_period_end")
    if start is None or end is None:
        item_data = _subscription_items(subscription)
        if item_data:
            if start is None:
                start = _get(item_data[0], "current_period_start")
            if end is None:
                end = _get(item_data[0], "current_period_end")
    return _iso_from_timestamp(start), _iso_from_timestamp(end)


def _metadata_user_id(obj: Any) -> str | None:
    metadata = _get(obj, "metadata", {}) or {}
    return _get(metadata, "user_id")


def _find_user_id_for_subscription(supabase: Any, subscription: Any) -> str | None:
    user_id = _metadata_user_id(subscription)
    if user_id:
        return user_id

    customer_id = _stripe_id(_get(subscription, "customer"))
    if customer_id:
        result = (
            supabase.table(BILLING_PROFILE_TABLE)
            .select("user_id")
            .eq("stripe_customer_id", customer_id)
            .maybe_single()
            .execute()
        )
        row = _single_row(result)
        if row:
            return row.get("user_id")

    subscription_id = _stripe_id(subscription)
    if subscription_id:
        result = (
            supabase.table(BILLING_PROFILE_TABLE)
            .select("user_id")
            .eq("stripe_subscription_id", subscription_id)
            .maybe_single()
            .execute()
        )
        row = _single_row(result)
        if row:
            return row.get("user_id")

    return None


def apply_subscription_state(
    supabase: Any,
    subscription: Any,
    stripe_event_id: str | None = None,
) -> dict | None:
    user_id = _find_user_id_for_subscription(supabase, subscription)
    if not user_id:
        return None

    status = str(_get(subscription, "status", "canceled") or "canceled")
    if status not in KNOWN_BILLING_STATUSES:
        status = "incomplete"

    price_id, lookup_key = _subscription_price(subscription)
    plan_key = plan_key_for_lookup_key(lookup_key)
    period_start, period_end = _subscription_period(subscription)
    payload = {
        "stripe_customer_id": _stripe_id(_get(subscription, "customer")),
        "stripe_subscription_id": _stripe_id(subscription),
        "stripe_price_id": price_id,
        "price_lookup_key": lookup_key,
        "plan_key": plan_key,
        "billing_status": status,
        "current_period_start": period_start,
        "current_period_end": period_end,
        "cancel_at_period_end": bool(_get(subscription, "cancel_at_period_end", False)),
    }
    if stripe_event_id:
        payload["last_stripe_event_id"] = stripe_event_id
    return upsert_billing_profile(supabase, user_id, payload)


def _retrieve_subscription(subscription_id: str) -> Any:
    stripe_client = _stripe_client()
    return stripe_client.Subscription.retrieve(
        subscription_id,
        expand=["items.data.price"],
    )


def _apply_checkout_session_completed(supabase: Any, session: Any, stripe_event_id: str) -> None:
    user_id = _metadata_user_id(session) or _get(session, "client_reference_id")
    if not user_id:
        return

    profile_payload = {
        "stripe_customer_id": _stripe_id(_get(session, "customer")),
        "last_stripe_event_id": stripe_event_id,
    }
    promo_code = _get(_get(session, "metadata", {}) or {}, "promo_code")
    if promo_code:
        profile_payload["promo_trial_code"] = promo_code
        profile_payload["promo_trial_redeemed_at"] = datetime.now(timezone.utc).isoformat()
    upsert_billing_profile(supabase, user_id, profile_payload)
    subscription_id = _stripe_id(_get(session, "subscription"))
    if subscription_id:
        apply_subscription_state(supabase, _retrieve_subscription(subscription_id), stripe_event_id)


def _apply_invoice_event(
    supabase: Any, invoice: Any, event_type: str, stripe_event_id: str
) -> None:
    subscription_id = _subscription_id_from_object(invoice)
    if subscription_id:
        apply_subscription_state(supabase, _retrieve_subscription(subscription_id), stripe_event_id)
        return

    customer_id = _stripe_id(_get(invoice, "customer"))
    if event_type == "invoice.payment_failed" and customer_id:
        result = (
            supabase.table(BILLING_PROFILE_TABLE)
            .select("user_id")
            .eq("stripe_customer_id", customer_id)
            .maybe_single()
            .execute()
        )
        row = _single_row(result)
        if row:
            upsert_billing_profile(
                supabase,
                row["user_id"],
                {"billing_status": "past_due", "last_stripe_event_id": stripe_event_id},
            )


def process_stripe_event(supabase: Any, event: Any) -> dict:
    inserted, stripe_event_id = _insert_event(supabase, event)
    if not inserted:
        return {"received": True, "duplicate": True, "eventId": stripe_event_id}

    event_type = _get(event, "type")
    obj = _event_object(event)
    try:
        if event_type == "checkout.session.completed":
            _apply_checkout_session_completed(supabase, obj, stripe_event_id)
        elif event_type in {
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
        }:
            apply_subscription_state(supabase, obj, stripe_event_id)
        elif event_type in {"invoice.payment_succeeded", "invoice.payment_failed"}:
            _apply_invoice_event(supabase, obj, event_type, stripe_event_id)
        else:
            _mark_event(supabase, stripe_event_id, "ignored")
            return {"received": True, "ignored": True, "eventId": stripe_event_id}
    except Exception as exc:
        _mark_event(supabase, stripe_event_id, "failed", str(exc))
        raise

    _mark_event(supabase, stripe_event_id, "processed")
    return {"received": True, "duplicate": False, "eventId": stripe_event_id}
