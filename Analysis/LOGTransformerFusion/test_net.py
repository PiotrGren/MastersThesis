import argparse
import yaml
import torch
import json
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import confusion_matrix, classification_report
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

            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

    logger.debug("Calculating metrics and generating reports...")

    report_dict = classification_report(all_labels, all_preds, target_names=CLASS_NAMES, output_dict=True)
    report_txt = classification_report(all_labels, all_preds, target_names=CLASS_NAMES, output_dict=False, digits=4)

    logger.info(f"\n{report_txt}")

    with open(results_dir / "classification_report.txt", "w") as f:
        f.write(f"{report_txt}")

    with open(results_dir / "metrics.json", "w") as f:
        json.dump(report_dict, f, indent=4)

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