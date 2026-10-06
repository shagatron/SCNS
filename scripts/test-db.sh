#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Only provisions the dedicated local Compose test database; never drops data.
exists=$(docker compose exec -T db psql -U scns -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='scns_test'")
if [[ "$exists" != "1" ]]; then
  docker compose exec -T db createdb -U scns scns_test
fi
