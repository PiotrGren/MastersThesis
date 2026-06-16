from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch
import torch.nn as nn


@dataclass
class LOGTransformerConfig:
    # --- Słownik i Wymiary ---
    vocab_size: int
    d_model: int = 128                  # Główny wymiar modelu (wspólny dla eventów, czasu i pozycji)
    
    # --- Cechy Czasowe ---
    time_feat_dim: int = 4              # [latency_ms, db_time_ms, app_time_ms, delta_t]
    time_mlp_hidden: int = 256
    
    # --- Transformer Encoder ---
    nhead: int = 8                      # Liczba głów atencji
    num_layers: int = 4                 # Liczba warstw enkodera
    dim_feedforward: int = 512          # Wymiar warstwy ukrytej w FeedForward wewnątrz Transformera
    max_seq_len: int = 500              # Maksymalna długość sesji dla Positional Encoding

    # --- Klasyfikator ---
    num_classes: int = 5
    head_hidden: int = 256

    # --- Regularyzacja ---
    dropout: float = 0.2

    # --- Misc ---
    pad_id: int = 0
    cls_id: int = 2


class TimeProjector(nn.Module):
    """
    Mapuje ciągłe cechy czasowe z wymiaru K na wymiar d_model
    [B, T, K] -> [B, T, d_model]
    """
    def __init__(self, in_dim: int, hidden: int, out_dim: int, dropout: float):
        super().__init__()
        self.ln = nn.LayerNorm(in_dim)
        self.mlp = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, out_dim)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.mlp(self.ln(x))
    

class LOGTransformerFusion(nn.Module):
    """
    Architektura Transformer z podwójnym wejściem dla analizy logów.
    Integruje dyskretne zdarzenia i ciągłe czasy z użyciem tokena <CLS>
    """
    def __init__(self, cfg: LOGTransformerConfig):
        super().__init__()
        self.cfg = cfg

        # 1. Osadzenia Zdarzeń (Event Embeddings)
        self.event_emb = nn.Embedding(
            num_embeddings=cfg.vocab_size,
            embedding_dim=cfg.d_model,
            padding_idx=cfg.pad_id,
        )

        # 2. Projekcja Czas (Time Embeddings)
        self.time_proj = TimeProjector(
            in_dim=cfg.time_feat_dim,
            hidden=cfg.time_mlp_hidden,
            out_dim=cfg.d_model,
            dropout=cfg.dropout
        )

        # 3. Kodowanie Pozycyjne (Learnable Positional Encoding)
        # Utworzenie wyuczalnej macierzy pozycji, ponieważ logi mają specyficzny układ
        self.pos_emb = nn.Embedding(
            num_embeddings=cfg.max_seq_len,
            embedding_dim=cfg.d_model
        )

        # 4. Fuzja (LayerNorm + Dropout po zsumowaniu wejść)
        self.fuse_ln = nn.LayerNorm(cfg.d_model)
        self.fuse_drop = nn.Dropout(cfg.dropout)

        # 5. Stos Enkodera (Transformer Blocks)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=cfg.d_model,
            nhead=cfg.nhead,
            dim_feedforward=cfg.dim_feedforward,
            dropout=cfg.dropout,
            activation='gelu',
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(
            encoder_layer,
            num_layers=cfg.num_layers
        )

        # 6. Klasyfikator (czyta tylko wektor z pozycji <CLS>)
        self.head = nn.Sequential(
            nn.LayerNorm(cfg.d_model),
            nn.Linear(cfg.d_model, cfg.head_hidden),
            nn.GELU(),
            nn.Dropout(cfg.dropout),
            nn.Linear(cfg.head_hidden, cfg.num_classes)
        )

        self.__init_weights()

    def __init_weights(self):
        """Inicjalizacja wag wzroowana na podejściu modeli BERT."""
        for name, p in self.named_parameters():
            if p.dim() > 1:
                # Kasawier/Glorot dla macierzy wag
                nn.init.xavier_uniform_(p)

        # Zerowanie wektora paddingu
        if self.cfg.pad_id is not None:
            with torch.no_grad():
                self.event_emb.weight[self.cfg.pad_id].fill_(0.0)

    def forward(self, event_ids: torch.Tensor, time_feats: torch.Tensor, lengths: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Przetwarza sekwencję zdarzeń i odpowiadające cechy czasowe.
        
        Args:
            event_ids: [B, T] (int64) - Tokeny (pierwszy to zawsze <CLS>)
            time_feats: [B, T, K] (float32) - Znormalizowane wektory czasu
            lengths: [B] (int64) - Długości sekwencji

        Returns:
            logits: [B, num_classes] - Wyniki klasyfikacji
        """
        B, T = event_ids.shape
        device = event_ids.device

        # Upewnienie czy nie przekroczono max_seq_len (przycinanie, jeśli trzeba)
        if T > self.cfg.max_seq_len:
            event_ids = event_ids[:, :self.cfg.max_seq_len]
            time_feats = time_feats[:, :self.cfg.max_seq_len]
            T = self.cfg.max_seq_len

        # Generowanie wektorów pozycji: [0, 1, 2, ..., T-1] dla każdego elementu w batchu
        positions = torch.arange(0, T, device=device).unsqueeze(0).expand(B, T)

        # --- ETAP 1: Early Fusion ---
        e = self.event_emb(event_ids)               # [B, T, d_model]
        t = self.time_proj(time_feats)              # [B, T, d_model]
        p = self.pos_emb(positions)                 # [B, T, d_model]

        x = e + p + t
        x = self.fuse_drop(self.fuse_ln(x))

        # --- ETAP 2: Maskowanie Paddingu ---
        src_key_padding_mask = (event_ids == self.cfg.pad_id)

        # --- ETAP 3: Transformer ---
        # x: [B, T, d_model]
        # output: [B, T, d_model]
        encoded = self.transformer(
            src=x,
            src_key_padding_mask=src_key_padding_mask
        )

        # --- ETAP 4: Wyodrębnienie <CLS> i Klasyfikacja ---
        # Zgodnie z konwencją BERT, bierzemy pierwszy token sekwencji z każdego batcha
        cls_output = encoded[:, 0, :]               # [B, d_model]
        
        logits = self.head(cls_output)              # [B, num_classes]

        return logits