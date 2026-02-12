#!/usr/bin/env bash
set -euo pipefail

# Run the Django management command inside the API container (prod).
# Usage examples:
#   ./deploy/move_model_brand.sh --model "VacuMax" --from-brand "Precision Medical" --to-brand "DevilBiss"
#   INTERNET=1 ./deploy/move_model_brand.sh --model "VacuMax" --from-brand "Precision Medical" --to-brand "DevilBiss"
#   ./deploy/move_model_brand.sh --model "VacuMax" --from-brand "Precision Medical" --to-brand "DevilBiss" --force-merge-types

compose_file="docker-compose.prod.yml"
env_file="${ENV_FILE:-.env.prod}"
if [[ "${INTERNET:-0}" == "1" ]]; then
  compose_file="docker-compose.prod.internet.yml"
  env_file="${ENV_FILE:-.env.prod.internet}"
fi

docker compose --env-file "${env_file}" -f "${compose_file}" exec -T api \
  python manage.py move_model_brand "$@"
