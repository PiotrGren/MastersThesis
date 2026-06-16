# Guideline modelu: BiLSTM z fuzją zdarzeń i czasu (PyTorch)

Ten dokument opisuje **architekturę** oraz **uzasadnienie** modelu w kontekście projektu: klasyfikacja typów użytkowników na podstawie logów requestów (sekwencje) oraz charakterystyk czasowych requestów.

Model jest zaprojektowany jako solidny baseline do:
1) klasyfikacji użytkowników (supervised),
2) późniejszego rozszerzenia o anomalię (fine-tuning / detekcja odchyleń).

---

## 1. Problem modelowania

Dane są sekwencją zdarzeń API generowanych przez użytkownika:
- każde zdarzenie to request do określonego endpointu/metody,
- każde zdarzenie ma parametry czasowe: opóźnienie całkowite, czas DB, czas aplikacji, odstęp czasowy do poprzedniego requestu.

W projekcie kluczowe jest rozpoznanie **stylu zachowania** użytkownika:
- ReadOnly: dominują GETy, mało mutacji,
- Active: trading, BUY/SELL, cancel, info,
- ActiveWithMarketAnalyze: trading + intensywne “market read” (rates, money-check).

To jest klasyczny problem **sekwencyjny**, gdzie:
- kolejność zdarzeń ma znaczenie,
- zależności czasowe (delta_t, latency) niosą dodatkowy sygnał.

---

## 2. Wejścia modelu

Model przyjmuje dwa wejścia zsynchronizowane po czasie (na każdy request):

### 2.1 `event_ids` – dyskretne tokeny zdarzeń
Tensor `LongTensor [B, T]`, gdzie `T` to długość sekwencji (po paddingu).

`event_id` to zakodowana informacja o typie requestu, zwykle połączenie:
- `endpoint_group`,
- `api_method`,
- `status_bucket`,
- `success`.

**Uzasadnienie**: zachowanie użytkownika to przede wszystkim wzorzec „jakie akcje i w jakiej kolejności”.

### 2.2 `time_feats` – cechy czasowe per request
Tensor `FloatTensor [B, T, K]`, np. K=4:
- `log1p(latency_ms_total)`,
- `log1p(db_time_ms)`,
- `log1p(app_time_ms)`,
- `log1p(delta_t_ms)`.

**Uzasadnienie**: dwaj użytkownicy mogą robić podobne requesty, ale w innym tempie i z innym profilem obciążenia (np. market-analyze generuje inne wzorce czasowe).

### 2.3 `lengths` / maska
Długości sekwencji są różne, więc model używa maski i packowania sekwencji, aby:
- nie uczyć się paddingu,
- poprawnie poolować reprezentację.

---

## 3. Embedding i fuzja informacji

### 3.1 Embedding zdarzeń
Warstwa `Embedding(vocab_size, event_embed_dim)` mapuje `event_ids` na wektory `[B, T, E]`.

**Uzasadnienie**:
- embedding uczy się podobieństw między zdarzeniami (np. różne endpointy z grupy BUY),
- zmniejsza sparsity w porównaniu do one-hot.

### 3.2 Kodowanie cech czasowych
Cechy czasowe `[B, T, K]` przechodzą przez mały MLP (TimeMLP) → `[B, T, Te]`.

**Uzasadnienie**:
- czas jest ciągły, więc MLP jest naturalnym „feature encoderem”,
- działa per krok, więc zachowuje informację sekwencyjną (nie uśredniamy po całej sekwencji).

### 3.3 Fuzja per krok
Wektory embeddingu zdarzeń i embeddingu czasu są konkatenowane:
- `x_t = [e_t ; t_t]` → `[B, T, E+Te]`,
następnie stabilizowane `LayerNorm` i `Dropout`.

**Uzasadnienie**:
- model dostaje pełny opis *co się wydarzyło* i *w jakim profilu czasowym* w każdym kroku,
- to zwiększa separowalność klas (np. „czytam rynek szybko” vs „handluję rzadko”).

---

## 4. Enkoder sekwencji: BiLSTM

### 4.1 Dlaczego LSTM?
LSTM dobrze radzi sobie z:
- zależnościami sekwencyjnymi,
- różnymi długościami sekwencji,
- relatywnie małymi zbiorami (w porównaniu do Transformerów),
- szybkim treningiem jako baseline.

W Twoim projekcie ważny jest **solidny model startowy** do testów i iteracji.

### 4.2 Dlaczego bidirectional?
BiLSTM analizuje sekwencję w przód i w tył:
- w praktyce dla klasyfikacji zachowania to pomaga, bo model „widzi kontekst” całej sekwencji,
- przy poolingach (attention) to często daje lepszą reprezentację globalną.

### 4.3 Packowanie sekwencji
Użycie `pack_padded_sequence` i `pad_packed_sequence` sprawia, że:
- padding nie jest przetwarzany jako realne dane,
- gradienty i stany nie są zaburzone przez „zera”.

To kluczowe przy danych z Locusta, gdzie długości sesji bywają zmienne.

---

## 5. Agregacja po czasie: Attention pooling

Po BiLSTM otrzymujemy `H = [B, T, D]`. Musimy zamienić sekwencję na jeden wektor `[B, D]`.

### 5.1 Dlaczego nie „ostatni krok”?
Ostatni request w sesji:
- może być przypadkowy,
- może nie zawierać informacji o typie użytkownika (np. końcowy GET /info).

### 5.2 Attention pooling – idea
Model uczy się wag `a_t` dla kroków w czasie, a reprezentacja to:
- `h = sum_t a_t * H_t`,
z maską wycinającą padding.

**Uzasadnienie w Twoim kontekście**:
- klasa `ActiveWithMarketAnalyze` może być rozpoznawana po „ważnych” fragmentach (seria rates + buy/sell),
- attention pozwala modelowi skupić się na diagnostycznych zdarzeniach.

### 5.3 Alternatywa: maskowany mean pooling
W baseline lub ablacjach można użyć mean pooling:
- szybciej,
- mniej parametrów,
- ale często gorsze wyniki.

W projekcie warto opisać to jako wariant porównawczy.

---

## 6. Głowica klasyfikacyjna (classification head)

Reprezentacja `[B, D]` przechodzi przez:
- `LayerNorm` (stabilizacja),
- `Linear → GELU → Dropout`,
- `Linear → num_classes`.

**Uzasadnienie**:
- normowanie pomaga przy zmiennych rozkładach danych,
- dropout ogranicza przeuczenie,
- GELU jest stabilne i często lepsze od ReLU w modelach sekwencyjnych.

Wyjściem są **logity** `[B, C]`. Do treningu używasz `CrossEntropyLoss`.

---

## 7. Dlaczego ta architektura pasuje do projektu

### 7.1 Zgodność z naturą danych
- logi są sekwencją zdarzeń → LSTM/BiLSTM jest naturalnym wyborem,
- czasy per request niosą dodatkową informację → osobny encoder czasów i fuzja per krok.

### 7.2 Odporność na zmienną długość i padding
- packowanie + maska + pooling → model działa stabilnie dla sesji o różnej długości,
- to ważne, bo Locust generuje ruch o różnej intensywności zależnie od scenariusza.

### 7.3 Interpretowalność i „story” do magisterki
- attention daje możliwość analizy: „które requesty były najbardziej istotne dla predykcji”,
- to bardzo dobrze wygląda w pracy i prezentacji (case study, heatmapy wag attention).

### 7.4 Baseline do późniejszych etapów
- po klasyfikacji użytkowników możesz:
  - fine-tunować model pod anomalię,
  - dodać dodatkowe głowice (multi-task),
  - przejść na Transformer – mając silny punkt odniesienia.

---

## 8. Co warto opisać jako eksperymenty/ablacje

W pracy i eksperymentach sensowne porównania:
1. tylko `event_ids` (bez czasów) vs fuzja z czasami,
2. BiLSTM vs jednokierunkowy LSTM,
3. attention pooling vs mean pooling,
4. różne definicje tokenu `event_id` (z/bez status_bucket, z/bez scenario_id).

To daje mocny, naukowy materiał do rozdziału „Eksperymenty i analiza”.

---

## 9. Zalecenia praktyczne do treningu (bez kodu)

- Normalizacja czasów: log1p + standaryzacja (z train).
- Split bez przecieków: po `user_id`.
- Class imbalance: wagi klas lub sampler.
- Długość sekwencji: ustalić `T_max` i stosować windows, jeśli trzeba.
- Metryki: accuracy, macro-F1 (dla nierównych klas), confusion matrix.

---

Ten opis jest celowo „dokumentacyjny” i długowieczny: masz tu komplet założeń i uzasadnień, które możesz bezpośrednio przenieść do rozdziału metod oraz na slajdy prezentacji.
