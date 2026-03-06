#python test_net.py --weights outputs/experiment_01/model_best.pth
import argparse
import yaml
import torch
import json
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import classification_report, confusion_matrix
import os

# Importy z Twoich modułów
from model.bilstm_fusion import BiLSTMFusion, BiLSTMFusionConfig
from scripts.data_loader import build_data_loader

# Definicja klas (musi być zgodna z process_data.py)
CLASS_NAMES = ["ReadOnlyUser", "ActiveUser", "ActiveUserWithMarketAnalize"]

def save_plots(cm, report_dict, output_dir):
    """Generuje i zapisuje profesjonalne wykresy do folderu results."""
    
    # Ustawienie stylu
    sns.set_style("whitegrid")
    plt.rcParams.update({'font.size': 12})

    # --- 1. Macierz Pomyłek (Liczbowa) ---
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                xticklabels=CLASS_NAMES, yticklabels=CLASS_NAMES, cbar=False)
    plt.ylabel('Prawdziwa Klasa', fontweight='bold')
    plt.xlabel('Przewidziana Klasa', fontweight='bold')
    plt.title('Macierz Pomyłek (Liczbowa)', fontsize=14)
    plt.tight_layout()
    plt.savefig(output_dir / "confusion_matrix_count.png", dpi=300)
    plt.close()

    # --- 2. Macierz Pomyłek (Znormalizowana - %) ---
    # Normalizacja wierszami (True Label)
    cm_norm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
    
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm_norm, annot=True, fmt='.2%', cmap='Greens', 
                xticklabels=CLASS_NAMES, yticklabels=CLASS_NAMES, cbar=False)
    plt.ylabel('Prawdziwa Klasa', fontweight='bold')
    plt.xlabel('Przewidziana Klasa', fontweight='bold')
    plt.title('Macierz Pomyłek (Znormalizowana)', fontsize=14)
    plt.tight_layout()
    plt.savefig(output_dir / "confusion_matrix_norm.png", dpi=300)
    plt.close()

    # --- 3. Wykres Metryk per Klasa (Bar Chart) ---
    # Konwersja raportu do DataFrame
    data = []
    for cls in CLASS_NAMES:
        if cls in report_dict:
            row = report_dict[cls]
            data.append({"Klasa": cls, "Metryka": "Precision", "Wartość": row['precision']})
            data.append({"Klasa": cls, "Metryka": "Recall", "Wartość": row['recall']})
            data.append({"Klasa": cls, "Metryka": "F1-Score", "Wartość": row['f1-score']})
    
    df_metrics = pd.DataFrame(data)
    
    plt.figure(figsize=(12, 6))
    sns.barplot(data=df_metrics, x="Klasa", y="Wartość", hue="Metryka", palette="viridis")
    plt.title("Jakość klasyfikacji w podziale na klasy", fontsize=14)
    plt.ylim(0, 1.1)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(output_dir / "metrics_by_class.png", dpi=300)
    plt.close()

def main(args):
    # 1. Ustalanie ścieżek wyjściowych
    weights_path = Path(args.weights)
    if not weights_path.exists():
        raise FileNotFoundError(f"Nie znaleziono pliku wag: {weights_path}")
         
    possible_paths = [
        weights_path.parent / "config.yaml",
        weights_path.parent.parent / "config.yaml"
    ]
    
    config_path = None
    for p in possible_paths:
        if p.exists():
            config_path = p
            break
            
    if config_path is None:
        raise FileNotFoundError(
            f"Nie znaleziono 'config.yaml' w folderze modelu ani folder wyżej.\n"
            f"Szukano w: {[str(p) for p in possible_paths]}"
        )

    print(f"Auto-detected config path: {config_path}")

    # 2. Wczytanie konfiguracji
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)
        
    device = torch.device(cfg["SYSTEM"]["DEVICE"] if args.num_gpus > 0 else "cpu")
    
    # Folder results tworzymy OBOK pliku z wagami
    results_dir = weights_path.parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Loading weights from: {weights_path}")
    print(f"Results will be saved to: {results_dir}")

    # 3. Wczytanie Słownika
    vocab_path = cfg["DATA"]["VOCAB_PATH"]
    with open(vocab_path, "r") as f:
        vocab = json.load(f)
    
    # 4. Inicjalizacja Modelu
    model_cfg = BiLSTMFusionConfig(
        vocab_size=len(vocab),
        lstm_hidden=int(cfg["MODEL"]["HIDDEN_DIM"]),
        lstm_layers=int(cfg["MODEL"]["LAYERS"]),
        dropout=float(cfg["MODEL"]["DROPOUT"]),
        num_classes=int(cfg["MODEL"]["NUM_CLASSES"])
    )
    model = BiLSTMFusion(model_cfg)
    model.to(device)

    # 5. Ładowanie stanu
    checkpoint = torch.load(weights_path, map_location=device)
    if "model" in checkpoint:
        model.load_state_dict(checkpoint["model"])
    else:
        model.load_state_dict(checkpoint)
    
    model.eval()

    # 6. Ładowanie Danych Testowych
    test_path = str(Path(cfg["DATA"]["TRAIN_PATH"]).parent / "test_data.pt")
    print(f"Loading test data from: {test_path}")
    
    test_loader = build_data_loader(
        test_path, 
        batch_size=int(cfg["SOLVER"]["USR_PER_BATCH"]), 
        is_train=False, 
        infinite=False
    )

    # 7. Inferencja
    all_preds = []
    all_labels = []

    print("Running inference...")
    with torch.no_grad():
        for batch in test_loader:
            event_ids = batch["event_ids"].to(device)
            time_feats = batch["time_feats"].to(device)
            lengths = batch["lengths"].to(device)
            labels = batch["labels"].to(device)

            logits, _ = model(event_ids, time_feats, lengths)
            preds = torch.argmax(logits, dim=1)

            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

    # 8. Generowanie Raportów
    print("\nGenerowanie raportów...")
    
    # A. Classification Report (JSON + TXT)
    report_dict = classification_report(all_labels, all_preds, target_names=CLASS_NAMES, output_dict=True)
    report_txt = classification_report(all_labels, all_preds, target_names=CLASS_NAMES, output_dict=False, digits=4)
    
    print(f"\n{report_txt}")
    
    # Zapis raportu txt
    with open(results_dir / "classification_report.txt", "w") as f:
        f.write(f"{report_txt}")
    
    # Zapis raportu json
    with open(results_dir / "metrics.json", "w") as f:
        json.dump(report_dict, f, indent=4)

    # B. Confusion Matrix
    cm = confusion_matrix(all_labels, all_preds)
    
    # C. Generowanie Wykresów
    save_plots(cm, report_dict, results_dir)
    
    print(f"\n[SUCCESS] Wszystkie wyniki zapisano w: {results_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    #parser.add_argument("--config", type=str, required=True, help="Path to config yaml")
    parser.add_argument("--weights", type=str, required=True, help="Path to .pth model file")
    parser.add_argument("--num-gpus", type=int, default=1, help="Number of GPUs")
    args = parser.parse_args()
    main(args)