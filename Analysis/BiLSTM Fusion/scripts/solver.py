import torch
from torch.optim.lr_scheduler import MultiStepLR, LambdaLR, SequentialLR

def build_optimizer(model: torch.nn.Module, cfg: dict):
    """
    Tworzy optymalizator na podstawie configu (SOLVER).
    """
    lr = float(cfg['BASE_LR'])
    weight_decay = float(cfg.get('WEIGHT_DECAY', 0.0))
    opt_name = cfg.get('OPTIMIZER', 'AdamW')

    # Separacja parametrów: zazwyczaj nie dajemy weight_decay na biasach i LayerNorm
    # Ale dla uproszczenia w Baseline wrzucamy wszystko.
    params = model.parameters()

    if opt_name == 'AdamW':
        return torch.optim.AdamW(params, lr=lr, weight_decay=weight_decay)
    elif opt_name == 'SGD':
        return torch.optim.SGD(params, lr=lr, momentum=0.9, weight_decay=weight_decay)
    else:
        raise ValueError(f"Unknown optimizer: {opt_name}")

def build_scheduler(optimizer, cfg: dict):
    """
    Tworzy Scheduler: Warmup (Linear) + MultiStepLR (Decay).
    """
    steps = cfg.get('STEPS', [])
    gamma = float(cfg.get('GAMMA', 0.1))
    warmup_iters = int(cfg.get('WARMUP_ITERS', 0))
    warmup_factor = float(cfg.get('WARMUP_FACTOR', 0.001))
    max_iter = int(cfg['MAX_ITER'])

    # 1. Główny scheduler (skokowa zmiana LR)
    main_scheduler = MultiStepLR(optimizer, milestones=steps, gamma=gamma)

    if warmup_iters > 0:
        # 2. Warmup scheduler
        def warmup_fn(iter_idx):
            if iter_idx >= warmup_iters:
                return 1.0
            alpha = float(iter_idx) / warmup_iters
            return warmup_factor * (1 - alpha) + alpha

        warmup_sched = LambdaLR(optimizer, lr_lambda=warmup_fn)
        
        # Łączymy: najpierw Warmup przez warmup_iters, potem MultiStep
        # SequentialLR wymaga PyTorch >= 1.10
        return SequentialLR(
            optimizer, 
            schedulers=[warmup_sched, main_scheduler], 
            milestones=[warmup_iters]
        )
    
    return main_scheduler