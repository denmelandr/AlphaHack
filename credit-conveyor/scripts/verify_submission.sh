#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

require_file() {
  test -f "$1" || fail "missing file: $1"
}

require_file README.md
require_file SUBMISSION.md
require_file VERSION
require_file THIRD_PARTY_NOTICES.md
require_file docker-compose.yml
require_file .env.example
require_file backend/requirements.txt
require_file ../pnpm-lock.yaml
require_file docs/ARCHITECTURE.md
require_file docs/API_GUIDE.md
require_file docs/openapi.json
require_file docs/postman_collection.json
require_file docs/TEST_SCENARIOS.md
require_file docs/SYNTHETIC_DATA.md
require_file docs/DEMO_RUNBOOK.md

command -v docker >/dev/null 2>&1 || fail "docker is not installed"
docker compose config --quiet || fail "docker compose config is invalid"

if curl -fsS http://localhost:8080/health >/dev/null 2>&1; then
  printf 'backend health: ok\n'
else
  printf 'backend health: skipped (start with docker compose up)\n'
fi

if docker compose ps --status running --services 2>/dev/null | grep -q '^backend$'; then
  docker compose exec -T backend python -m pytest -q
else
  printf 'backend tests: skipped (backend container is not running)\n'
fi

printf 'submission artifact check: ok\n'
