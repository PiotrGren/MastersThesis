# Pipeline danych do modelu BiLSTM (logi requestów + czasy)

Ten dokument jest **guideline/blueprint** przygotowania danych do modelu sekwencyjnego (BiLSTM z dwoma wejściami). Ma być aktualny nawet po przerwie w projekcie: opisuje **co** i **dlaczego** robimy, a nie konkretną implementację.

Zakładamy, że źródłem danych są logi generowane przez middleware (JSONL) i opcjonalnie DB, a zadaniem jest **klasyfikacja użytkowników** (np. ReadOnly / Active / ActiveWithMarketAnalyze) oraz później **anomalia/odchylenia** (fine-tuning, detekcja).

---

## 0. Cel pipeline’u i definicje

**Cel pipeline’u**: z surowych wpisów requestów stworzyć przykład uczący w postaci:

- `event_ids`: tensor `LongTensor [T]` – sekwencja zdarzeń (1 token na request),
- `time_feats`: tensor `FloatTensor [T, K]` – cechy czasowe na request (np. K=4),
- `length`: długość sekwencji (bez paddingu),
- `label`: etykieta klasy użytkownika (na etapie klasyfikacji),
- metadane: `user_id`, `session_id`, zakres czasu, `scenario_id`, `env` (do audytu i debug).

**Jednostka obserwacji** (wybór jest kluczowy):
- rekomendacja dla klasyfikacji: **sekwencje per `session_id`**, a jeśli sesje są za krótkie – sekwencje per `user_id` z oknem czasowym,
- rekomendacja dla anomalii: **sekwencje per session lub per window** (łatwiejsza detekcja „odstępstw” w ramach zachowania).

**Założenie**: logi posiadają co najmniej `user_id`, `session_id`, `timestamp`, `api_method`, `endpoint`, `endpoint_group`, `http_status`, `success`, oraz czasy: `latency_ms_total`, `db_time_ms`, `app_time_ms`. Jeśli któreś pole bywa `null`, pipeline musi mieć jasno określone fallbacki.

---

## 1. Ingest danych (źródła i format)

### 1.1 Źródła danych
Minimalny zestaw:
- `request_log.jsonl` – *główne źródło* (każda linia = 1 request).
- `error_log.jsonl` – uzupełniające (niekonieczne do klasyfikacji, przydatne do anomalii i jakości danych).

Opcjonalnie:
- tabele DB (jeśli chcesz weryfikować spójność lub dorabiać cechy).

### 1.2 Wczytanie i walidacja schematu
Krok po kroku:
1. Czytaj JSONL strumieniowo (żeby nie zabić RAM przy milionach rekordów).
2. Waliduj minimalne pola:
   - `timestamp` da się sparsować (UTC),
   - `user_id` i `session_id` nie są puste,
   - `endpoint` i `api_method` istnieją,
   - `latency_ms_total` jest liczbą dodatnią lub 0.
3. Jeśli rekord nie przechodzi walidacji:
   - oznacz jako `bad_record` i **odfiltruj** z datasetu treningowego,
   - zachowaj osobny raport (liczności, przykłady).

**Uwaga**: brakujące lub `null` w `db_time_ms`/`app_time_ms` – dopuszczalne, ale musisz mieć politykę uzupełnienia (patrz sekcja 4).

---

## 2. Czyszczenie i normalizacja semantyczna logów

### 2.1 Deduplikacja i spójność identyfikatorów
1. Jeśli zdarzają się duplikaty requestów (np. retry po stronie klienta/logera), deduplikuj po:
   - `request_id` (najlepiej),
   - ewentualnie `(timestamp, user_id, endpoint, api_method, latency_ms_total)` jako fallback.
2. Sprawdź spójność:
   - czy `session_id` nie miesza wielu `user_id` (powinno być 1:1 w obrębie testu),
   - czy `user_role` jest stałe per `user_id` (jeśli logujesz role).

### 2.2 Standaryzacja endpointów
Ważne dla budowy tokenów:
- Ujednolić końcowe slashe (`/api/buyoffers` vs `/api/buyoffers/`),
- Znormalizować endpointy z parametrami ścieżki:
  - np. `/api/buyoffers/123/` → `/api/buyoffers/<id>/`.
- Query parametry:
  - **nie** wkładaj całego query do tokenu wprost (zbyt duża wariancja),
  - zamiast tego stwórz *bucket* lub flagę (np. `n_bucket` dla `/rates/?n=...`).

---

## 3. Definicja etykiet (labels) i problemu uczenia

### 3.1 Klasyfikacja użytkowników (supervised)
Etykietę możesz wyprowadzać na 2 sposoby:
1. **Z nagłówka / pola logu** `user_class` (np. z Locusta): najprostsze i stabilne.
2. **Z `scenario_id`** (jeśli scenario jednoznacznie mapuje na typ użytkownika).

Rekomendacja: bazuj na `user_class` jako prawdzie etykietującej (bo to dokładnie to chcesz później przewidywać).

### 3.2 Anomalie (później)
Etykietowanie anomalii:
- dla „sterowanych anomalii” (FundsInjector itd.) – label z `scenario_id`,
- dla „nienadzorowanych” – budowa zbioru walidacyjnego i definicja thresholdów (osobny etap).

---

## 4. Cechy czasowe (time_feats) – co liczymy i jak

Model ma osobne wejście czasowe na każdy request. Proponowany zestaw K=4:

1. `latency_ms_total` (czas całkowity requestu)
2. `db_time_ms`
3. `app_time_ms`
4. `delta_t_ms` – różnica między bieżącym a poprzednim requestem w tej samej sekwencji

### 4.1 Uzupełnianie braków
Polityka:
- jeśli `db_time_ms` jest `null` → traktuj jako 0 i dodaj opcjonalną flagę `db_missing` (jeśli chcesz K=5),
- jeśli `app_time_ms` jest `null`, a masz `latency_ms_total` i `db_time_ms` → `app = max(latency - db, 0)`,
- jeśli `delta_t_ms` dla pierwszego requestu w sekwencji → 0.

### 4.2 Transformacje skali
Czasy mają rozkład z długim ogonem. Stabilne podejście:
- stosuj `log1p(x)` na wszystkich czasach (`log1p(latency)`, `log1p(db)`, `log1p(app)`, `log1p(delta_t)`),
- następnie standaryzacja (mean/std) liczona **tylko na train**,
- te same parametry normalizacji używane dla val/test.

**Dlaczego**: LSTM uczy się stabilniej, mniejsza wrażliwość na outliery.

---

## 5. Budowa tokenów sekwencyjnych (event_ids)

### 5.1 Co jest „zdarzeniem” (event)
Każdy request mapujesz na jeden dyskretny token `event_id`.

Rekomendowany skład tokenu (wariant baseline, solidny):
- `endpoint_group`
- `api_method`
- `http_status_bucket` (np. 2xx, 3xx, 4xx, 5xx)
- `success` (0/1)

Przykład string-key:
`"BUY|POST|2xx|1"`

Opcjonalne rozszerzenia (po baseline):
- `scenario_id` (czasem pomaga, ale może przeciekać etykietę – używać ostrożnie),
- `endpoint_template` (np. `/api/buyoffers/<id>/`),
- bucket `response_size` lub `latency_bucket`.

### 5.2 Słownik (vocab) i OOV
1. Zbierz częstości tokenów na train.
2. Zdefiniuj:
   - `PAD=0` (padding),
   - `UNK=1` (nieznane).
3. Odetnij rzadkie tokeny (np. `<min_freq=5`) → idą do `UNK`.
4. Zamroź vocab po zbudowaniu na train.

**Dlaczego**: stabilność, brak eksplozji vocab na query/ID.

---

## 6. Segmentacja na sekwencje (sessionizacja / okna)

### 6.1 Wariant A: sekwencje per session_id (rekomendowane)
Kroki:
1. Grupuj rekordy po `session_id` (i upewnij się, że to 1 użytkownik).
2. Sortuj rosnąco po `timestamp`.
3. Buduj sekwencję `T`:
   - `event_ids[t]` z tokenu,
   - `time_feats[t]` z cech czasowych + `delta_t`.
4. Odrzuć sekwencje zbyt krótkie (np. `T<5`), bo są mało informacyjne.

Zalety: czytelna jednostka zachowania; łatwe debugowanie.

### 6.2 Wariant B: okna per user_id (gdy sesje są za długie/krótkie)
Jeśli masz wielogodzinne sesje lub bardzo krótkie sesje:
- buduj okna stałej długości `T_max` z krokiem (stride), np. `T_max=128`, `stride=64`,
- albo okna czasowe (np. 10 minut).

Zalety: więcej próbek, lepsza równowaga klas, stabilne batchowanie.

### 6.3 Długości i padding
Ustal `T_max` (np. 128 albo 256):
- jeśli sekwencja > `T_max` → tnij (albo rób sliding windows),
- jeśli sekwencja < `T_max` → padding `event_id=PAD` i `time_feats=0`.

Zapisz realną długość `length`.

---

## 7. Split danych (train/val/test) bez przecieku

Najważniejsza zasada: **nie mieszać tego samego usera/sesji między splitami**.

Rekomendacja:
- splituj po `user_id` (najbezpieczniej), a nie po rekordach,
- jeśli uczysz per session – też pilnuj, żeby wszystkie sesje usera były w jednym splicie.

Przykładowy podział:
- Train 70%
- Val 15%
- Test 15%

Dodatkowo:
- utrzymuj rozkład klas (stratyfikacja po klasie na poziomie usera).

---

## 8. Balans klas i strategie próbkowania

Jeśli klasy są nierówne:
- w DataLoaderze użyj `WeightedRandomSampler` albo reważenia loss,
- albo kontroluj proporcje klas na poziomie generowania logów (to już zrobiłeś Locustem).

W pracy warto opisać: *skąd bierze się imbalance i jak go kontrolujesz*.

---

## 9. Format datasetu na dysku (do szybkiego treningu)

Dla dużych danych:
- po wstępnym przetworzeniu zapisz dataset w formacie binarnym:
  - `pt`/`npz`/`parquet` (zależnie od stacku),
- przechowuj:
  - `event_ids` (int16/int32),
  - `time_feats` (float32, ewentualnie float16),
  - `lengths`,
  - `labels`,
  - metadane indeksu (mapowanie sample → user/session).

To pozwala trenować wielokrotnie bez ponownego parsowania JSONL.

---

## 10. Kontrola jakości (Quality Gates)

Przed treningiem generuj raport:
- liczba rekordów wejściowych,
- ile odrzucono (invalid/missing),
- rozkład długości sekwencji,
- rozkład klas,
- top tokeny eventów,
- percentyle czasów (latency/db/app/delta),
- odsetek 4xx/5xx.

**Cel**: wykryć regresje (np. zły mapping endpointów, brak scenario_id, itp.).

---

## 11. Dane do anomalii – przygotowanie kompatybilne z tym samym modelem

Żeby później robić fine-tuning/anomaly:
- używaj tej samej definicji `event_id` i tych samych cech `time_feats`,
- zachowaj identyczną normalizację (mean/std z baseline),
- twórz osobne zbiory:
  - „normal” (klasy użytkowników bez anomalii),
  - „anomaly” (FundsInjector + inne).

Dzięki temu jeden model i jeden pipeline mogą obsłużyć oba etapy.

---

## 12. Co musi być opisane w pracy / prezentacji

W części pisemnej i slajdach warto mieć jasno:
- źródła danych (JSONL, middleware),
- definicję zdarzenia i cech czasowych,
- definicję sekwencji (session/user window),
- normalizację i padding,
- split bez przecieków,
- kontrolę jakości.

To daje spójny, „naukowy” opis pipeline’u.
