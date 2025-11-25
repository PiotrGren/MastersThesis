#!/usr/bin/env bash
set -euo pipefail

# --- Konfiguracja z ENV ---
: "${LOCUST_HOST:=http://localhost:8000}"        # np. http://api:8000 w compose
: "${USERS:=50}"                                  # liczba wirtualnych userów
: "${SPAWN_RATE:=5}"                              # przyrost userów / sekundę
: "${TIME:=}"                                   # czas testu (np. 5m, 30s, 1h)
: "${LOCUST_CLASSES:=ReadOnlyUser,ActiveBuyer,ActiveSeller}"  # klasy z locustfile.py
: "${LOG_DIR:=/logs}"                             # wspólny wolumen na logi/csv
: "${TIME_BETWEEN_REQUESTS_MIN:=0.5}"
: "${TIME_BETWEEN_REQUESTS_MAX:=1.5}"
: "${RATES_N:=3}"

mkdir -p "$LOG_DIR"

# --- Uruchomienie Locusta (headless) ---
exec locust \
  --headless \
  --host "$LOCUST_HOST" \
  -u "$USERS" \
  -r "$SPAWN_RATE" \
  --csv="$LOG_DIR/locust" \
  --only-summary \
  --loglevel INFO
