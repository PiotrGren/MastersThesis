# Sprawozdanie z Postępów Prac: Implementacja Pipeline'u ML i Modelu BiLSTM Fusion

**Temat:** Klasyfikacja behawioralna użytkowników systemu giełdowego przy użyciu hybrydowych sieci rekurencyjnych.
**Data:** 23.01.2026
**Autor:** Piotr Greń

---

## 1. Metodyka Zbierania Danych (Data Collection)

W celu wytrenowania modelu uczenia maszynowego, zamiast polegać na syntetycznie generowanych wektorach losowych, przeprowadzono pełną symulację środowiska giełdowego przy użyciu narzędzia **Locust**. Podejście to pozwoliło na odwzorowanie realistycznych zależności czasowych i logicznych w zachowaniu użytkowników.

Proces zbierania danych oparto na następujących filarach:

* **Scenariusze Behawioralne:** Zaimplementowano klasy użytkowników symulujących różne strategie:
    * `ActiveUser`: Trader dokonujący częstych transakcji kupna/sprzedaży.
    * `ReadOnlyUser`: Użytkownik pasywny, generujący ruch odczytu (monitoring cen), ale minimalny ruch transakcyjny.
    * `ActiveUserWithMarketAnalize`: Zaawansowany bot wykonujący analizę rynku (pobranie kursów $\to$ analiza portfela $\to$ decyzja transakcyjna typu *burst*).
* **Inicjalizacja Rynku (Bootstrapping):** Aby wyeliminować problem „zimnego startu”, wprowadzono mechanizm **„Airdrop”** oraz losową alokację portfela początkowego. Dzięki temu użytkownicy od pierwszej sekundy posiadają zróżnicowane zasoby (akcje/gotówka), co umożliwia natychmiastowe zawieranie transakcji.
* **Wymuszanie Błędów Biznesowych:** Zbalansowano ekonomię symulacji (ceny akcji vs. portfel startowy) w taki sposób, aby statystycznie ok. 2-5% transakcji kończyło się błędami typu `Insufficient Funds` lub `Validation Error`. Stanowi to kluczową cechę dystynktywną dla modelu (np. odróżnienie bota, który „ślepo” ponawia zlecenia, od człowieka).
* **Middleware Logujący:** Całość ruchu HTTP oraz błędów aplikacyjnych jest przechwytywana przez dedykowany middleware w warstwie Django, który działa w trybie *non-blocking*, zapisując zdarzenia do strumieniowych plików logów.

---

## 2. Charakterystyka Zbioru Danych

W wyniku symulacji wygenerowano surowy zbiór danych składający się z dwóch skorelowanych strumieni w formacie JSONL:

1.  **`request_log.jsonl` (Główny strumień zdarzeń):**
    * Zawiera sekwencyjny zapis każdego żądania HTTP.
    * Kluczowe atrybuty: `session_id` (identyfikator sesji), `timestamp`, `endpoint_group` (zgeneralizowana kategoria, np. BUY, SELL, RATES), oraz metryki wydajnościowe: `latency_ms`, `db_time_ms`, `app_time_ms`.
    * Obecny wolumen: ~550 000 rekordów.
2.  **`error_log.jsonl` (Kontekst anomalii):**
    * Zawiera szczegółowe informacje o błędach (kod błędu, stacktrace, komunikat biznesowy).
    * Błędy są skorelowane z głównym logiem poprzez `request_id`, co pozwala na wzbogacenie sekwencji o informację, czy dana akcja zakończyła się sukcesem, czy porażką.

---

## 3. Architektura Modelu: BiLSTM Fusion

Zastosowano autorską architekturę hybrydową **BiLSTM Fusion**, która łączy przetwarzanie sekwencji zdarzeń (podejście NLP) z analizą wielowymiarowych szeregów czasowych. Poniżej przedstawiono opis koncepcyjny oraz techniczny.

### 3.1 Opis Intuicyjny (Koncepcja Działania)

Model działa na zasadzie analityka, który obserwuje sesję użytkownika „klatka po klatce”. W przeciwieństwie do prostych modeli statystycznych, BiLSTM Fusion analizuje dwa aspekty jednocześnie:

1.  **Aspekt Semantyczny (CO?):** Model widzi sekwencję czynności, np. *Sprawdzenie Ceny $\to$ Próba Kupna $\to$ Błąd Walidacji $\to$ Ponowna Próba*.
2.  **Aspekt Temporalny (JAK?):** Model otrzymuje informację o dynamice działania. Czy decyzja o kupnie nastąpiła 50ms po sprawdzeniu ceny (bot), czy 5 sekund później (człowiek)? Czy aplikacja działała wolno?

**Mechanizm Fuzji:** Informacje te są łączone (fusion), dzięki czemu sieć może nauczyć się złożonych korelacji, np.: *„Szybka seria zapytań `BUY` jest typowa dla bota, ale tylko jeśli odstępy czasu ($\Delta t$) są regularne i mniejsze niż 100ms”*.

**Dwukierunkowość i Uwaga:** Dzięki architekturze BiLSTM, model analizując środek sesji, zna jej kontekst zarówno z przeszłości, jak i przyszłości. Mechanizm uwagi (*Attention*) pozwala natomiast sieci zignorować szum (np. rutynowe odświeżanie strony) i skupić się na momentach kluczowych dla klasyfikacji (np. nagły wybuch aktywności transakcyjnej).

### 3.2 Opis Techniczny (Specyfikacja)

Architektura modelu składa się z następujących bloków różniczkowalnych:

1.  **Event Embedding:**
    * Wejście: Tensor indeksów zdarzeń $E \in \mathbb{R}^{B \times T}$ (gdzie $B$ to batch size, $T$ to długość sesji).
    * Transformacja: Warstwa `nn.Embedding` mapuje dyskretne ID endpointów na gęste wektory o wymiarze $D_{emb}$.
2.  **Time Encoder (MLP):**
    * Wejście: Tensor cech ciągłych $C \in \mathbb{R}^{B \times T \times 4}$. Cechy to: `latency`, `db_time`, `app_time` oraz $\Delta t$ (czas od poprzedniego zdarzenia).
    * Transformacja: Dwuwarstwowy perceptron (Linear $\to$ GELU $\to$ Linear) rzutuje cechy czasowe do tej samej przestrzeni wymiarowej co embeddingi zdarzeń.
3.  **Fusion Layer (Warstwa Fuzji):**
    * Następuje konkatenacja wektorów zdarzeń i czasu: $x_t = [e_t; c_t]$.
    * Zastosowano normalizację `LayerNorm` oraz `Dropout` w celu stabilizacji uczenia.
4.  **Sequence Encoder (BiLSTM):**
    * Rdzeń modelu stanowi dwukierunkowa sieć LSTM (Long Short-Term Memory). Przetwarza ona sekwencję w obu kierunkach, generując stany ukryte $h_t = [\vec{h_t}; \overleftarrow{h_t}]$.
5.  **Attention Pooling (Mechanizm Uwagi):**
    * Zamiast brać ostatni stan ukryty, model oblicza wagę ważności $\alpha_t$ dla każdego kroku czasowego $t$:
        $$\alpha_t = \text{softmax}(v^T \tanh(W h_t))$$
    * Ostateczna reprezentacja sesji $V$ jest ważoną sumą stanów ukrytych: $V = \sum_{t=1}^{T} \alpha_t h_t$.
6.  **Classification Head:**
    * Warstwa liniowa rzutująca wektor $V$ na liczbę klas (Active, ReadOnly, Analyst), zakończona funkcją Softmax/LogSoftmax.



---

## 4. Przetwarzanie Danych (`process_data.py`)

Zaimplementowano dedykowany pipeline ETL (Extract, Transform, Load), który przekształca surowe logi w tensory PyTorch.

**Przebieg procesu:**
1.  **Filtracja:** Usunięcie logów technicznych (np. endpointy `debug/airdrop`, healthchecki), które nie niosą wartości behawioralnej.
2.  **Integracja Błędów:** Algorytm łączy `error_log` z `request_log` używając klucza `request_id`. Dzięki temu błędy (np. brak środków) stają się jawnymi zdarzeniami w sekwencji sesji użytkownika.
3.  **Feature Engineering (Inżynieria Cech):**
    * Obliczenie **`delta_t`**: Różnica czasu między kolejnymi żądaniami w sesji.
    * **Log-Normalizacja:** Zastosowanie transformacji $x' = \ln(1 + x)$ na wszystkich cechach czasowych. Jest to krytyczne, aby zniwelować rzędy wielkości (np. 10ms vs 5000ms) i ułatwić zbieżność sieci neuronowej.
4.  **Tokenizacja:** Utworzenie słownika (`vocab.json`), mapującego unikalne pary `(Metoda, Endpoint Group)` na liczby całkowite.
5.  **Podział Danych (Splitting):** Podział na zbiory treningowy (80%), walidacyjny (10%) i testowy (10%) odbywa się na poziomie unikalnych **ID sesji**, co zapobiega wyciekowi danych (*data leakage*).

**Wynik:** Pliki `.pt` zawierające listy tensorów gotowych do ładowania przez `DataLoader`.

---

## 5. Pipeline Treningowy

Środowisko treningowe zostało zaprojektowane w paradygmacie konfigurowalnym (Data-Driven Configuration), typowym dla zaawansowanych frameworków badawczych.

**Kluczowe komponenty:**

* **`train_net.py` (Silnik Treningowy):** Skrypt CLI zarządzający procesem uczenia. Obsługuje wznawianie treningu (`--resume`) oraz wybór urządzenia (CPU/GPU).
* **`config.yaml` (Centralna Konfiguracja):** Plik definiujący wszystkie hiperparametry (Learning Rate, wymiary LSTM, Batch Size, ścieżki). Umożliwia łatwe uruchamianie wielu eksperymentów (Ablation Studies) bez modyfikacji kodu.
* **Dynamiczny DataLoader (`data_loader.py`):**
    * Zaimplementowano `InfiniteDataLoader` – trening oparty na liczbie iteracji, a nie epokach.
    * Wykorzystuje funkcję `collate_fn` do dynamicznego **paddingu** (dopełniania zerami) sekwencji o różnej długości wewnątrz batcha.
* **Solver i Metryki:**
    * Optymalizator: **AdamW** z regularyzacją wag.
    * Scheduler: **Warmup** (liniowy wzrost LR na początku) + **Step Decay** (redukcja LR w trakcie treningu).
    * Ewaluacja: Co zadaną liczbę kroków liczony jest **F1-Score (Macro)**, Precision, Recall oraz Accuracy. Najlepszy model jest automatycznie zapisywany jako `model_best.pth`.
    * Logowanie: Pełne logowanie przebiegu do pliku tekstowego oraz do formatu JSON (dla późniejszej wizualizacji wykresów).

Tak przygotowany pipeline zapewnia pełną reprodukowalność wyników i jest gotowy do przeprowadzenia właściwej fazy eksperymentalnej.