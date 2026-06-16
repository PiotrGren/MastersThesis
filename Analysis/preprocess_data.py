import argparse
import json
import os 
import random
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from tqdm import tqdm

from helpers.custom_logger import get_custom_logger

logger = get_custom_logger("DataPipeline")

LABEL_MAP = {
    "WindowShopper": 0,
    "ImpulsiveTrader": 1,
    "CarefulTrader": 2,
    "IndecisiveTrader": 3,
    "StrategicHolder": 4
}

def load_jsonl(path: Path) -> pd.DataFrame:
    if not path.exists():
        logger.warning(f"Plik {path} nie istnieje!")
        return pd.DataFrame()
    
    data = []
    with open(path, 'r', encoding='utf-8') as f:
        total_lines = sum(1 for _ in f)

    with open(path, 'r', encoding='utf-8') as f:
        for line in tqdm(f, total=total_lines, desc=f'Loading {path.name}', unit='lines'):
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return pd.DataFrame(data)


def generate_semantic_token(row) -> str:
    """Generuje bogaty token na podstawie metody, endpointu, statusu i kontekstu błędu."""
    method = str(row.get('api_method', 'UNK')).upper()
    group = str(row.get('endpoint_group', 'UNK')).upper()

    # Przechwycenie statusu odpowiedzi - domyślnie 000 jeśli brak
    status = row.get('http_status')
    status_str = str(int(status)) if pd.notna(status) else "000"

    # NOWOŚĆ: Wyciągnięcie typu błędu, jeśli wystąpił
    error_context = row.get('error_context')
    error_suffix = ""
    
    if isinstance(error_context, dict):
        # Jeśli jest to słownik, wyciągamy error_type (np. "validation")
        err_type = error_context.get('error_type')
        if err_type:
            error_suffix = f"_{str(err_type).upper()}"

    # Zwraca np. "POST_BUY_201" dla sukcesu lub "POST_BUY_400_VALIDATION" dla błędu
    return f"{method}_{group}_{status_str}{error_suffix}"


def main(args):
    log_dir = Path(args.log_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    req_path = log_dir / args.request_file

    # Jednak tylko request_log bo zawiera pełne statusy http i errory
    df_req = load_jsonl(req_path)

    if df_req.empty:
        logger.error("Nie można przetworzyć danych - brak validnych rekordów w request_log.")
        return
    
    logger.info(f"Preprocessing request_log...")

    # Usuwanie śmieci
    initial_len = len(df_req)
    df_req = df_req[~df_req['endpoint'].str.contains("debug/airdrop", case=False, na=False)]
    df_req = df_req.dropna(subset=['session_id', 'user_class'])
    logger.info(f"Usunięto {initial_len - len(df_req)} odfiltrowanych rekordów.")

    df_req['timestamp'] = pd.to_datetime(df_req['timestamp'])

    # Sortowanie i obliczanie DELTA_T
    df_req = df_req.sort_values(['session_id', 'timestamp'])
    df_req['delta_t'] = df_req.groupby('session_id')['timestamp'].diff().dt.total_seconds() * 1000.0 
    df_req['delta_t'] = df_req['delta_t'].fillna(0.0)

    # Generowanie tokenów semantycznych
    df_req['token_key'] = df_req.apply(generate_semantic_token, axis=1)

    logger.info("Grupowanie po sesjach i podział Train/Val/Test...")
    
    all_sessions = []
    grouped = df_req.groupby('session_id')
    
    # Najpierw wyodrębniamy same DataFrame'y sesji i ich etykiety
    for sess_id, group in tqdm(grouped, desc="Extracting sessions"):
        u_class = group['user_class'].iloc[0]
        if u_class not in LABEL_MAP:
            continue
        all_sessions.append({'session_id': sess_id, 'data': group, 'label_id': LABEL_MAP[u_class]})
        
    # Podział 80/10/10 na poziomie surowych sesji
    random.seed(169783)
    random.shuffle(all_sessions)

    n = len(all_sessions)
    n_train = int(n * 0.80)
    n_val = int(n * 0.10)

    train_raw = all_sessions[:n_train]
    val_raw = all_sessions[n_train : n_train + n_val]
    test_raw = all_sessions[n_train + n_val :]

    # --- Budowa słownika (Vocab) TYLKO na zbiorze treningowym ---
    logger.info("Budowa słownika (Vocab) z danych treningowych...")
    train_tokens = []
    for sess in train_raw:
        train_tokens.extend(sess['data']['token_key'].tolist())

    token_counts = Counter(train_tokens)
    logger.info(f"Znaleziono {len(token_counts)} unikalnych tokenów w zbiorze treningowym.")

    # --- Budowa słownika VOCAB z tokenem CLS ---
    # 0=PAD, 1=UNK, 2=CLS (dla Transformera)
    vocab = {"<PAD>": 0, "<UNK>": 1, "<CLS>": 2}
    for token, _ in token_counts.most_common():
        vocab[token] = len(vocab)

    with open(output_dir / "vocab.json", 'w') as f:
        json.dump(vocab, f, indent=2)

    cls_token_id = vocab["<CLS>"]

    # Funkcja pomocnicza do konwersji surowych sesji na Tensory w oparciu o wyuczony Vocab
    def process_split(raw_sessions, desc):
        processed = []
        for sess in tqdm(raw_sessions, desc=f"Tensorizing {desc}"):
            group = sess['data']
            label_id = sess['label_id']
            sess_id = sess['session_id']

            # 1. Event IDs (Nieznane tokeny z test/val wpadną jako <UNK> dzięki .fillna(1))
            tokens = group['token_key'].map(vocab).fillna(1).astype(int).values
            event_ids_array = np.insert(tokens, 0, cls_token_id)
            event_ids = torch.tensor(event_ids_array, dtype=torch.long)

            # 2. Time Feats: Log-normalizacja
            t_feats = group[['latency_ms_total', 'db_time_ms', 'app_time_ms', 'delta_t']].fillna(0.0).values
            t_feats = np.clip(t_feats, 0.0, None) 
            t_feats = np.log1p(t_feats)

            cls_time_feat = np.array([[0.0, 0.0, 0.0, 0.0]])
            t_feats_array = np.vstack([cls_time_feat, t_feats])
            time_feats = torch.tensor(t_feats_array, dtype=torch.float32)

            processed.append({
                'event_ids': event_ids,
                'time_feats': time_feats,
                'label': label_id,
                'session_id': sess_id
            })
        return processed

    train_data = process_split(train_raw, "Train")
    val_data = process_split(val_raw, "Val")
    test_data = process_split(test_raw, "Test")

    # Zapis
    save_split = lambda data_list, name: torch.save(data_list, output_dir / f"{name}_data.pt") if data_list else None
    save_split(train_data, "train")
    save_split(val_data, "val")
    save_split(test_data, "test")

    logger.info("Zapisano przetworzone dane Train / Test / Val w formacie []_data.pt w katalogu output.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-dir", type=str, default="./logs")
    parser.add_argument("--request-file", type=str, default="request_log.jsonl")
    parser.add_argument("--output-dir", type=str, default="./data")
    args = parser.parse_args()
    main(args)