import os
import json
import logging
import torch
import sys
import numpy as np
from pathlib import Path
from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score

class TrainingLogger:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_txt_path = self.output_dir / "log.txt"
        self.metrics_json_path = self.output_dir / "metrics.json"
        
        self.logger = logging.getLogger("TrainNet")
        self.logger.setLevel(logging.INFO)
        # Czyszczenie handlerów przy restarcie
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
        
        formatter = logging.Formatter("%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        
        fh = logging.FileHandler(self.log_txt_path)
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        self.logger.addHandler(sh)

    def info(self, msg: str):
        self.logger.info(msg)

    def log_metrics(self, metrics: dict):
        # Konwersja floatów numpy/torch na python float dla JSON
        clean_metrics = {}
        for k, v in metrics.items():
            if hasattr(v, 'item'): v = v.item()
            #if isinstance(v, (np.float32, np.float64)): v = float(v)
            if isinstance(v, np.floating): v = float(v)
            clean_metrics[k] = v
            
        with open(self.metrics_json_path, "a") as f:
            f.write(json.dumps(clean_metrics) + "\n")

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