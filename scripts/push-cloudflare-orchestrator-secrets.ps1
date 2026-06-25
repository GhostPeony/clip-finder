param(
    [string]$EnvFile = ".env.cloudflare.local",
    [string]$Config = "workers/orchestrator/wrangler.toml"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Missing $EnvFile. Create it first with WORKFLOW_INTERNAL_SECRET and ORCHESTRATOR_SHARED_SECRET."
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

$required = @(
    "WORKFLOW_INTERNAL_SECRET",
    "ORCHESTRATOR_SHARED_SECRET"
)

$missing = $required | Where-Object { -not $values.ContainsKey($_) -or -not $values[$_].Trim() }
if ($missing.Count -gt 0) {
    throw "Missing required secrets in ${EnvFile}: $($missing -join ', ')"
}

Write-Host "Uploading ORCHESTRATOR_SHARED_SECRET..."
$values["ORCHESTRATOR_SHARED_SECRET"] | npx wrangler secret put ORCHESTRATOR_SHARED_SECRET --config $Config

Write-Host "Uploading MEMEXAI_WORKFLOW_SECRET..."
$values["WORKFLOW_INTERNAL_SECRET"] | npx wrangler secret put MEMEXAI_WORKFLOW_SECRET --config $Config

Write-Host "Cloudflare orchestrator secrets uploaded."
