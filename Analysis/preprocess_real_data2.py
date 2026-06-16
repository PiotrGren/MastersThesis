import pandas as pd
import numpy as np
import torch
import json
from pathlib import Path
from tqdm import tqdm

# --- KONFIGURACJA ---
INPUT_CSV = "real_data/2020-Feb.csv" # Upewnij się, że to dobra ścieżka!
OUTPUT_DIR = Path("data_real_v2")    # ZMIANA: Nowy folder, żeby nie nadpisać starych danych!
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_SEQ_LEN = 200
MIN_EVENTS_IN_SESSION = 3  
N_ROWS_TO_READ = 3_000_000 

# Specjalne tokeny
PAD_TOKEN = "<PAD>"
UNK_TOKEN = "<UNK>"
CLS_TOKEN = "<CLS>"

def process_data():
    print(f"Wczytywanie pierwszych {N_ROWS_TO_READ} wierszy z {INPUT_CSV}...")
    # ZMIANA: Wczytujemy dodatkowo kolumnę 'price'
    df = pd.read_csv(INPUT_CSV, nrows=N_ROWS_TO_READ, usecols=["event_time", "event_type", "user_session", "price"])
    
    # ZMIANA: Zabezpieczenie przed brakującymi cenami (NaN -> 0.0)
    df["price"] = df["price"].fillna(0.0)
    
    # Czyszczenie i konwersja czasu
    df = df.dropna(subset=["user_session", "event_time"])
    df["event_time"] = pd.to_datetime(df["event_time"])
    df = df.sort_values(by=["user_session", "event_time"])

    # Budowa słownika (Vocab)
    unique_events = ["view", "cart", "remove_from_cart"]
    vocab = {PAD_TOKEN: 0, UNK_TOKEN: 1, CLS_TOKEN: 2}
    for ev in unique_events:
        vocab[ev] = len(vocab)
        
    with open(OUTPUT_DIR / "vocab.json", "w") as f:
        json.dump(vocab, f, indent=4)
    print(f"Słownik zapisany. Rozmiar: {len(vocab)}")

    # Przetwarzanie sesji
    print("Grupowanie i przetwarzanie sesji...")
    grouped = df.groupby("user_session")
    
    dataset = []
    
    for session_id, group in tqdm(grouped, total=len(grouped)):
        events = group["event_type"].tolist()
        times = group["event_time"].tolist()
        prices = group["price"].tolist() # ZMIANA: Pobieramy ceny z grupy
        
        # --- ETAP 1: Labeling i Target Leakage Prevention ---
        if "purchase" in events:
            label = 1
            first_purchase_idx = events.index("purchase")
            events = events[:first_purchase_idx]
            times = times[:first_purchase_idx]
            prices = prices[:first_purchase_idx] # ZMIANA: Ucinamy też ceny
        else:
            label = 0
            
        if len(events) < MIN_EVENTS_IN_SESSION:
            continue
            
        # --- ETAP 2: Wyliczanie czasu (delta_t) i Ceny ---
        time_feats = []
        for i in range(len(times)):
            if i == 0:
                delta_sec = 0.0
            else:
                delta_sec = (times[i] - times[i-1]).total_seconds()
                delta_sec = max(0.0, delta_sec)
            
            # Logarytmiczna kompresja czasu i ceny
            log_t = np.log1p(delta_sec)
            log_price = np.log1p(max(0.0, prices[i])) # Zabezpieczenie przed ujemną ceną w logach
            
            # ZMIANA: Wektor ma teraz 2 wymiary [Czas, Cena]
            time_feats.append([log_t, log_price])
            
        # --- ETAP 3: Tokenizacja i <CLS> ---
        event_ids = [vocab[CLS_TOKEN]] + [vocab.get(e, vocab[UNK_TOKEN]) for e in events]
        # ZMIANA: Dodajemy wektor [0.0, 0.0] dla tokena CLS
        time_feats = [[0.0, 0.0]] + time_feats 
        
        # Przycinanie do MAX_SEQ_LEN
        if len(event_ids) > MAX_SEQ_LEN:
            event_ids = event_ids[:MAX_SEQ_LEN]
            time_feats = time_feats[:MAX_SEQ_LEN]
            
        # Padding
        seq_len = len(event_ids)
        pad_len = MAX_SEQ_LEN - seq_len
        
        if pad_len > 0:
            event_ids.extend([vocab[PAD_TOKEN]] * pad_len)
            # ZMIANA: Pusty padding ma teraz postać wektora 2D [0.0, 0.0]
            time_feats.extend([[0.0, 0.0]] * pad_len)
            
        dataset.append({
            "event_ids": torch.tensor(event_ids, dtype=torch.long),
            "time_feats": torch.tensor(time_feats, dtype=torch.float32),
            "lengths": torch.tensor(seq_len, dtype=torch.long),
            "labels": torch.tensor(label, dtype=torch.long)
        })

    print(f"\nWygenerowano {len(dataset)} poprawnych sesji.")
    labels_list = [d["labels"].item() for d in dataset]
    print(f"Klasa 0 (Porzucenie): {labels_list.count(0)}")
    print(f"Klasa 1 (Zakup): {labels_list.count(1)}")
    
    # Podział na Train / Val / Test (70% / 15% / 15%)
    np.random.shuffle(dataset)
    n = len(dataset)
    train_end = int(n * 0.7)
    val_end = int(n * 0.85)
    
    torch.save(dataset[:train_end], OUTPUT_DIR / "train_data.pt")
    torch.save(dataset[train_end:val_end], OUTPUT_DIR / "val_data.pt")
    torch.save(dataset[val_end:], OUTPUT_DIR / "test_data.pt")
    print(f"Dane zapisane w katalogu {OUTPUT_DIR}/")

if __name__ == "__main__":
    process_data()