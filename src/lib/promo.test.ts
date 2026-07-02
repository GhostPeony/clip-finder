import { afterEach, describe, expect, it } from 'vitest';
import { capturePromoCodeFromUrl, clearStoredPromoCode, getStoredPromoCode } from './promo';

const setUrl = (path: string) => {
  window.history.replaceState(null, '', path);
};

describe('promo code capture', () => {
  afterEach(() => {
    clearStoredPromoCode();
    setUrl('/');
  });

  it('stores a lowercased ?promo= code and strips it from the URL', () => {
    setUrl('/?promo=ProductHunt&other=kept');

    capturePromoCodeFromUrl();

    expect(getStoredPromoCode()).toBe('producthunt');
    expect(window.location.search).toBe('?other=kept');
  });

  it('leaves storage untouched when no promo param is present', () => {
    setUrl('/?other=kept');

    capturePromoCodeFromUrl();

    expect(getStoredPromoCode()).toBeNull();
  });

  it('clears the stored code after a successful checkout return', () => {
    setUrl('/?promo=producthunt');
    capturePromoCodeFromUrl();
    expect(getStoredPromoCode()).toBe('producthunt');

    setUrl('/?billing=success');
    capturePromoCodeFromUrl();

    expect(getStoredPromoCode()).toBeNull();
  });

  it('clears the stored code on demand', () => {
    setUrl('/?promo=producthunt');
    capturePromoCodeFromUrl();

    clearStoredPromoCode();

    expect(getStoredPromoCode()).toBeNull();
  });
});
