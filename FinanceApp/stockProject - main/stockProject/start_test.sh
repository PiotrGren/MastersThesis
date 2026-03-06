#!/usr/bin/env bash
set -euo pipefail

PARAM_FILE="${1:-parameters.txt}"
PROFILE="load"
BACKEND_SERVICE="api"

if [ ! -f "$PARAM_FILE" ]; then
  echo "Brak pliku z parametrami: $PARAM_FILE"
  exit 1
fi

echo "=== Uruchamiam monitor ==="
docker compose --profile "$PROFILE" up -d monitor

SCENARIO_NUM=1

# Pomijamy nagłówek i iterujemy po wierszach CSV
tail -n +2 "$PARAM_FILE" | while IFS=, read -r SCENARIO_ID USERS SPAWN_RATE TIME CLASSES WAIT_MIN WAIT_MAX RATES_N; do
  # Pomijamy puste / niekompletne linie (np. ucięty ostatni wiersz)
  if [ -z "${SCENARIO_ID:-}" ] || [ -z "${RATES_N:-}" ]; then
    echo ">>> Pomijam niekompletny wiersz w parameters.txt"
    continue
  fi

  echo
  echo "=========================================================="
  echo "=== [$SCENARIO_NUM] PRZYGOTOWANIE BAZY (CLEAN SLATE) ==="
  echo "=========================================================="

  # 1. Wyczyszczenie bazy (usuwa wszystkich userów, oferty, transakcje)
  # Uwaga: To nie usuwa plików JSONL z logami (one są bezpieczne na wolumenie/dysku)
  echo ">>> Czyszczenie bazy danych (flush)..."
  docker compose --profile "$PROFILE" exec -T $BACKEND_SERVICE python manage.py flush --no-input < /dev/null

  # 2. Ponowne utworzenie firm i kursów startowych
  echo ">>> Tworzenie rynku (bootstrap)..."
  docker compose --profile "$PROFILE" exec -T $BACKEND_SERVICE python manage.py bootstrap_market < /dev/null

  echo
  echo "=== [$SCENARIO_NUM] START SCENARIUSZA: $SCENARIO_ID ==="
  echo "USERS=$USERS SPAWN_RATE=$SPAWN_RATE TIME=$TIME CLASSES=$CLASSES"

  set +e
  docker compose --profile "$PROFILE" run --rm -T \
    -e USERS="$USERS" \
    -e SPAWN_RATE="$SPAWN_RATE" \
    -e TIME="$TIME" \
    -e LOCUST_CLASSES="${CLASSES//:/,}" \
    -e TIME_BETWEEN_REQUESTS_MIN="$WAIT_MIN" \
    -e TIME_BETWEEN_REQUESTS_MAX="$WAIT_MAX" \
    -e RATES_N="$RATES_N" \
    -e SCENARIO_ID="$SCENARIO_ID" \
    locust < /dev/null
  RC=$?
  set -e
  if [ "$RC" -ne 0 ]; then
    echo "!!! UWAGA: scenariusz $SCENARIO_ID zakończony kodem $RC (lecę dalej)"
  fi

  echo "=== Scenariusz $SCENARIO_ID zakończony ==="
  sleep 10
  SCENARIO_NUM=$((SCENARIO_NUM+1))
done

echo
echo "=== Wszystkie scenariusze zakończone. Zatrzymuję monitor. ==="
#docker compose --profile "$PROFILE" stop monitor locust
docker compose --profile "$PROFILE" down

echo "Gotowe. Locust i monitor są zatrzymane."
