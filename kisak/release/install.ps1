# Downloads the third-party runtime files (Miles audio, Bink video, Steam API stub) the exe needs, from upstream
# KisakCOD, and checks them against deps.txt. Edit deps.txt (BASE line) to use another source. Safe to re-run.
# Right click -> Run with PowerShell.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$lines = Get-Content deps.txt | Where-Object { $_ -notmatch '^\s*#' -and $_.Trim() -ne '' }
$base = ($lines | Where-Object { $_ -like 'BASE=*' }).Substring(5)
foreach ($l in $lines | Where-Object { $_ -notlike 'BASE=*' }) {
  $sum, $dst, $src = $l -split '\s+'
  if ((Test-Path $dst) -and ((Get-FileHash $dst -Algorithm SHA256).Hash -eq $sum)) { continue }
  New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent | ForEach-Object { if ($_) { $_ } else { '.' } }) | Out-Null
  Write-Host "downloading $dst"
  Invoke-WebRequest "$base/$src" -OutFile "$dst.tmp"
  if ((Get-FileHash "$dst.tmp" -Algorithm SHA256).Hash -ne $sum) { Remove-Item "$dst.tmp"; throw "CHECKSUM MISMATCH for $dst" }
  Move-Item -Force "$dst.tmp" $dst
}
if (-not ((Test-Path ..\main) -and (Test-Path ..\zone))) { Write-Warning "..\main and ..\zone not found - this folder must sit inside your game folder." }
Write-Host "Dependencies ready."
