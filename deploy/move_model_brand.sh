#!/usr/bin/env bash
set -euo pipefail

# Run the Django management command inside the API container (prod).
# Usage examples:
#   ./deploy/move_model_brand.sh --model "VacuMax" --from-brand "Precision Medical" --to-brand "DevilBiss"
#   ./deploy/move_model_brand.sh --model "VacuMax" --from-brand "Precision Medical" --to-brand "DevilBiss" --force-merge-types

docker compose -f docker-compose.prod.yml exec -T api \
  python manage.py move_model_brand "$@"
