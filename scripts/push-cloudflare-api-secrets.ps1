param(
    [string]$EnvFile = ".env.cloudflare.local",
    [string]$Config = "wrangler.api.toml"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Missing $EnvFile. Create it first with the API Worker secrets."
}

if (-not (Test-Path -LiteralPath $Config)) {
    throw "Missing $Config. Run this from the project root."
}

$values = @{}
Get-Content -LiteralPath $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
        return
    }

    $key, $value = $line.Split("=", 2)
    $key = $key.Trim()
    $value = $value.Trim().Trim('"').Trim("'")
    if ($key) {
        $values[$key] = $value
    }
}

if (-not $values.ContainsKey("SUPABASE_ANON_KEY") -and $values.ContainsKey("VITE_SUPABASE_ANON_KEY")) {
    $values["SUPABASE_ANON_KEY"] = $values["VITE_SUPABASE_ANON_KEY"]
}

$required = @(
    "API_KEY_ENCRYPTION_KEY",
    "GEMINI_API_KEY",
    "VITE_SUPABASE_URL",
    "VITE_SUPABASE_ANON_KEY",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET"
)

$missing = $required | Where-Object { -not $values.ContainsKey($_) -or -not $values[$_].Trim() }
if ($missing.Count -gt 0) {
    throw "Missing required secrets in ${EnvFile}: $($missing -join ', ')"
}

foreach ($name in $required) {
    Write-Host "Uploading $name..."
    $values[$name] | npx wrangler secret put $name --config $Config
}

if ($values.ContainsKey("WORKFLOW_INTERNAL_SECRET") -and $values["WORKFLOW_INTERNAL_SECRET"].Trim()) {
    Write-Host "Uploading WORKFLOW_INTERNAL_SECRET..."
    $values["WORKFLOW_INTERNAL_SECRET"] | npx wrangler secret put WORKFLOW_INTERNAL_SECRET --config $Config
}

if ($values.ContainsKey("SUPABASE_JWT_SECRET") -and $values["SUPABASE_JWT_SECRET"].Trim()) {
    Write-Host "Uploading SUPABASE_JWT_SECRET..."
    $values["SUPABASE_JWT_SECRET"] | npx wrangler secret put SUPABASE_JWT_SECRET --config $Config
}

$optionalStripeValues = @(
    "STRIPE_PLUS_MONTHLY_LOOKUP_KEY",
    "STRIPE_PLUS_ANNUAL_LOOKUP_KEY",
    "STRIPE_PRO_MONTHLY_LOOKUP_KEY",
    "STRIPE_PRO_ANNUAL_LOOKUP_KEY",
    "STRIPE_SUCCESS_URL",
    "STRIPE_CANCEL_URL",
    "STRIPE_PORTAL_RETURN_URL"
)

foreach ($name in $optionalStripeValues) {
    if ($values.ContainsKey($name) -and $values[$name].Trim()) {
        Write-Host "Uploading $name..."
        $values[$name] | npx wrangler secret put $name --config $Config
    }
}

Write-Host "Cloudflare API Worker secrets uploaded."
