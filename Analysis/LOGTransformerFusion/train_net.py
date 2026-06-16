import argparse
import yaml
import shutil
import torch
import torch.nn as nn
import os
import sys
import json
import time
from pathlib import Path
from collections import Counter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.transformer_fusion import LOGTransformerFusion, LOGTransformerConfig
from helpers.data_loader import build_data_loader
from helpers.solver import build_optimizer, build_scheduler
from helpers.utils import TrainingLogger, Checkpointer, calculate_metrics


def main(args):
    with open(args.config, 'r') as f:
        cfg = yaml.safe_load(f)

    if args.num_gpus == 0:
        cfg['SYSTEM']["DEVICE"] = "cpu"

    device = torch.device(cfg["SYSTEM"]["DEVICE"])
    output_dir = Path(cfg["SYSTEM"]["OUTPUT_DIR"])
    output_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy(args.config, output_dir / 'config.yaml')

    logger = TrainingLogger(str(output_dir)).logger
    logger.info(f"Starting training with config: {args.config}")
    logger.info(f"Output dir: {output_dir}")
    logger.info(f"Device: {device}")

    vocab_path = cfg["DATA"]["VOCAB_PATH"]
    with open(vocab_path, 'r') as f:
        vocab = json.load(f)
    vocab_size = len(vocab)
    logger.info(f"Vocab loaded. Size: {vocab_size}")

    train_loader = build_data_loader(
        cfg["DATA"]["TRAIN_PATH"],
        batch_size=int(cfg["SOLVER"]["USR_PER_BATCH"]),
        is_train=True,
        infinite=True
    )

    val_loader = build_data_loader(
        cfg["DATA"]["VAL_PATH"],
        batch_size=int(cfg["SOLVER"]["USR_PER_BATCH"]),
        is_train=False,
        infinite=False
    )

    # Budowa modelu Transformer
    model_cfg = LOGTransformerConfig(
        vocab_size=vocab_size,
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

    optimizer = build_optimizer(model, cfg["SOLVER"])
    scheduler = build_scheduler(optimizer, cfg["SOLVER"])

    # --- DYNAMICZNE WYLICZANIE WAG KLAS ---
    logger.info("Calculating dynamic class weights directly from file...")

    # Wczytujemy dane bezpośrednio z pliku, żeby ominąć ograniczenia InfiniteDataLoader
    train_data_raw = torch.load(cfg["DATA"]["TRAIN_PATH"], weights_only=False)
    all_train_labels = [item["labels"].item() for item in train_data_raw]
    del train_data_raw  # Od razu zwalniamy pamięć RAM!
    class_counts = Counter(all_train_labels)
    total_samples = len(all_train_labels)
    num_classes = int(cfg["MODEL"]["NUM_CLASSES"])

    weights = torch.zeros(num_classes, dtype=torch.float32)
    for c in range(num_classes):
        count = class_counts.get(c, 0)
        if count > 0:
            weights[c] = total_samples / (num_classes * count)
        else:
            weights[c] = 0.0  # Bezpiecznik, gdyby klasa w ogóle nie wystąpiła w trainie

    weights = weights.to(device)
    criterion = nn.CrossEntropyLoss(weight=weights)

    logger.info(f"Class counts in train: {dict(class_counts)}")
    logger.info(f"Applied Class Weights: {weights.cpu().numpy()}")

    checkpointer = Checkpointer(model, optimizer, scheduler, output_dir)
    start_iter = 0

    if args.resume:
        last_ckpt = checkpointer.get_last_checkpoint_path()
        if last_ckpt.exists():
            start_iter = checkpointer.load(str(last_ckpt))
            logger.info(f"Resumed from iteration {start_iter}")

    max_iter = int(cfg["SOLVER"]["MAX_ITER"])
    logger.info(f"Training started. Max iter: {max_iter}")

    model.train()
    start_time = time.time()
    best_val_f1 = 0.0

    for iteration, batch in enumerate(train_loader, start=start_iter):
        if iteration >= max_iter:
            break

        event_ids = batch["event_ids"].to(device)
        time_feats = batch["time_feats"].to(device)
        lengths = batch["lengths"].to(device)
        labels = batch["labels"].to(device)

        # --- ABLATION STUDY: Wyzerowanie czasu ---
        time_feats = torch.zeros_like(time_feats)
        # -----------------------------------------

        logits = model(event_ids, time_feats, lengths)
        loss = criterion(logits, labels)

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), float(cfg["SOLVER"]["CLIP_GRADIENTS"]))
        optimizer.step()
        scheduler.step()


        if iteration % int(cfg["PERIODS"]["LOG_PERIOD"]) == 0:
            lr = optimizer.param_groups[0]['lr']
            elapsed = time.time() - start_time
            avg_time = elapsed / (iteration - start_iter + 1) if iteration > start_iter else 0
            eta_seconds = avg_time * (max_iter - iteration)
            eta_str = str(time.strftime("%H:%M:%S", time.gmtime(eta_seconds)))

            with torch.no_grad():
                metrics = calculate_metrics(logits, labels)

            log_msg = (
                f"Iter: {iteration}/{max_iter} | "
                f"Loss: {loss.item():.4f} | "
                f"Acc: {metrics['acc']:.2%} | "
                f"LR: {lr:.6f} | "
                f"ETA: {eta_str}"
            )
            logger.debug(log_msg)

        if iteration % int(cfg["PERIODS"]["CHECKPOINT_PERIOD"]) == 0:
            checkpointer.save("last_checkpoint", iteration)

        if iteration % int(cfg["PERIODS"]["EVAL_PERIOD"]) == 0 and iteration > 0:
            logger.info(f"ITER: {iteration}/{max_iter} | Starting evaluation on validation set...")
            model.eval()
            val_loss_sum = 0.0
            val_metrics_sum = {"acc": 0.0, "f1": 0.0, "precision": 0.0, "recall": 0.0}
            num_batches = 0

            with torch.no_grad():
                for val_batch in val_loader:
                    v_event = val_batch["event_ids"].to(device)
                    v_time = val_batch["time_feats"].to(device)
                    v_len = val_batch["lengths"].to(device)
                    v_lbl = val_batch["labels"].to(device)

                    # --- ABLATION STUDY: Wyzerowanie czasu ---
                    v_time = torch.zeros_like(v_time)
                    # -----------------------------------------

                    v_logits = model(v_event, v_time, v_len)
                    v_loss = criterion(v_logits, v_lbl)

                    val_loss_sum += v_loss.item()
                    batch_mets = calculate_metrics(v_logits, v_lbl)
                    for k in val_metrics_sum:
                        val_metrics_sum[k] += batch_mets[k]
                    num_batches += 1

            avg_loss = val_loss_sum / num_batches
            avg_mets = {k: v / num_batches for k, v in val_metrics_sum.items()}

            logger.info(f"EVAL RESULT | Loss: {avg_loss:.4f} | F1: {avg_mets['f1']:.4f} | Acc: {avg_mets['acc']:.2%}")
            
            if avg_mets['f1'] > best_val_f1:
                best_val_f1 = avg_mets['f1']
                checkpointer.save("best_checkpoint", iteration, extra={"f1": best_val_f1})
                logger.info(f"New best model saved! F1: {best_val_f1:.4f}")

            model.train()

    final_path = output_dir / "final"
    final_path.mkdir(exist_ok=True)
    torch.save(model.state_dict(), final_path / "model_final.pth")
    logger.info(f"Training completed. Final model saved to {final_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train LOGTransformerFusion")
    parser.add_argument("--config", type=str, required=True, help="Path to config.yaml")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--num-gpus", type=int, default=1, help="Number of GPUs (0 for CPU)")
    args = parser.parse_args()

    main(args)

# e.g. python train_net.py --config configs/config_transformer.yaml --num-gpus 1