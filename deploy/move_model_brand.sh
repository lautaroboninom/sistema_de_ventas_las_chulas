#!/usr/bin/env bash
set -euo pipefail

# Run the Django management command inside the API container (prod).
# Usage examples:
#   ./deploy/move_model_brand.sh --model "VacuMax" --from-brand "Precision Medical" --to-brand "DevilBiss"
#   INTERNET=1 ./deploy/move_model_brand.sh --model "VacuMax" --from-brand "Precision Medical" --to-brand "DevilBiss"
#   ./deploy/move_model_brand.sh --model "VacuMax" --from-brand "Precision Medical" --to-brand "DevilBiss" --force-merge-types

compose_args=("-f" "docker-compose.prod.yml")
if [[ "${INTERNET:-0}" == "1" ]]; then
  compose_args=("-f" "docker-compose.prod.internet.yml")
fi

docker compose "${compose_args[@]}" exec -T api \
  python manage.py move_model_brand "$@"

