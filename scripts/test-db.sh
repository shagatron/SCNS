#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Only provisions the dedicated local Compose test database; never drops data.
for test_database in scns_test scns_e2e_test scns_migration_test; do
  exists=$(docker compose exec -T db psql -U scns -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$test_database'")
  if [[ "$exists" != "1" ]]; then
    docker compose exec -T db createdb -U scns "$test_database"
  fi
done
