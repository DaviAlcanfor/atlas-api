# Production migration template (used on 2026-11-12 to fix the v1.1 503s). Copy, set $revision, rehearse, then run.
# 1. Create a worktree of the EXACT code being deployed (never a branch with newer migrations):
#      git -C atlas-api worktree add ..\atlas-api-deploy <branch-or-commit>
# 2. Rehearse on a scratch local DB (CREATE DATABASE atlas_rehearsal) with the same commands.
# 3. Run from the "atlas" folder; production first, merge the API PR after (the merge deploys).
# Keep this file pure ASCII: Windows PowerShell 5.1 reads BOM-less scripts as ANSI and mangles accented folder names.
$ErrorActionPreference = 'Stop'
$revision = '0010'   # last migration of the code being deployed (v1.2 part A = 0010)
$api  = Join-Path (Get-Location).Path 'atlas-api'
if (-not (Test-Path (Join-Path $api '.env'))) { throw "Run from the 'atlas' folder: $api\.env not found" }
$deploy = Join-Path (Get-Location).Path 'atlas-api-deploy'
if (-not (Test-Path $deploy)) { throw "Create the worktree first: git -C atlas-api worktree add ..\atlas-api-deploy <branch>" }
$py   = Join-Path $api '.venv\Scripts\python.exe'

$line = Get-Content (Join-Path $api '.env') | Where-Object { $_ -like 'SUPABASE_DATABASE_URL=*' }
if (-not $line) { throw 'SUPABASE_DATABASE_URL not found in atlas-api\.env' }
$env:DATABASE_URL = $line.Substring('SUPABASE_DATABASE_URL='.Length)
$env:PYTHONPATH = 'src'
Set-Location $deploy
if (-not (Test-Path 'data_out')) { Copy-Item -Recurse (Join-Path $api 'data_out') 'data_out' }

Write-Host '1/4 current revision:'
& $py -m alembic current
Write-Host "2/4 migrating to $revision (NOT head)..."
& $py -m alembic upgrade $revision
& $py -m alembic current
Write-Host '3/4 importing content and facts...'
& $py -m atlas_api.cli import-content
& $py -m atlas_api.cli import-facts
Write-Host '4/4 checking production (the new endpoints only answer after the API PR is merged/deployed):'
foreach ($p in 'countries/BR', 'glossary', 'countries/BR/leaders') {
  try { $r = Invoke-WebRequest "https://atlas-api.fastapicloud.dev/v1/$p" -UseBasicParsing; Write-Host "$p -> $($r.StatusCode)" }
  catch { Write-Host "$p -> $($_.Exception.Message)" }
}
Remove-Item Env:DATABASE_URL
