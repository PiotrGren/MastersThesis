# Specyfikacja Pipeline'u Treningowego: BiLSTM Fusion

Dokument definiuje wymagania funkcjonalne, architekturę procesu trenowania oraz strukturę konfiguracji dla modelu `BiLSTMFusion`.

## 1. Założenia Architektoniczne

* **Model:** `BiLSTMFusion` (zdefiniowany w `bilstm_fusion.py`). Nie modyfikujemy kodu modelu.
* **Wejście:** Skrypt trenujący (`train_net.py`) przyjmuje parametry z pliku konfiguracyjnego YAML oraz argumenty CLI.
* **Sterowanie:** Proces uczenia oparty na **iteracjach** (krokach), a nie epokach. Zbiór danych jest zapętlony (*Infinite Data Loader*).
* **Środowisko:** Obsługa CPU i GPU (konfigurowalna liczba urządzeń).

## 2. Wymagania Funkcjonalne (`train_net.py`)

### A. Interfejs Użytkownika (CLI)
Skrypt uruchamiany z konsoli z następującymi flagami:
* `--config`: Ścieżka do pliku `.yaml` (wymagane).
* `--resume`: Flaga wznawiająca trening z ostatniego checkpointu w `OUTPUT_DIR`.
* `--num-gpus`: Liczba GPU (domyślnie 1, 0 = CPU).

### B. Przebieg Treningu
1.  **Inicjalizacja:** Utworzenie katalogu wyjściowego (`outputs/`), wczytanie konfiguracji, budowa modelu i optymalizatora.
2.  **Pętla Uczenia:**
    * Trening trwa do osiągnięcia `MAX_ITER`.
    * Model pobiera batch o wielkości `USR_PER_BATCH` (liczba użytkowników/sesji).
3.  **Scheduler:** Zmiana `BASE_LR` w zadanych krokach (`STEPS`) oraz faza rozgrzewki (`WARMUP_ITERS`).

### C. Logowanie i Metryki
Wszystkie logi trafiają do `OUTPUT_DIR`:
1.  **CLI (Terminal):** Logowanie co `LOG_PERIOD` iteracji. Wyświetla: iterację, loss, lr, ETA (szacowany czas końca).
2.  **`log.txt`:** Kopia wszystkiego, co pojawia się w CLI + pełne stacktrace błędów.
3.  **`metrics.json`:** Plik append-only, gdzie każda linia to obiekt JSON z metrykami z danej iteracji (łatwe parsowanie do wykresów).

### D. Checkpointy i Ewaluacja
1.  **Checkpointing:**
    * Zapis co `CHECKPOINT_PERIOD`.
    * Plik `last_checkpoint.pth` (nadpisywany) zawiera: wagi modelu, stan optymalizatora, stan schedulera, numer iteracji.
2.  **Ewaluacja (Walidacja):**
    * Uruchamiana co `EVAL_PERIOD`.
    * Model zamrażany (`eval()`), przeliczany zbiór walidacyjny.
    * Jeśli wynik jest najlepszy w historii -> zapis `model_best.pth`.
3.  **Finalizacja:**
    * Po zakończeniu treningu zapis `model_final.pth` w podkatalogu `final/`.

---

## 3. Struktura Pliku Konfiguracyjnego (`config.yaml`)

Poniżej znajduje się wzorcowa struktura pliku konfiguracyjnego.

```yaml
# ==============================================================================
# CONFIG: BiLSTM Fusion Training
# ==============================================================================

# --- USTAWIENIA SYSTEMOWE I ŚCIEŻKI ---
SYSTEM:
  OUTPUT_DIR: "./outputs/experiment_01_baseline"  # Gdzie zapisywać logi i modele
  DEVICE: "cuda"                                  # "cuda" lub "cpu" (nadpisywane przez --num-gpus)
  SEED: 42                                        # Ziarno losowości dla powtarzalności

# --- DANE ---
DATA:
  TRAIN_PATH: "./data/processed/train_data.pt"    # Ścieżka do przetworzonych tensorów treningowych
  VAL_PATH: "./data/processed/val_data.pt"        # Ścieżka do danych walidacyjnych
  VOCAB_PATH: "./data/processed/vocab.json"       # Słownik mapujący endpoint -> int
  NUM_WORKERS: 4                                  # Liczba wątków ładowania danych

# --- ARCHITEKTURA MODELU (BiLSTMFusionConfig) ---
MODEL:
  HIDDEN_DIM: 192           # Rozmiar stanu ukrytego LSTM
  LAYERS: 1                 # Liczba warstw LSTM
  DROPOUT: 0.25             # Dropout ogólny
  ATTN_DROPOUT: 0.1         # Dropout w mechanizmie uwagi
  BIDIRECTIONAL: True
  USE_ATTENTION: True
  NUM_CLASSES: 3            # Active, ReadOnly, ActiveAnalyst

# --- PARAMETRY TRENINGU (SOLVER) ---
SOLVER:
  OPTIMIZER: "AdamW"
  BASE_LR: 0.001            # Podstawowy Learning Rate
  WEIGHT_DECAY: 0.0001      # Regularyzacja L2
  CLIP_GRADIENTS: 1.0       # Przycinanie gradientów (ważne dla LSTM!)
  
  MAX_ITER: 5000            # Całkowita liczba iteracji treningowych
  USR_PER_BATCH: 32         # Batch size (liczba unikalnych sesji/użytkowników na krok)
  
  # Scheduler (MultiStepLR z Warmupem)
  STEPS: [3000, 4500]       # Kiedy zmniejszyć LR (np. o czynnik 0.1)
  GAMMA: 0.1                # Mnożnik zmniejszania LR
  
  WARMUP_ITERS: 500         # Liczba iteracji rozgrzewkowych (liniowy wzrost LR)
  WARMUP_FACTOR: 0.001      # Startowy mnożnik dla warmupu

# --- CZĘSTOTLIWOŚĆ ZDARZEŃ ---
PERIODS:
  LOG_PERIOD: 20            # Co ile iteracji wypisywać status w CLI
  EVAL_PERIOD: 200          # Co ile iteracji uruchamiać walidację
  CHECKPOINT_PERIOD: 500    # Co ile iteracji zapisywać stan modelu