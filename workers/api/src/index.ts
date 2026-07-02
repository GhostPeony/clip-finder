import { Container, getContainer } from '@cloudflare/containers';

export interface Env {
  API_CONTAINER: DurableObjectNamespace<MemexaiApiContainer>;
  API_KEY_ENCRYPTION_KEY: string;
  GEMINI_API_KEY: string;
  SEARCHTUBE_STORAGE: string;
  SEARCHTUBE_AUTH_MODE: string;
  SEARCHTUBE_API_KEY_MODE: string;
  SEARCHTUBE_ALLOWED_ORIGINS: string;
  MEMEXAI_APP_URL: string;
  INGESTION_DISPATCH_MODE: string;
  EMBEDDING_MODEL: string;
  EMBEDDING_DIMENSIONS: string;
  LLM_MODEL: string;
  SUPABASE_ANON_KEY?: string;
  SUPABASE_JWT_SECRET?: string;
  SUPABASE_SERVICE_ROLE_KEY: string;
  STRIPE_PLUS_ANNUAL_LOOKUP_KEY?: string;
  STRIPE_PLUS_MONTHLY_LOOKUP_KEY?: string;
  STRIPE_PORTAL_RETURN_URL?: string;
  STRIPE_PRO_ANNUAL_LOOKUP_KEY?: string;
  STRIPE_PRO_MONTHLY_LOOKUP_KEY?: string;
  STRIPE_SECRET_KEY?: string;
  STRIPE_WEBHOOK_SECRET?: string;
  STRIPE_CANCEL_URL?: string;
  STRIPE_SUCCESS_URL?: string;
  PROMO_TRIAL_CODES?: string;
  VITE_SUPABASE_ANON_KEY: string;
  VITE_SUPABASE_URL: string;
  WORKFLOW_INTERNAL_SECRET?: string;
}

const API_INSTANCE_ID = 'production-20260630-mcp-retrieval';

export class MemexaiApiContainer extends Container {
  defaultPort = 8080;
  sleepAfter = '10m';
  envVars = {
    API_KEY_ENCRYPTION_KEY: this.env.API_KEY_ENCRYPTION_KEY,
    GEMINI_API_KEY: this.env.GEMINI_API_KEY,
    SEARCHTUBE_STORAGE: this.env.SEARCHTUBE_STORAGE,
    SEARCHTUBE_AUTH_MODE: this.env.SEARCHTUBE_AUTH_MODE,
    SEARCHTUBE_API_KEY_MODE: this.env.SEARCHTUBE_API_KEY_MODE,
    SEARCHTUBE_ALLOWED_ORIGINS: this.env.SEARCHTUBE_ALLOWED_ORIGINS,
    MEMEXAI_APP_URL: this.env.MEMEXAI_APP_URL,
    INGESTION_DISPATCH_MODE: this.env.INGESTION_DISPATCH_MODE,
    EMBEDDING_MODEL: this.env.EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS: this.env.EMBEDDING_DIMENSIONS,
    LLM_MODEL: this.env.LLM_MODEL,
    SUPABASE_ANON_KEY: this.env.SUPABASE_ANON_KEY || this.env.VITE_SUPABASE_ANON_KEY,
    SUPABASE_JWT_SECRET: this.env.SUPABASE_JWT_SECRET || '',
    SUPABASE_SERVICE_ROLE_KEY: this.env.SUPABASE_SERVICE_ROLE_KEY,
    STRIPE_SECRET_KEY: this.env.STRIPE_SECRET_KEY || '',
    STRIPE_WEBHOOK_SECRET: this.env.STRIPE_WEBHOOK_SECRET || '',
    STRIPE_PLUS_MONTHLY_LOOKUP_KEY:
      this.env.STRIPE_PLUS_MONTHLY_LOOKUP_KEY || 'memexai_plus_monthly_v1',
    STRIPE_PLUS_ANNUAL_LOOKUP_KEY:
      this.env.STRIPE_PLUS_ANNUAL_LOOKUP_KEY || 'memexai_plus_annual_v1',
    STRIPE_PRO_MONTHLY_LOOKUP_KEY:
      this.env.STRIPE_PRO_MONTHLY_LOOKUP_KEY || 'memexai_pro_monthly_v1',
    STRIPE_PRO_ANNUAL_LOOKUP_KEY: this.env.STRIPE_PRO_ANNUAL_LOOKUP_KEY || 'memexai_pro_annual_v1',
    STRIPE_SUCCESS_URL: this.env.STRIPE_SUCCESS_URL || '',
    STRIPE_CANCEL_URL: this.env.STRIPE_CANCEL_URL || '',
    STRIPE_PORTAL_RETURN_URL: this.env.STRIPE_PORTAL_RETURN_URL || '',
    PROMO_TRIAL_CODES: this.env.PROMO_TRIAL_CODES || '',
    VITE_SUPABASE_ANON_KEY: this.env.VITE_SUPABASE_ANON_KEY,
    VITE_SUPABASE_URL: this.env.VITE_SUPABASE_URL,
    WORKFLOW_INTERNAL_SECRET: this.env.WORKFLOW_INTERNAL_SECRET || '',
  };
}

export default {
  async fetch(request: Request, runtimeEnv: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === '/_worker/health') {
      return Response.json({
        status: 'ok',
        service: 'memexai-api-worker',
        containerInstance: API_INSTANCE_ID,
      });
    }

    const container = getContainer(runtimeEnv.API_CONTAINER, API_INSTANCE_ID);
    await container.startAndWaitForPorts({
      ports: [8080],
      cancellationOptions: {
        instanceGetTimeoutMS: 10000,
        portReadyTimeoutMS: 45000,
        waitInterval: 500,
      },
    });
    return container.fetch(request);
  },
};
