# Security Policy

## Supported Branch

This production fork is the active security target. The older open-source local-mode project may diverge.

## Secrets

Never commit real secrets. Required production secrets include:

- `GEMINI_API_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`
- `API_KEY_ENCRYPTION_KEY`

Use `.env.production.example` for names and placeholders only. Run:

```bash
python scripts/check_hosted_readiness.py
```

before hosted smoke tests.

## Reporting Vulnerabilities

Do not open public issues containing credentials, exploit details, user data, or private URLs. Send a private report to the project owner with:

- affected endpoint or feature
- reproduction steps
- expected impact
- any relevant logs with secrets redacted

## Baseline Checks

Before deployment:

```bash
npm run verify
python -m compileall backend
python -c "import backend.server; import backend.worker"
python -m pytest
```
