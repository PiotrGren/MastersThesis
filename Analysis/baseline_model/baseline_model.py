import torch
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
import time
import json
from pathlib import Path
# ==========================================
# KONFIGURACJA ŚCIEŻEK (Dane z SYMULACJI)
# ==========================================
DATA_DIR = "data" # Zgodnie z prośbą: dane w folderze data/
TRAIN_PATH = f"{DATA_DIR}/train_data.pt"
TEST_PATH = f"{DATA_DIR}/test_data.pt"
RESULTS_DIR = Path("results") # Tu trafią wszystkie wykresy i raporty

# Funkcja do wyciągania i spłaszczania danych
MAX_SEQ_LEN = 200 # Set this to the maximum expected sequence length

# Funkcja do wyciągania i spłaszczania danych
def extract_features(data_list):
    X, y = [], []
    for item in data_list:
        # 1. Pobieramy zdarzenia
        events = item['event_ids'].numpy()
        
        # 2. Pobieramy i SPŁASZCZAMY czas (macierz [seq_len, 4] -> wektor [seq_len * 4])
        times = item['time_feats'].numpy().flatten()
        
        # PADDING / TRUNCATING do stałej długości (MAX_SEQ_LEN)
        # Pad/truncate events
        if len(events) > MAX_SEQ_LEN:
            events_padded = events[:MAX_SEQ_LEN]
        else:
            # Pad with 0 (assuming 0 is your PAD token ID)
            events_padded = np.pad(events, (0, MAX_SEQ_LEN - len(events)), constant_values=0)
            
        # Pad/truncate times
        max_time_len = MAX_SEQ_LEN * 4 # 4 features per timestep
        if len(times) > max_time_len:
            times_padded = times[:max_time_len]
        else:
            # Pad with 0.0
            times_padded = np.pad(times, (0, max_time_len - len(times)), constant_values=0.0)

        # 3. Łączymy w jeden długi wektor
        features = np.concatenate([events_padded, times_padded])
        X.append(features)
        
        # 4. Pobieramy etykietę (ZMIENIONO 'labels' na 'label')
        y.append(item['label'])
        
    return np.array(X), np.array(y)

def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"Ładowanie danych z symulacji z folderu {DATA_DIR}/ ...")
    train_data = torch.load(TRAIN_PATH, weights_only=False)
    test_data = torch.load(TEST_PATH, weights_only=False)
    
    print("Ekstrakcja i spłaszczanie cech dla modelu klasy Baseline...")
    X_train, y_train = extract_features(train_data)
    X_test, y_test = extract_features(test_data)
    
    print(f"Kształt danych treningowych: X={X_train.shape}, y={y_train.shape}")
    
    print("\nRozpoczęcie treningu Płytkiego Drzewa Decyzyjnego...")
    start_t = time.time()
    
    # Inicjalizacja Płytkiego Drzewa (max_depth=4 to bardzo "słaby" model)
    clf = DecisionTreeClassifier(
        max_depth=4, 
        random_state=42,
        class_weight='balanced'
    )
    
    clf.fit(X_train, y_train)
    print(f"Trening zakończony błyskawicznie w {time.time() - start_t:.2f} sekund.")
    
    print("\nPrzewidywanie na zbiorze testowym...")
    y_pred = clf.predict(X_test)
    
    target_names = [
        "WindowShopper", 
        "ImpulsiveTrader", 
        "CarefulTrader", 
        "IndecisiveTrader", 
        "StrategicHolder"
    ]
    
    # ==========================================
    # GENEROWANIE I ZAPISYWANIE WYNIKÓW
    # ==========================================
    print("\nGenerowanie raportów i macierzy pomyłek do folderu 'results_tree/'...")
    
    report_txt = classification_report(y_test, y_pred, target_names=target_names, digits=4)
    report_dict = classification_report(y_test, y_pred, target_names=target_names, digits=4, output_dict=True)
    
    print("\n--- WYNIKI MODELU BAZOWEGO (Naiwne Drzewo Decyzyjne) ---")
    print(report_txt)
    
    with open(RESULTS_DIR / "classification_report.txt", "w", encoding="utf-8") as f:
        f.write(report_txt)
        
    with open(RESULTS_DIR / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=4)
        
    # Macierz pomyłek -> PNG
    cm = confusion_matrix(y_test, y_pred)
    
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Oranges', 
                xticklabels=target_names, yticklabels=target_names)
    plt.title("Confusion Matrix - Decision Tree Baseline (max_depth=4)")
    plt.ylabel("Rzeczywista klasa")
    plt.xlabel("Przewidziana klasa")
    plt.tight_layout()
    
    cm_path = RESULTS_DIR / "confusion_matrix.png"
    plt.savefig(cm_path, dpi=300)
    plt.close()
    
    print(f"\n[SUCCESS] Macierz pomyłek zapisano jako: {cm_path}")
    print(f"[SUCCESS] Raporty tekstowe zapisano w folderze: {RESULTS_DIR}")

if __name__ == "__main__":
    main()