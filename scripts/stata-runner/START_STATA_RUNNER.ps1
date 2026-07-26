$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$configPath = Join-Path $repoRoot ".env.stata-runner.local"

if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
  throw "Runner config is missing. Run SETUP_STATA_RUNNER.bat first."
}

Get-Content -LiteralPath $configPath | ForEach-Object {
  $line = $_.Trim()
  if (-not $line -or $line.StartsWith("#")) { return }
  $parts = $line.Split("=", 2)
  if ($parts.Count -ne 2) { return }
  $value = $parts[1].Trim()
  if ($value.Length -ge 2 -and $value.StartsWith('"') -and $value.EndsWith('"')) {
    $value = $value.Substring(1, $value.Length - 2)
  }
  [Environment]::SetEnvironmentVariable($parts[0].Trim(), $value, "Process")
}

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$python = if (Test-Path -LiteralPath $venvPython) {
  $venvPython
} else {
  (Get-Command python -ErrorAction Stop).Source
}
$env:PYTHONPATH = Join-Path $repoRoot "src"
Set-Location $repoRoot
Write-Host "Starting AI4MS Stata Local Runner on $env:AI4MS_LOCAL_RUNNER_HOST`:$env:AI4MS_LOCAL_RUNNER_PORT" -ForegroundColor Cyan
Write-Host "Keep this window open while Stata jobs are running."
& $python -m ai4ms.runners.local_app
exit $LASTEXITCODE
