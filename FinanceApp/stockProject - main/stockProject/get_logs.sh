#!/usr/bin/env bash
set -euo pipefail

# Skąd bierzemy logi (montowane w compose do /logs)
SRC_DIR="${1:-./logs}"          # domyślnie lokalny mount z compose
OUT_DIR="${2:-./artifacts}"     # gdzie zrzucić paczkę

TS="$(date -u +'%Y%m%dT%H%M%SZ')"
DEST="${OUT_DIR}/${TS}"
mkdir -p "$DEST"

if [ ! -d "$SRC_DIR" ]; then
  echo "Brak katalogu z logami: ${SRC_DIR}"
  exit 1
fi

# Zbierz wszystko co JSONL/CSV z bieżącej sesji
find "$SRC_DIR" -maxdepth 1 -type f \( -name '*.jsonl' -o -name '*.csv' \) -print0 | xargs -0 -I{} cp "{}" "$DEST" || true

# Dla wygody także md5sum
( cd "$DEST" && ls -1 | xargs -I{} sh -c 'md5sum "{}" || true' ) > "$DEST/checksums.md5" || true

# Spakuj
TAR="${OUT_DIR}/logs_${TS}.tar.gz"
tar -C "$OUT_DIR" -czf "$TAR" "$(basename "$DEST")"

echo "Zebrano logi → ${DEST}"
echo "Archiwum → ${TAR}"
