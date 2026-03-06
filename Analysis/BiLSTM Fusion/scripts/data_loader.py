import torch
from torch.utils.data import Dataset, DataLoader
from torch.nn.utils.rnn import pad_sequence
from typing import List, Dict, Any, Iterator

class FusionDataset(Dataset):
    """
    Prosty wrapper na listę słowników zapisaną przez process_data.py.
    Oczekuje formatu: [{'event_ids': tensor, 'time_feats': tensor, 'label': int, ...}, ...]
    """
    def __init__(self, data_path: str):
        print(f"Loading data from {data_path} ...")
        # torch.load bezpiecznie wczytuje listę zapisaną w process_data.py
        self.data = torch.load(data_path, weights_only=False)
        print(f"Loaded {len(self.data)} sequences.")

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        return self.data[idx]

class FusionCollator:
    """
    Odpowiada za padding sekwencji w batchu.
    BiLSTM wymaga, aby wszystkie sekwencje w tensorze miały ten sam wymiar [B, T_max].
    """
    def __init__(self, pad_id: int = 0):
        self.pad_id = pad_id

    def __call__(self, batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Wyciągamy poszczególne elementy z listy słowników
        event_ids_list = [item['event_ids'] for item in batch]
        time_feats_list = [item['time_feats'] for item in batch]
        labels_list = [item['label'] for item in batch]
        session_ids = [item['session_id'] for item in batch]

        # 1. Obliczamy długości (potrzebne dla pack_padded_sequence w modelu)
        lengths = torch.tensor([len(x) for x in event_ids_list], dtype=torch.long)

        # 2. Padding (batch_first=True -> [Batch, Time])
        # event_ids: padding wartością pad_id (np. 0)
        event_ids_padded = pad_sequence(event_ids_list, batch_first=True, padding_value=self.pad_id)
        
        # time_feats: padding zerami (0.0) -> [Batch, Time, Features]
        time_feats_padded = pad_sequence(time_feats_list, batch_first=True, padding_value=0.0)

        # 3. Labels -> Tensor
        labels = torch.tensor(labels_list, dtype=torch.long)

        return {
            "event_ids": event_ids_padded,
            "time_feats": time_feats_padded,
            "lengths": lengths,
            "labels": labels,
            "session_ids": session_ids
        }

class InfiniteDataLoader:
    """
    Wrapper, który sprawia, że DataLoader nigdy się nie kończy (dla treningu opartego na iteracjach).
    Gdy skończy się epoka, automatycznie resetuje iterator.
    """
    def __init__(self, data_loader: DataLoader):
        self.data_loader = data_loader
        self.iterator = iter(data_loader)

    def __iter__(self):
        return self

    def __next__(self):
        try:
            batch = next(self.iterator)
        except StopIteration:
            # Koniec epoki -> tasujemy i zaczynamy od nowa
            self.iterator = iter(self.data_loader)
            batch = next(self.iterator)
        return batch

def build_data_loader(
    data_path: str, 
    batch_size: int, 
    is_train: bool = True, 
    num_workers: int = 2,
    infinite: bool = False
) -> DataLoader | InfiniteDataLoader:
    
    dataset = FusionDataset(data_path)
    collator = FusionCollator(pad_id=0) # Zakładamy, że 0 to padding w vocab

    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=is_train,       # Tasuj tylko treningowe
        num_workers=num_workers,
        collate_fn=collator,
        pin_memory=True,        # Szybszy transfer na GPU
        drop_last=is_train      # Ucinamy ostatni niepełny batch w treningu
    )

    if infinite:
        return InfiniteDataLoader(loader)
    return loader