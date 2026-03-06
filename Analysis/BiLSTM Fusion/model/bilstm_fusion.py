from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class BiLSTMFusionConfig:
    # --- event embedding ---
    vocab_size: int
    event_embed_dim: int = 128
    
    # --- time features ---
    time_feat_dim: int = 4              # [latency_ms, db_time_ms, app_time_ms, delta_t]
    time_embed_dim: int = 64
    time_mlp_hidden: int = 128
    
    # --- sequence encoder ---
    lstm_hidden: int = 192
    lstm_layers: int = 1
    bidirectional: bool = True
    
    # --- heads ---
    num_classes: int = 3
    head_hidden: int = 256
    
    # --- regularization ---
    dropout: float = 0.25
    attn_dropout: float = 0.10
    
    # --- misc ---
    pad_id: int = 0
    use_attention_pooling: bool = True
    
    
class TimeMLP(nn.Module):
    """
    Mapuje cechy czasoe per request: [B, T, K] -> [B, T, time_embed_dim]
    Uwaga: nomralizację (log1p, standaryzację) przeprowadza się w pipline danych, tutaj dodajemy jedynie LayerNorm dla stabilności.
    """
    def __init__(self, in_dim: int, hidden: int, out_dim: int, dropout: float):
        super().__init__()
        self.ln = nn.LayerNorm(in_dim)
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, out_dim),
            nn.GELU(),
        )
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(self.ln(x)) # x: [B, T, K]
    

class AttnPooling(nn.Module):
    """
    Attention pooling po czasie z maską padding
    Zwraca reprezentację [B, D]
    """
    def __init__(self, dim: int, dropout: float):
        super().__init__()
        self.score = nn.Linear(dim, 1)
        self.dropout = nn.Dropout(dropout)
        
    def forward(self, x: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        """
        x:      [B, T, D]
        mask:   [B, T]    True dla pozycji "ważnych" (nie-padding)
        """
        logits = self.score(self.dropout(x)).squeeze(-1)  # [B, T]
        
        # padding dostaje -inf, żeby softmax go wyzerował
        logits = logits.masked_fill(~mask, float("-inf"))
        attn = torch.softmax(logits, dim=-1)
        
        # na wypadek sekwencji o długości 0 (wszystko padding) - zabiezpieczamy softax NaN
        attn = torch.nan_to_num(attn, nan=0.0)
        
        pooled = torch.bmm(attn.unsqueeze(1), x).squeeze(1)
        return pooled
    
    
class BiLSTMFusion(nn.Module):
    """
    BiLSTM do klasyfikacji użytkowników z dwoma wejściami:
        1) event_ids: [B, T] - sekwencja eventów (int)
        2) time_fets: [B, T, K] - cechy czasowe per event (float)
        
    Wyjście:
        logits: [B, num_classes]
    """
    def __init__(self, cfg: BiLSTMFusionConfig):
        super().__init__()
        self.cfg = cfg
        
        self.event_emb = nn.Embedding(
            num_embeddings=cfg.vocab_size,
            embedding_dim=cfg.event_embed_dim,
            padding_idx=cfg.pad_id,
        )
        
        self.time_mlp = TimeMLP(
            in_dim=cfg.time_feat_dim,
            hidden=cfg.time_mlp_hidden,
            out_dim=cfg.time_embed_dim,
            dropout=cfg.dropout,
        )
        
        fused_dim = cfg.event_embed_dim + cfg.time_embed_dim
        
        self.fuse_ln = nn.LayerNorm(fused_dim)
        self.fuse_drop = nn.Dropout(cfg.dropout)
        
        self.lstm = nn.LSTM(
            input_size=fused_dim,
            hidden_size=cfg.lstm_hidden,
            num_layers=cfg.lstm_layers,
            batch_first=True,
            bidirectional=cfg.bidirectional,
            dropout=cfg.dropout if cfg.lstm_layers > 1 else 0.0,
        )
        
        enc_dim = cfg.lstm_hidden * (2 if cfg.bidirectional else 1)
        
        self.use_attention_pooling = cfg.use_attention_pooling
        if self.use_attention_pooling:
            self.pool = AttnPooling(enc_dim, dropout=cfg.attn_dropout)
        else:
            self.pool = None
            
        # --- Klasyfikator ---
        self.head = nn.Sequential(
            nn.LayerNorm(enc_dim),
            nn.Linear(enc_dim, cfg.head_hidden),
            nn.GELU(),
            nn.Dropout(cfg.dropout),
            nn.Linear(cfg.head_hidden, cfg.num_classes),
        )
        
        self._init_weights()

   
    def _init_weights(self):
        # sensowne inits pod LSTM/embedding/linear
        nn.init.normal_(self.event_emb.weight, mean=0.0, std=0.02)
        if self.cfg.pad_id is not None:
            with torch.no_grad():
                self.event_emb.weight[self.cfg.pad_id].fill_(0.0)
                
        for name, p in self.lstm.named_parameters():
            if "weight" in name:
                nn.init.xavier_uniform_(p)
            elif "bias" in name:
                nn.init.constant_(p, 0.0)
                
        for m in self.head:
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                nn.init.constant_(m.bias, 0.0)
                
    
    @staticmethod
    def lengths_to_mask(lengths: torch.Tensor, max_len: int) -> torch.Tensor:
        """
        lengths: [B] (int) - długości sekwencji (bez pddingu)
        returns: [B, T] (bool) - mask, True - valid token
        """
        device = lengths.device
        rng = torch.arange(max_len, device=device).unsqueeze(0)  # [1, T]
        return rng < lengths.unsqueeze(1)               # [B, T]
    
    
    def forward(self, event_ids: torch.Tensor, time_feats: torch.Tensor, lengths: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        event_ids: [B, T] (int64)
        time_feats: [B, T, K] (float32/float16)
        lengths: Optional [B] (int64) - długości sekwencji (bez paddingu)
        """
        assert event_ids.dim() == 2 # event_ids MUSZĄ BYĆ [B, T]
        assert time_feats.dim() == 3 # time_feats MUSZĄ BYĆ [B, T, K]
        B, T = event_ids.shape
        
        if lengths is None:
            lengths = (event_ids != self.cfg.pad_id).sum(dim=1)
        lengths = lengths.clamp(min=1)
        
        mask = self.lengths_to_mask(lengths, T)
        
        e = self.event_emb(event_ids)          # [B, T, E]
        t = self.time_mlp(time_feats)         # [B, T, Te]
        x = torch.cat([e, t], dim=-1)         # [B, T, E + Te]
        x = self.fuse_drop(self.fuse_ln(x))
        
        # pack -> LSTM -> unpack (żeby ignorować padding)
        packed = nn.utils.rnn.pack_padded_sequence(
            x, lengths.cpu(), batch_first=True, enforce_sorted=False
        )
        packed_out, _ = self.lstm(packed)
        out, _ = nn.utils.rnn.pad_packed_sequence(packed_out, batch_first=True, total_length=T) # out: [B, T, enc_dim]
        
        if self.use_attention_pooling:
            pooled = self.pool(out, mask)   # type: ignore
        else:
            out = out.masked_fill(~mask.unsqueeze(-1), 0.0)
            pooled = out.sum(dim=1) / mask.sum(dim=1).unsqueeze(-1)
            
        logits = self.head(pooled)          # [B, num_classes]
        return logits