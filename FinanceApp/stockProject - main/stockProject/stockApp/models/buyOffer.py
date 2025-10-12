from django.db import models
from .user import CustomUser
from .company import Company


class BuyOffer(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='buy_offers')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='buy_offers')
    maxPrice = models.FloatField(default=0.0)
    startAmount = models.IntegerField(default=1)
    amount = models.IntegerField()
    
    # [WHY] dodany indeks db - przyspieszane expireOffers
    dateLimit = models.DateTimeField(db_index=True)
    actual = models.BooleanField(default=True)
    
    # --- NOWE POD LOGI I STABILNOŚĆ ---
    # [WHY] semantyka oferty (czytelniejsze od boola)
    STATUS_CHOICES = (
        ('active', 'ACTIVE'),
        ('matched', 'MATCHED'),
        ('expired', 'EXPIRED'),
        ('cancelled', 'CANCELLED'),
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='active', db_index=True)
    
    # [WHY] korelacja HTTP → JSONL - opcjonalne, żeby nie ruszać obecnych wywołań
    request_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    session_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    
    # [WHY] analizy czasowe / porządki w logach
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        constraints = [
            # [WHY] obie ilości nie mogą zejść poniżej 0 (ochrona przy matcherze)
            models.CheckConstraint(check=models.Q(amount__gte=0), name='buyoffer_amount_nonneg'),
            models.CheckConstraint(check=models.Q(startAmount__gte=0), name='buyoffer_start_amount_nonneg'),
        ]
        indexes = [
            # [WHY] matcher bierze najlepsze ceny w ramach spółki - to przyspiesza:
            models.Index(fields=['company', 'status', 'maxPrice']),
            models.Index(fields=['company', 'actual', 'maxPrice']),
            # [WHY] szybkie wyszukanie ofert użytkownika
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"BUY #{self.pk} u={self.user} c={self.company} amt={self.amount} max={self.maxPrice} [{self.status}]"