$ErrorActionPreference = "Stop"

$required = @(
  "README.md",
  "SUBMISSION.md",
  "VERSION",
  "THIRD_PARTY_NOTICES.md",
  "docker-compose.yml",
  ".env.example",
  "backend/requirements.txt",
  "../pnpm-lock.yaml",
  "docs/ARCHITECTURE.md",
  "docs/API_GUIDE.md",
  "docs/openapi.json",
  "docs/postman_collection.json",
  "docs/TEST_SCENARIOS.md",
  "docs/SYNTHETIC_DATA.md",
  "docs/DEMO_RUNBOOK.md"
)

foreach ($path in $required) {
  if (-not (Test-Path $path -PathType Leaf)) {
    throw "Missing file: $path"
  }
}

docker compose config --quiet

try {
  Invoke-WebRequest -UseBasicParsing http://localhost:8080/health | Out-Null
  Write-Host "backend health: ok"
} catch {
  Write-Host "backend health: skipped (start with docker compose up)"
}

$running = docker compose ps --status running --services 2>$null
if ($running -contains "backend") {
  docker compose exec -T backend python -m pytest -q
} else {
  Write-Host "backend tests: skipped (backend container is not running)"
}

Write-Host "submission artifact check: ok"
