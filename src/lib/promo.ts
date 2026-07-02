// Promotional signup links land with ?promo=CODE (e.g. Product Hunt launch links).
// The code is stashed in localStorage so it survives the OAuth signup redirect,
// then redeemed through Stripe Checkout as a plan trial.

const PROMO_STORAGE_KEY = 'memexai:promo-code:v1';

export function capturePromoCodeFromUrl(): void {
  if (typeof window === 'undefined') return;
  const url = new URL(window.location.href);
  const promo = url.searchParams.get('promo');
  if (promo && promo.trim()) {
    try {
      window.localStorage.setItem(PROMO_STORAGE_KEY, promo.trim().toLowerCase());
    } catch {
      // Storage can be unavailable (private mode); the link still works without it.
    }
    url.searchParams.delete('promo');
    window.history.replaceState(
      window.history.state,
      '',
      `${url.pathname}${url.search}${url.hash}`,
    );
  }
  // A completed checkout means the stored code was redeemed (or is now moot).
  if (url.searchParams.get('billing') === 'success') {
    clearStoredPromoCode();
  }
}

export function getStoredPromoCode(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage.getItem(PROMO_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function clearStoredPromoCode(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(PROMO_STORAGE_KEY);
  } catch {
    // Ignore storage failures.
  }
}
