#!/bin/bash

# Ścieżka do pliku z parametrami
param_file="parametry.txt"

# Sprawdzenie, czy plik istnieje
if [ ! -f "$param_file" ]; then
  echo "Plik z parametrami $param_file nie istnieje!"
  exit 1
fi

# Inicjalizacja licznika
counter=1

# Iteracja przez każdy wiersz (zestaw parametrów) w pliku
while IFS= read -r params; do
  # Sprawdzenie, czy wiersz nie jest pusty
  if [[ -z "$params" ]]; then
    continue
  fi

  echo "Uruchamiam Dockera z parametrami: $params"

  # Rozdzielenie parametrów oddzielonych przecinkami
  IFS=',' read -r -a param_array <<< "$params"

  # Przekazanie parametrów do skryptu Docker (użycie cudzysłowów, aby zachować spacje w argumentach)
  ./generate_docker-compose.sh "${param_array[@]}"

  # Czekaj
  echo "Oczekiwanie"
  sleep 4200

  # Zatrzymanie kontenerów
  echo "Zatrzymuję kontenery..."
  docker-compose -f docker-compose.generated.yml down

  # Pobranie logów za pomocą skryptu get-logs.sh, z numerem iteracji w nazwie pliku
  echo "Pobieranie logów i zapisywanie do pliku: logdatabase_test$counter.sql"
  ./get_logs.sh "$counter"

  # Zwiększenie licznika
  counter=$((counter + 1))

  # Po zakończeniu iteracji dla tego zestawu parametrów
  docker-compose -f docker-compose.generated.yml down -v
  echo "Zakończono przetwarzanie zestawu parametrów: $params"
done < "$param_file"

echo "Wszystkie testy zostały zakończone."