#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
API_BASE_URL="${API_BASE_URL:-http://localhost:8080}"
FRONTEND_BASE_URL="${FRONTEND_BASE_URL:-http://localhost:5173}"
for path in README.md SUBMISSION.md VERSION THIRD_PARTY_NOTICES THIRD_PARTY_NOTICES.md .env.example compose.yaml pnpm-lock.yaml docs/architecture.md docs/api.md docs/openapi.json docs/postman_collection.json docs/test-scenarios.md docs/demo.md credit-conveyor/backend/requirements.txt; do
  test -f "$path" || { printf 'FAIL: missing %s\n' "$path" >&2; exit 1; }
done
python3 scripts/check_contract.py
docker compose config --quiet
# A running, healthy demo is required: do not silently skip failed checks.
curl --fail --silent --show-error "$API_BASE_URL/health"
curl --fail --silent --show-error "$FRONTEND_BASE_URL/api/health"
curl --fail --silent --show-error "$API_BASE_URL/docs" -o /dev/null
python3 scripts/check_contract.py --live --base-url "$API_BASE_URL"
docker compose exec -T backend python -m pytest -q
printf '\nPASS: submission artifacts, Swagger, API schema and backend tests\n'
printf 'Frontend build/tests: pnpm install --frozen-lockfile && pnpm build && pnpm test\n'
printf 'API collection (creates a synthetic application): python3 scripts/run_collection.py\n'
