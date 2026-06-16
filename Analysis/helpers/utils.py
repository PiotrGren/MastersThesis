import os
import json
import logging
import torch
import sys
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score

from .custom_logger import get_custom_logger


class TrainingLogger:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_txt_path = self.output_dir / "log.txt"
        self.metrics_json_path = self.output_dir / "metrics.json"
        
        # Używamy naszego kolorowego loggera (który już ma StreamHandler do konsoli)
        self.logger = get_custom_logger("TrainNet")
        
        # Zostawiamy TYLKO FileHandler, aby logi wciąż zapisywały się do pliku txt
        formatter = logging.Formatter("%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        fh = logging.FileHandler(self.log_txt_path)
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)


class Checkpointer:
    def __init__(self, model, optimizer, scheduler, output_dir):
        self.model = model
        self.optimizer = optimizer
        self.scheduler = scheduler
        self.output_dir = Path(output_dir)

    #def save(self, name: str, iteration: int, extra: dict = None):
    def save(self, name: str, iteration: int, extra: dict | None = None):
        save_path = self.output_dir / f"{name}.pth"
        data = {
            "model": self.model.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "scheduler": self.scheduler.state_dict() if self.scheduler else None,
            "iteration": iteration,
        }
        if extra:
            data.update(extra)
        torch.save(data, save_path)
        return save_path

    def load(self, path: str):
        if not os.path.exists(path):
            return 0
        checkpoint = torch.load(path, map_location="cpu")
        self.model.load_state_dict(checkpoint["model"])
        if "optimizer" in checkpoint and self.optimizer:
            self.optimizer.load_state_dict(checkpoint["optimizer"])
        if "scheduler" in checkpoint and self.scheduler and checkpoint["scheduler"]:
            self.scheduler.load_state_dict(checkpoint["scheduler"])
        return checkpoint.get("iteration", 0)

    def get_last_checkpoint_path(self):
        return self.output_dir / "last_checkpoint.pth"


def calculate_metrics(logits, targets):
    """
    Oblicza Accuracy, F1-Macro, Precision-Macro, Recall-Macro.
    """
    preds = torch.argmax(logits, dim=1).cpu().numpy()
    y_true = targets.cpu().numpy()
    
    acc = accuracy_score(y_true, preds)
    # average='macro' -> ważymy każdą klasę po równo (ważne przy imbalance!)
    f1 = f1_score(y_true, preds, average='macro', zero_division=0)
    prec = precision_score(y_true, preds, average='macro', zero_division=0)
    rec = recall_score(y_true, preds, average='macro', zero_division=0)
    
    return {
        "acc": acc,
        "f1": f1,
        "precision": prec,
        "recall": rec
    }


def save_plots(cm, report_dict, output_dir, class_names):
    """Generuje i zapisuje profesjonalne wykresy do folderu results."""
    
    # Ustawienie stylu
    sns.set_style("whitegrid")
    plt.rcParams.update({'font.size': 12})

    # --- 1. Macierz Pomyłek (Liczbowa) ---
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                xticklabels=class_names, yticklabels=class_names, cbar=False)
    plt.ylabel('Prawdziwa Klasa', fontweight='bold')
    plt.xlabel('Przewidziana Klasa', fontweight='bold')
    plt.title('Macierz Pomyłek (Liczbowa)', fontsize=14)
    plt.tight_layout()
    plt.savefig(output_dir / "confusion_matrix_count.png", dpi=300)
    plt.close()

    # --- 2. Macierz Pomyłek (Znormalizowana - %) ---
    cm_norm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm_norm, annot=True, fmt='.2%', cmap='Greens', 
                xticklabels=class_names, yticklabels=class_names, cbar=False)
    plt.ylabel('Prawdziwa Klasa', fontweight='bold')
    plt.xlabel('Przewidziana Klasa', fontweight='bold')
    plt.title('Macierz Pomyłek (Znormalizowana)', fontsize=14)
    plt.tight_layout()
    plt.savefig(output_dir / "confusion_matrix_norm.png", dpi=300)
    plt.close()

    # --- 3. Wykres Metryk per Klasa (Bar Chart) ---
    data = []
    for cls in class_names:
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