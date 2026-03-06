# python train_net.py --config configs/config_fusion.yaml --num-gpus 1 --resume
import argparse
import yaml
import shutil
import torch
import torch.nn as nn
import os
import json
import time
from pathlib import Path

# Importy z Twoich modułów
from model.bilstm_fusion import BiLSTMFusion, BiLSTMFusionConfig
from scripts.data_loader import build_data_loader
from scripts.solver import build_optimizer, build_scheduler
from scripts.utils import TrainingLogger, Checkpointer, calculate_metrics

def main(args):
    # 1. Wczytanie konfiguracji
    with open(args.config, "r") as f:
        cfg = yaml.safe_load(f)

    # Nadpisywanie z CLI
    if args.num_gpus == 0:
        cfg["SYSTEM"]["DEVICE"] = "cpu"
    
    device = torch.device(cfg["SYSTEM"]["DEVICE"])
    output_dir = Path(cfg["SYSTEM"]["OUTPUT_DIR"])
    output_dir.mkdir(parents=True, exist_ok=True)
    
    shutil.copy(args.config, output_dir / "config.yaml")
    
    # 2. Logger
    logger = TrainingLogger(str(output_dir))
    logger.info(f"Starting training with config: {args.config}")
    logger.info(f"Output dir: {output_dir}")
    logger.info(f"Device: {device}")

    # 3. Dane i Słownik
    vocab_path = cfg["DATA"]["VOCAB_PATH"]
    with open(vocab_path, "r") as f:
        vocab = json.load(f)
    vocab_size = len(vocab)
    logger.info(f"Vocab loaded. Size: {vocab_size}")

    # DataLoaders
    train_loader = build_data_loader(
        cfg["DATA"]["TRAIN_PATH"], 
        batch_size=int(cfg["SOLVER"]["USR_PER_BATCH"]), 
        is_train=True, 
        infinite=True
    )
    # Walidacyjny loader (nie infinite, bo chcemy przejść go raz na epokę ewaluacji)
    val_loader = build_data_loader(
        cfg["DATA"]["VAL_PATH"], 
        batch_size=int(cfg["SOLVER"]["USR_PER_BATCH"]), 
        is_train=False, 
        infinite=False
    )

    # 4. Budowa Modelu
    model_cfg = BiLSTMFusionConfig(
        vocab_size=vocab_size,
        lstm_hidden=int(cfg["MODEL"]["HIDDEN_DIM"]),
        lstm_layers=int(cfg["MODEL"]["LAYERS"]),
        dropout=float(cfg["MODEL"]["DROPOUT"]),
        num_classes=int(cfg["MODEL"]["NUM_CLASSES"])
    )
    model = BiLSTMFusion(model_cfg)
    model.to(device)

    # 5. Solver
    optimizer = build_optimizer(model, cfg["SOLVER"])
    scheduler = build_scheduler(optimizer, cfg["SOLVER"])
    criterion = nn.CrossEntropyLoss()

    # 6. Checkpointer
    checkpointer = Checkpointer(model, optimizer, scheduler, output_dir)
    start_iter = 0

    if args.resume:
        last_ckpt = checkpointer.get_last_checkpoint_path()
        if last_ckpt.exists():
            start_iter = checkpointer.load(str(last_ckpt))
            logger.info(f"Resumed from iteration {start_iter}")
        else:
            logger.info("Resume requested but no checkpoint found. Starting from scratch.")

    # 7. Pętla Treningowa
    max_iter = int(cfg["SOLVER"]["MAX_ITER"])
    logger.info(f"Training started. Max iter: {max_iter}")
    
    model.train()
    start_time = time.time()
    best_val_f1 = 0.0

    # Iterujemy po nieskończonym loaderze
    for iteration, batch in enumerate(train_loader, start=start_iter):
        if iteration >= max_iter:
            break

        # Przeniesienie danych na GPU
        event_ids = batch["event_ids"].to(device)
        time_feats = batch["time_feats"].to(device)
        lengths = batch["lengths"].to(device)
        labels = batch["labels"].to(device)

        # Forward
        logits = model(event_ids, time_feats, lengths)
        loss = criterion(logits, labels)

        # Backward
        optimizer.zero_grad()
        loss.backward()
        
        # Clip gradients (ważne dla LSTM!)
        torch.nn.utils.clip_grad_norm_(model.parameters(), float(cfg["SOLVER"]["CLIP_GRADIENTS"]))
        
        optimizer.step()
        scheduler.step()

        # --- LOGGING ---
        if iteration % int(cfg["PERIODS"]["LOG_PERIOD"]) == 0:
            lr = optimizer.param_groups[0]["lr"]
            # Szacowanie czasu
            elapsed = time.time() - start_time
            avg_time = elapsed / (iteration - start_iter + 1) if iteration > start_iter else 0
            eta_seconds = avg_time * (max_iter - iteration)
            eta_str = str(time.strftime("%H:%M:%S", time.gmtime(eta_seconds)))
            
            # Szybkie metryki treningowe
            with torch.no_grad():
                metrics = calculate_metrics(logits, labels)
            
            log_msg = (
                f"Iter: {iteration}/{max_iter} | "
                f"Loss: {loss.item():.4f} | "
                f"Acc: {metrics['acc']:.2%} | "
                f"LR: {lr:.6f} | "
                f"ETA: {eta_str}"
            )
            logger.info(log_msg)
            
            # Zapis do metrics.json (trening)
            file_metrics = {"iter": iteration, "phase": "train", "loss": loss.item(), "lr": lr}
            file_metrics.update(metrics)
            logger.log_metrics(file_metrics)

        # --- CHECKPOINT ---
        if iteration % int(cfg["PERIODS"]["CHECKPOINT_PERIOD"]) == 0:
            checkpointer.save("last_checkpoint", iteration)

        # --- EVALUATION ---
        if iteration % int(cfg["PERIODS"]["EVAL_PERIOD"]) == 0 and iteration > 0:
            logger.info("Running evaluation...")
            model.eval()
            val_loss_sum = 0
            val_metrics_sum = {"acc": 0.0, "f1": 0.0, "precision": 0.0, "recall": 0.0}
            num_batches = 0

            with torch.no_grad():
                for val_batch in val_loader:
                    v_event = val_batch["event_ids"].to(device)
                    v_time = val_batch["time_feats"].to(device)
                    v_len = val_batch["lengths"].to(device)
                    v_lbl = val_batch["labels"].to(device)

                    v_logits = model(v_event, v_time, v_len)
                    v_loss = criterion(v_logits, v_lbl)
                    
                    val_loss_sum += v_loss.item()
                    batch_mets = calculate_metrics(v_logits, v_lbl)
                    for k in val_metrics_sum:
                        val_metrics_sum[k] += batch_mets[k]
                    num_batches += 1
            
            # Średnie wyniki
            avg_loss = val_loss_sum / num_batches
            avg_mets = {k: v / num_batches for k, v in val_metrics_sum.items()}
            
            logger.info(f"EVAL RESULT | Loss: {avg_loss:.4f} | F1: {avg_mets['f1']:.4f} | Acc: {avg_mets['acc']:.2%}")
            
            # Zapis do metrics.json (walidacja)
            val_file_metrics = {"iter": iteration, "phase": "val", "loss": avg_loss}
            val_file_metrics.update(avg_mets)
            logger.log_metrics(val_file_metrics)
            
            # Zapis najlepszego modelu (według F1)
            if avg_mets['f1'] > best_val_f1:
                best_val_f1 = avg_mets['f1']
                checkpointer.save("model_best", iteration, extra={"f1": best_val_f1})
                logger.info(f"New best model saved! F1: {best_val_f1:.4f}")

            model.train()

    # 8. Koniec
    final_path = output_dir / "final"
    final_path.mkdir(exist_ok=True)
    torch.save(model.state_dict(), final_path / "model_final.pth")
    logger.info(f"Training finished. Final model saved to {final_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True, help="Path to config yaml")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--num-gpus", type=int, default=1, help="Number of GPUs (0 for CPU)")
    args = parser.parse_args()
    main(args)