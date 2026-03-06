import argparse
import json
import logging
import os
import random
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from tqdm import tqdm

# --- KONFIGURACJA LOGOWANIA CLI ---
class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    reset = "\x1b[0m"
    format_str = "%(asctime)s - %(levelname)s - %(message)s"

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: green + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: red + format_str + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%H:%M:%S")
        return formatter.format(record)

logger = logging.getLogger("DataPipeline")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)

# --- MAPOWANIE KLAS UŻYTKOWNIKÓW ---
LABEL_MAP = {
    "ReadOnlyUser": 0,
    "ActiveUser": 1,
    "ActiveUserWithMarketAnalize": 2
    # Jeśli pojawią się inne, wpadną jako -1 (i zostaną odfiltrowane)
}

def load_jsonl(path: Path) -> pd.DataFrame:
    """Wczytuje JSONL do DataFrame z paskiem postępu."""
    if not path.exists():
        logger.warning(f"Plik nie istnieje: {path}")
        return pd.DataFrame()
    
    logger.info(f"Wczytywanie: {path}")
    data = []
    # Liczymy linie dla tqdm
    with open(path, 'r', encoding='utf-8') as f:
        total_lines = sum(1 for _ in f)
        
    with open(path, 'r', encoding='utf-8') as f:
        for line in tqdm(f, total=total_lines, desc=f"Loading {path.name}", unit="lines"):
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return pd.DataFrame(data)

def main(args):
    # 1. Ścieżki
    log_dir = Path(args.log_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    req_path = log_dir / args.request_file
    err_path = log_dir / args.error_file

    # 2. Wczytanie danych
    df_req = load_jsonl(req_path)
    df_err = load_jsonl(err_path)

    if df_req.empty:
        logger.error("Brak danych request_log! Prerywam.")
        return

    # 3. Czyszczenie i Preprocessing Requestów
    logger.info("Preprocessing request_log...")
    
    # A. Filtrowanie endpointów debugowych (Airdrop)
    initial_len = len(df_req)
    df_req = df_req[~df_req['endpoint'].str.contains("debug/airdrop", case=False, na=False)]
    logger.info(f"Usunięto {initial_len - len(df_req)} rekordów debug/airdrop.")

    # B. Konwersja czasu
    df_req['timestamp'] = pd.to_datetime(df_req['timestamp'])
    
    # C. Upewnienie się, że mamy potrzebne kolumny
    required_cols = ['session_id', 'user_class', 'endpoint_group', 'api_method', 'latency_ms_total', 'db_time_ms', 'app_time_ms']
    df_req = df_req.dropna(subset=['session_id', 'user_class']) # Musi być sesja i klasa
    
    # 4. Integracja Error Log (Dołączamy błędy jako zdarzenia w sesji)
    if not df_err.empty:
        logger.info("Integrowanie error_log...")
        df_err['timestamp'] = pd.to_datetime(df_err['timestamp'])
        
        # Error log często nie ma session_id, ale ma request_id. 
        # Musimy zmapować request_id -> session_id z request_loga
        req_to_session = df_req.set_index('request_id')['session_id'].to_dict()
        req_to_class = df_req.set_index('request_id')['user_class'].to_dict()
        
        df_err['session_id'] = df_err['request_id'].map(req_to_session)
        df_err['user_class'] = df_err['request_id'].map(req_to_class)
        
        # Filtrujemy błędy, których nie udało się przypisać do sesji
        df_err_matched = df_err.dropna(subset=['session_id', 'user_class']).copy()
        
        if not df_err_matched.empty:
            # Tworzymy syntetyczne zdarzenie dla błędu
            # Np. endpoint_group = "SYSTEM_ERROR", api_method = error_code
            df_err_matched['endpoint_group'] = 'SYSTEM_ERROR'
            df_err_matched['api_method'] = df_err_matched['error_code'].fillna('UNKNOWN')
            
            # Wypełniamy czasy zerami (błąd systemowy to zdarzenie punktowe dla modelu)
            for col in ['latency_ms_total', 'db_time_ms', 'app_time_ms']:
                df_err_matched[col] = 0.0
                
            # Wybieramy tylko kolumny pasujące do df_req
            cols_to_merge = ['timestamp', 'session_id', 'user_class', 'endpoint_group', 'api_method', 'latency_ms_total', 'db_time_ms', 'app_time_ms']
            df_combined = pd.concat([df_req[cols_to_merge], df_err_matched[cols_to_merge]], ignore_index=True)
            logger.info(f"Dołączono {len(df_err_matched)} błędów do sekwencji.")
        else:
            df_combined = df_req
            logger.warning("Błędy istnieją, ale nie pasują do żadnych session_id z requestów (może stare logi?).")
    else:
        df_combined = df_req

    # 5. Sortowanie i obliczanie DELTA_T (Feature Engineering)
    logger.info("Obliczanie delta_t i sortowanie sesji...")
    df_combined = df_combined.sort_values(['session_id', 'timestamp'])
    
    # Obliczamy różnicę czasu w milisekundach dla każdej grupy (sesji)
    df_combined['delta_t'] = df_combined.groupby('session_id')['timestamp'].diff().dt.total_seconds() * 1000.0  # type: ignore
    df_combined['delta_t'] = df_combined['delta_t'].fillna(0.0) # Pierwszy request w sesji ma delta 0

    # 6. Budowa Słownika (Vocab)
    # Token = "METHOD GROUP", np. "POST BUY", "GET USER", "VALIDATION SYSTEM_ERROR"
    df_combined['token_key'] = df_combined['api_method'].astype(str) + " " + df_combined['endpoint_group'].astype(str)
    
    token_counts = Counter(df_combined['token_key'])
    logger.info(f"Znaleziono {len(token_counts)} unikalnych typów zdarzeń.")
    
    # Mapowanie: 0=PAD, 1=UNK, reszta od 2
    vocab = {"<PAD>": 0, "<UNK>": 1}
    for token, _ in token_counts.most_common():
        vocab[token] = len(vocab)
        
    # Zapis słownika
    with open(output_dir / "vocab.json", "w") as f:
        json.dump(vocab, f, indent=2)
    
    # 7. Konwersja na Tensory (Grupowanie)
    logger.info("Konwersja na sekwencje tensorowe...")
    
    sessions_data = [] # Lista krotek (event_ids, time_feats, label)
    
    # Grupujemy po sesji
    grouped = df_combined.groupby('session_id')
    
    for sess_id, group in tqdm(grouped, desc="Processing Sessions"):
        # Label
        u_class = group['user_class'].iloc[0]
        if u_class not in LABEL_MAP:
            continue # Pomijamy nieznane klasy
        label_id = LABEL_MAP[u_class]
        
        # Event IDs
        tokens = group['token_key'].map(vocab).fillna(1).astype(int).values # 1 = UNK
        event_ids = torch.tensor(tokens, dtype=torch.long)
        
        # Time Feats: [latency, db, app, delta]
        # Log-normalizacja: log1p(x) -> zmniejsza wpływ outlierów
        t_feats = group[['latency_ms_total', 'db_time_ms', 'app_time_ms', 'delta_t']].fillna(0.0).values
        t_feats = np.log1p(t_feats) # LOG NORMALIZACJA WAŻNE!
        time_feats = torch.tensor(t_feats, dtype=torch.float32)
        
        sessions_data.append({
            'event_ids': event_ids,
            'time_feats': time_feats,
            'label': label_id,
            'session_id': sess_id
        })

    logger.info(f"Przetworzono {len(sessions_data)} poprawnych sesji.")

    # 8. Podział Train / Val / Test
    random.seed(42)
    random.shuffle(sessions_data)
    
    n = len(sessions_data)
    n_train = int(n * 0.80)
    n_val = int(n * 0.10)
    # Reszta (10%) to test
    
    train_set = sessions_data[:n_train]
    val_set = sessions_data[n_train : n_train + n_val]
    test_set = sessions_data[n_train + n_val :]
    
    # Helper do zapisu
    def save_split(data_list, name):
        if not data_list:
            return
        
        # Collate (padding)
        # Ponieważ zapisujemy listę, padding zrobimy dynamicznie w DataLoaderze podczas treningu
        # ALE wygodniej zapisać jako listę słowników, torch.save to obsłuży.
        
        path = output_dir / f"{name}_data.pt"
        torch.save(data_list, path)
        logger.info(f"Zapisano {name.upper()}: {len(data_list)} sesji -> {path}")

    save_split(train_set, "train")
    save_split(val_set, "val")
    save_split(test_set, "test") # <-- O TO PYTAŁEŚ, TU JEST TEST SET

    logger.info("Gotowe! Dane przygotowane do treningu.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preprocessing logów dla BiLSTMFusion")
    parser.add_argument("--log_dir", type=str, default="./logs", help="Folder z plikami .jsonl")
    parser.add_argument("--request_file", type=str, default="request_log.jsonl", help="Nazwa pliku requestów")
    parser.add_argument("--error_file", type=str, default="error_log.jsonl", help="Nazwa pliku błędów")
    parser.add_argument("--output_dir", type=str, default="./data", help="Gdzie zapisać .pt")
    
    args = parser.parse_args()
    main(args)