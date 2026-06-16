from django.db import models
from .sellOffer import SellOffer
from .buyOffer import BuyOffer

class Transaction(models.Model):
    buyOffer = models.ForeignKey(BuyOffer, on_delete=models.CASCADE, related_name='transactions')
    sellOffer = models.ForeignKey(SellOffer, on_delete=models.CASCADE, related_name='transactions')

    amount = models.IntegerField()
    price = models.FloatField()
    totalPrice = models.FloatField()
    transacionDate = models.DateTimeField(auto_now_add=True, db_index=True)

    # --- NOWE POD LOGI/AI ---
    # [WHY] korelacja HTTP ↔ Celery ↔ DB; opcjonalne (nie łamią istniejących wywołań)
    request_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    task_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)

    # [WHY] szybki dostęp bez joinów (opcjonalna denormalizacja)
    buyer_id_cache = models.IntegerField(null=True, blank=True, db_index=True)
    seller_id_cache = models.IntegerField(null=True, blank=True, db_index=True)

    class Meta:
        constraints = [
            # [WHY] prosta walidacja spójności biznesowej; jeśli za wcześnie na Decimal, walidujemy przybliżeniem:
            models.CheckConstraint(
                check=models.Q(totalPrice__gte=0),  # minimalna ochrona, resztę zrobimy w serializerze/tasku
                name='txn_totalprice_nonneg'
            ),
        ]
        indexes = [
            models.Index(fields=['transacionDate']),
            models.Index(fields=['request_id']),
            models.Index(fields=['task_id']),
        ]

    def __str__(self):
        return f"TXN #{self.pk} buy={self.buyOffer} sell={self.sellOffer} amt={self.amount} price={self.price}"
