import argparse
import yaml
import torch
import json
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, roc_curve
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.transformer_fusion import LOGTransformerFusion, LOGTransformerConfig
from helpers.data_loader import build_data_loader
from helpers.utils import save_plots, TrainingLogger


# CLASS_NAMES = [
#     "WindowShopper", 
#     "ImpulsiveTrader", 
#     "CarefulTrader", 
#     "IndecisiveTrader", 
#     "StrategicHolder"
# ]

CLASS_NAMES = ["Abandon", "Purchase"]


def main(args):
    weights_path = Path(args.weights)
    if not weights_path.exists():
        raise FileNotFoundError(f"Model weights not found: {weights_path}")
    
    results_dir = weights_path.parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    
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
        raise FileNotFoundError(f"Config file not found in expected locations: {possible_paths}")
    
    logger = TrainingLogger(str(results_dir)).logger
    logger.debug(f"Auto-detected config path: {config_path}")

    with open(config_path, 'r') as f:
        cfg = yaml.safe_load(f)

    device = torch.device(cfg["SYSTEM"]["DEVICE"] if args.num_gpus > 0 else "cpu")

    vocab_path = cfg["DATA"]["VOCAB_PATH"]
    with open(vocab_path, "r") as f:
        vocab = json.load(f)

    model_cfg = LOGTransformerConfig(
        vocab_size=len(vocab),
        d_model=int(cfg["MODEL"]["D_MODEL"]),
        time_feat_dim=int(cfg["MODEL"]["TIME_FEAT_DIM"]),
        time_mlp_hidden=int(cfg["MODEL"]["TIME_MLP_HIDDEN"]),
        nhead=int(cfg["MODEL"]["NHEAD"]),
        num_layers=int(cfg["MODEL"]["NUM_LAYERS"]),
        dim_feedforward=int(cfg["MODEL"]["DIM_FEEDFORWARD"]),
        max_seq_len=int(cfg["MODEL"]["MAX_SEQ_LEN"]),
        num_classes=int(cfg["MODEL"]["NUM_CLASSES"]),
        head_hidden=int(cfg["MODEL"]["HEAD_HIDDEN"]),
        dropout=float(cfg["MODEL"]["DROPOUT"])
    )

    model = LOGTransformerFusion(model_cfg)
    model.to(device)

    logger.debug(f"Loading weights from: {weights_path}")
    checkpoint = torch.load(weights_path, map_location=device, weights_only=False)
    if "model" in checkpoint:
        model.load_state_dict(checkpoint["model"])
    else:
        model.load_state_dict(checkpoint)

    model.eval()

    test_path = str(Path(cfg["DATA"]["TRAIN_PATH"]).parent / "test_data.pt")
    logger.info(f"Loading test data from: {test_path}")

    test_loader = build_data_loader(
        test_path,
        batch_size=int(cfg["SOLVER"]["USR_PER_BATCH"]),
        is_train=False,
        infinite=False
    )

    all_preds = []
    all_labels = []
    all_probs = []

    logger.warning("Running inference...")
    with torch.no_grad():
        for barch in test_loader:
            event_ids = barch["event_ids"].to(device)
            time_feats = barch["time_feats"].to(device)
            lengths = barch["lengths"].to(device)
            labels = barch["labels"].to(device)

            # --- ABLATION STUDY: Wyzerowanie czasu ---
            time_feats = torch.zeros_like(time_feats)
            # -----------------------------------------

            outputs = model(event_ids, time_feats, lengths)
            logits = outputs[0] if isinstance(outputs, tuple) else outputs
            preds = torch.argmax(logits, dim=1)
            probs = torch.softmax(logits, dim=1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
            all_probs.extend(probs.detach().cpu().numpy())

    logger.debug("Calculating metrics and generating reports...")

    report_dict = classification_report(all_labels, all_preds, target_names=CLASS_NAMES, output_dict=True)
    report_txt = classification_report(all_labels, all_preds, target_names=CLASS_NAMES, output_dict=False, digits=4)

    logger.info(f"\n{report_txt}")

    with open(results_dir / "classification_report.txt", "w") as f:
        f.write(f"{report_txt}")

    with open(results_dir / "metrics.json", "w") as f:
        json.dump(report_dict, f, indent=4)

    all_probs_np = np.array(all_probs)
    if all_probs_np.ndim == 2:
        all_probs_np = all_probs_np[:, 1]

    roc_auc = roc_auc_score(all_labels, all_probs_np)
    
    with open(results_dir / "roc_auc_report.txt", "w") as f:
        f.write("=== Raport ROC AUC ===\n")
        f.write(f"Zbiór ewaluacyjny: {len(all_labels)} próbek\n")
        f.write(f"ROC AUC Score: {roc_auc:.4f}\n")

    logger.info(f"Zapisano wynik ROC AUC: {roc_auc:.4f} do pliku roc_auc_report.txt")
    
    # Zabezpieczenie: dodanie wyniku też do ogólnego JSONa
    report_dict["roc_auc"] = roc_auc
    with open(results_dir / "metrics.json", "w") as f:
        json.dump(report_dict, f, indent=4)

    # C. Generowanie i zapis wykresu krzywej ROC
    logger.debug("Generating ROC Curve plot...")
    
    # Wyliczenie wektorów FPR i TPR na podstawie skorygowanych prawdopodobieństw
    fpr, tpr, thresholds = roc_curve(all_labels, all_probs_np)
    
    plt.figure(figsize=(8, 6))
    
    # Rysowanie właściwej krzywej modelu
    plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'Krzywa ROC (AUC = {roc_auc:.4f})')
    
    # Rysowanie linii bazowej (losowy klasyfikator, AUC = 0.5)
    plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--', label='Losowy klasyfikator')
    
    # Formatowanie wykresu w rygorze akademickim
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('Odsetek Fałszywie Pozytywnych (FPR)')
    plt.ylabel('Odsetek Prawdziwie Pozytywnych (TPR)')
    plt.title('Krzywa ROC (Receiver Operating Characteristic)')
    plt.legend(loc="lower right")
    plt.grid(True, alpha=0.3)
    
    # Zapis wykresu (bbox_inches='tight' usuwa niepotrzebne białe marginesy)
    roc_plot_path = results_dir / "roc_curve.png"
    plt.savefig(roc_plot_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    logger.info(f"Zapisano wykres krzywej ROC do: {roc_plot_path}")

    logger.debug("Generating confusion matrix and plots...")
    cm = confusion_matrix(all_labels, all_preds)
    save_plots(cm, report_dict, results_dir, CLASS_NAMES)

    logger.info(f"[SUCCESS] All results saved to: {results_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test LOGTransformerFusion model")
    parser.add_argument("--weights", type=str, required=True, help="Path to model weights (.pth)")
    parser.add_argument("--num-gpus", type=int, default=1, help="Number of GPUs (0 for CPU)")
    args = parser.parse_args()

    main(args)