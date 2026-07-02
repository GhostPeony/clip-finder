import React from 'react';
import { SocialLinks } from './SocialLinks';
import {
  CONTACT_EMAIL,
  GHOST_PEONY_GITHUB_URL,
  GHOST_PEONY_NAME,
  GHOST_PEONY_URL,
  PRODUCT_DOMAIN,
  PRODUCT_NAME,
} from '../brand';

export function ContactPage({ onBack }: { onBack: () => void }) {
  return (
    <div className="py-8 max-w-2xl mx-auto">
      <button onClick={onBack} className="link-quiet mb-6 flex items-center gap-1 text-sm">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back
      </button>
      <div className="card p-8">
        <h1 className="mb-4 font-serif text-4xl font-medium text-ink">Contact</h1>
        <div className="space-y-4 text-sm leading-7 text-bark">
          <p>Have questions, feedback, or found a bug? We'd love to hear from you.</p>
          <div className="space-y-3 rounded-xl bg-cream p-5">
            <a
              href={`mailto:${CONTACT_EMAIL}`}
              className="block font-semibold text-violet-deep underline decoration-2 underline-offset-4"
            >
              {CONTACT_EMAIL}
            </a>
            <a
              href={GHOST_PEONY_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="block font-semibold text-violet-deep underline decoration-2 underline-offset-4"
            >
              ghostpeony.com
            </a>
            <a
              href={GHOST_PEONY_GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="block font-semibold text-violet-deep underline decoration-2 underline-offset-4"
            >
              github.com/GhostPeony
            </a>
            <SocialLinks className="pt-2" />
          </div>
          <p className="pt-2">
            {PRODUCT_NAME} is a {GHOST_PEONY_NAME} product for turning YouTube videos into a
            searchable saved-video library. The production home is {PRODUCT_DOMAIN}.
          </p>
        </div>
      </div>
    </div>
  );
}
