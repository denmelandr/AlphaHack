$ErrorActionPreference = "Stop"
Push-Location (Join-Path $PSScriptRoot "..")
try {
  $required = @("README.md", "SUBMISSION.md", "VERSION", "THIRD_PARTY_NOTICES", "THIRD_PARTY_NOTICES.md", ".env.example", "compose.yaml", "pnpm-lock.yaml", "docs/architecture.md", "docs/api.md", "docs/openapi.json", "docs/postman_collection.json", "docs/test-scenarios.md", "docs/demo.md", "credit-conveyor/backend/requirements.txt")
  foreach ($path in $required) { if (-not (Test-Path $path -PathType Leaf)) { throw "Missing: $path" } }
  python scripts/check_contract.py
  if ($LASTEXITCODE -ne 0) { throw "Contract check failed" }
  docker compose config --quiet
  if ($LASTEXITCODE -ne 0) { throw "Compose invalid" }
  Invoke-WebRequest http://localhost:8080/health -UseBasicParsing | Out-Null
  Invoke-WebRequest http://localhost:5173/api/health -UseBasicParsing | Out-Null
  Invoke-WebRequest http://localhost:8080/docs -UseBasicParsing | Out-Null
  python scripts/check_contract.py --live
  if ($LASTEXITCODE -ne 0) { throw "Live contract differs" }
  docker compose exec -T backend python -m pytest -q
  if ($LASTEXITCODE -ne 0) { throw "Backend tests failed" }
  Write-Host "PASS: submission artifacts, Swagger, API schema and backend tests"
} finally { Pop-Location }
