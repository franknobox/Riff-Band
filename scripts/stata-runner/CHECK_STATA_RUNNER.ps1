$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$configPath = Join-Path $repoRoot ".env.stata-runner.local"

if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
  throw "Runner config is missing. Run SETUP_STATA_RUNNER.bat first."
}

$settings = @{}
Get-Content -LiteralPath $configPath | ForEach-Object {
  $line = $_.Trim()
  if (-not $line -or $line.StartsWith("#")) { return }
  $parts = $line.Split("=", 2)
  if ($parts.Count -ne 2) { return }
  $settings[$parts[0].Trim()] = $parts[1].Trim().Trim('"')
}

$url = "$($settings["AI4MS_STATA_RUNNER_URL"])/v1/status"
$headers = @{ "X-AI4MS-Runner-Token" = $settings["AI4MS_STATA_RUNNER_TOKEN"] }
$profile = Invoke-RestMethod -Method Get -Uri $url -Headers $headers -TimeoutSec 5
$profile | ConvertTo-Json -Depth 5
if (-not $profile.available) {
  throw "Runner answered, but Stata is unavailable: $($profile.reason)"
}
Write-Host "AI4MS Stata Local Runner is ready." -ForegroundColor Green
