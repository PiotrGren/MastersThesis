#!/usr/bin/env bash
set -euo pipefail

PARAM_FILE="${1:-parameters.txt}"
PROFILE="load"

if [ ! -f "$PARAM_FILE" ]; then
  echo "Brak pliku z parametrami: $PARAM_FILE"
  exit 1
fi

echo "=== Uruchamiam monitor ==="
docker compose --profile "$PROFILE" up -d monitor

SCENARIO_NUM=1

while IFS=',' read -r SCENARIO_ID USERS SPAWN_RATE TIME CLASSES WAIT_MIN WAIT_MAX RATES_N; do
  # pomijamy puste linie i komentarze
  [[ -z "$SCENARIO_ID" ]] && continue
  [[ "$SCENARIO_ID" =~ ^# ]] && continue

  echo
  echo "=== [${SCENARIO_NUM}] SCENARIUSZ: $SCENARIO_ID ==="
  echo "USERS=$USERS SPAWN_RATE=$SPAWN_RATE TIME=$TIME CLASSES=$CLASSES WAIT=${WAIT_MIN}-${WAIT_MAX} RATES_N=$RATES_N"

  # Odpalamy locusta jako jednorazowy run; kontener sam się usunie po zakończeniu
  docker compose --profile "$PROFILE" run --rm \
    -e USERS="$USERS" \
    -e SPAWN_RATE="$SPAWN_RATE" \
    -e TIME="$TIME" \
    -e LOCUST_CLASSES="${CLASSES//:/,}" \
    -e TIME_BETWEEN_REQUESTS_MIN="$WAIT_MIN" \
    -e TIME_BETWEEN_REQUESTS_MAX="$WAIT_MAX" \
    -e RATES_N="$RATES_N" \
    -e SCENARIO_ID="$SCENARIO_ID" \
    locust

  echo "=== Scenariusz $SCENARIO_ID zakończony ==="
  SCENARIO_NUM=$((SCENARIO_NUM+1))

done < "$PARAM_FILE"

echo
echo "=== Wszystkie scenariusze zakończone. Zatrzymuję monitor. ==="
docker compose --profile "$PROFILE" stop monitor

echo "Gotowe. Locust i monitor są zatrzymane."
