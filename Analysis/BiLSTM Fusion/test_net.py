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
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importy z Twoich modułów
from model.bilstm_fusion import BiLSTMFusion, BiLSTMFusionConfig
from helpers.data_loader import build_data_loader
from helpers.utils import TrainingLogger, save_plots

# Definicja klas (musi być zgodna z process_data.py)
# CLASS_NAMES = [
#     "WindowShopper", 
#     "ImpulsiveTrader", 
#     "CarefulTrader", 
#     "IndecisiveTrader", 
#     "StrategicHolder"
#]

CLASS_NAMES = ["Abandon", "Purchase"]


def main(args):
    # 1. Ustalanie ścieżek wyjściowych
    weights_path = Path(args.weights)
    if not weights_path.exists():
        raise FileNotFoundError(f"Nie znaleziono pliku wag: {weights_path}")
    
    # Folder results tworzymy OBOK pliku z wagami
    results_dir = weights_path.parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    logger = TrainingLogger(str(results_dir)).logger
         
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

    logger.debug(f"Auto-detected config path: {config_path}")

    # 2. Wczytanie konfiguracji
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)
        
    device = torch.device(cfg["SYSTEM"]["DEVICE"] if args.num_gpus > 0 else "cpu")
    
    logger.debug(f"Results will be saved to: {results_dir}")

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
    logger.debug(f"Loading weights from: {weights_path}")
    checkpoint = torch.load(weights_path, map_location=device)
    if "model" in checkpoint:
        model.load_state_dict(checkpoint["model"])
    else:
        model.load_state_dict(checkpoint)
    
    model.eval()

    # 6. Ładowanie Danych Testowych
    test_path = str(Path(cfg["DATA"]["TRAIN_PATH"]).parent / "test_data.pt")
    logger.info(f"Loading test data from: {test_path}")
    
    test_loader = build_data_loader(
        test_path, 
        batch_size=int(cfg["SOLVER"]["USR_PER_BATCH"]), 
        is_train=False, 
        infinite=False
    )

    # 7. Inferencja
    all_preds = []
    all_labels = []

    logger.warning("Running inference...")
    with torch.no_grad():
        for batch in test_loader:
            event_ids = batch["event_ids"].to(device)
            time_feats = batch["time_feats"].to(device)
            lengths = batch["lengths"].to(device)
            labels = batch["labels"].to(device)

            # --- ABLATION STUDY: Wyzerowanie czasu ---
            #time_feats = torch.zeros_like(time_feats)
            # -----------------------------------------

            #logits, *_ = model(event_ids, time_feats, lengths)
            #preds = torch.argmax(logits, dim=1)

            outputs = model(event_ids, time_feats, lengths)
            
            # Bezpieczne wyciągnięcie logits (zadziała i dla krotki, i dla pojedynczego Tensora)
            logits = outputs[0] if isinstance(outputs, tuple) else outputs
            
            preds = torch.argmax(logits, dim=1)

            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

    # 8. Generowanie Raportów
    logger.debug("Calculating metrics and generating reports...")
    
    # A. Classification Report (JSON + TXT)
    report_dict = classification_report(all_labels, all_preds, target_names=CLASS_NAMES, output_dict=True)
    report_txt = classification_report(all_labels, all_preds, target_names=CLASS_NAMES, output_dict=False, digits=4)
    
    logger.info(f"\n{report_txt}")
    
    # Zapis raportu txt
    with open(results_dir / "classification_report.txt", "w") as f:
        f.write(f"{report_txt}")
    
    # Zapis raportu json
    with open(results_dir / "metrics.json", "w") as f:
        json.dump(report_dict, f, indent=4)

    # B. Confusion Matrix
    logger.debug("Generating confusion matrix and plots...")
    cm = confusion_matrix(all_labels, all_preds)
    
    # C. Generowanie Wykresów
    save_plots(cm, report_dict, results_dir, CLASS_NAMES)
    
    logger.info(f"[SUCCESS] All results saved to: {results_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=str, required=True, help="Path to .pth model file")
    parser.add_argument("--num-gpus", type=int, default=1, help="Number of GPUs")
    args = parser.parse_args()

    main(args)