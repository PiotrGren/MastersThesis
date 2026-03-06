# StockProject – szybki powrót po przerwie (Docker Compose + Locust)

Krótki checklist: jak postawić stack i jak uruchamiać scenariusze testów z `parameters.txt`.

## 0) Wymagania
- Docker + Docker Compose (plugin)
- Odpalasz komendy w katalogu projektu (tam gdzie `docker-compose.yaml`, `.env`, `start_test.sh`, `parameters.txt`).

## 1) Start aplikacji (DB + Redis + API + Celery)
To są serwisy **bez profilu `load`**:

```bash
docker compose up -d db redis api worker beat
```

Szybkie sprawdzenie:
```bash
docker compose ps
docker compose logs -f api
```

## 2) Testy obciążeniowe (Locust + Monitor) – scenariusze z `parameters.txt`
Locust i monitor są w profilu `load`. Najprościej uruchamiasz jeden skrypt:

```bash
chmod +x start_test.sh
./start_test.sh parameters.txt
```

Ten skrypt:
1) uruchamia `monitor` w tle
2) odpala kolejne scenariusze jako `docker compose --profile load run --rm locust ...`
3) na końcu zatrzymuje `monitor`

### Locust nie kończy się po czasie (TIME)
Jeśli w logu Locusta widzisz:
> `No run time limit set, use CTRL+C to interrupt`

to znaczy, że zmienna `TIME` nie dotarła do kontenera (albo jest pusta), więc Locust nie dostał `--run-time`.

Szybki test:
```bash
docker compose --profile load run --rm -e TIME="10s" locust
```

Jeśli to działa, to problem jest w tym, jak `start_test.sh` czyta `TIME` z `parameters.txt` (np. header/CRLF/pusta kolumna).

## 3) Gdzie są logi?
Najczęściej wszystko ląduje w `./logs` (bind mount do `/logs` w kontenerach):
- backend: `logs/request_log.jsonl`, `logs/error_log.jsonl` (zależnie od konfiguracji middleware)
- monitor: `logs/system_metric.jsonl`
- locust: `logs/locust_*.csv` i opcjonalny `locust_client_log.jsonl`

Podgląd na żywo:
```bash
tail -f logs/request_log.jsonl
tail -f logs/system_metric.jsonl
```

## 4) Stop / sprzątanie
Zatrzymanie wszystkiego:
```bash
docker compose down
```

Usunięcie wolumenów (UWAGA: kasuje dane Postgresa):
```bash
docker compose down -v
```

## 5) Najczęstsze potknięcia
- **TIME/SCENARIO_ID/RATES_N “nie działa”** → sprawdź, czy `start_test.sh` na pewno przekazuje je jako `-e ...` do `docker compose run`.
- **Monitor ma działać tylko podczas testów** → nie uruchamiaj `--profile load up` ręcznie, tylko przez `start_test.sh`.
