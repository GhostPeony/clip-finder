import React, { useEffect, useState } from 'react';
import {
  BillingPromo,
  createBillingCheckout,
  fetchBillingPromo,
  fetchBillingStatus,
} from '../services/api';
import { clearStoredPromoCode, getStoredPromoCode } from '../lib/promo';

// Shown to signed-in Free users who arrived through a promotional signup link
// (?promo=CODE). Redeems through Stripe Checkout as a card-optional plan trial.
export const PromoTrialBanner: React.FC = () => {
  const [promo, setPromo] = useState<BillingPromo | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = getStoredPromoCode();
    if (!code) return;
    let cancelled = false;
    Promise.all([fetchBillingPromo(code), fetchBillingStatus()]).then(([offer, status]) => {
      if (cancelled) return;
      if (!offer) {
        clearStoredPromoCode();
        return;
      }
      if (!status || status.planKey !== 'free') return;
      setPromo(offer);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!promo) return null;

  const planLabel = promo.planKey.replace(/^\w/, (char) => char.toUpperCase());

  const startTrial = async () => {
    setBusy(true);
    setError(null);
    try {
      window.location.href = await createBillingCheckout(promo.lookupKey, promo.code);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not open Stripe Checkout.');
      setBusy(false);
    }
  };

  const dismiss = () => {
    clearStoredPromoCode();
    setPromo(null);
  };

  return (
    <section
      aria-label="Promotional trial offer"
      className="mb-6 rounded-xl border border-ink/10 bg-surface p-4 shadow-soft"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-bark">
            Launch offer unlocked
          </p>
          <h2 className="mt-1 font-serif text-xl font-medium text-ink">
            Try {planLabel} free for {promo.trialDays} days
          </h2>
          <p className="mt-1 text-sm leading-6 text-bark">
            Full {planLabel} limits while you test. No card required — after the trial your account
            returns to Free unless you subscribe.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button onClick={startTrial} disabled={busy} className="btn btn-primary">
            {busy ? 'Opening Stripe...' : 'Start free trial'}
          </button>
          <button
            onClick={dismiss}
            disabled={busy}
            className="rounded-xl px-3 py-2 text-sm font-medium text-bark transition-colors hover:bg-cream/60"
          >
            Dismiss
          </button>
        </div>
      </div>
      {error ? (
        <p className="mt-3 rounded-lg bg-rose/10 px-3 py-2 text-sm text-rose-deep" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
};
