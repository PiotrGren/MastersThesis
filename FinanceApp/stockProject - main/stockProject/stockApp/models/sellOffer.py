from django.db import models
from .user import CustomUser
from .stock import Stock
from .company import Company
from django.utils import timezone


class SellOffer(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sell_offers')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='sell_offers')
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='sell_offers')
    
    minPrice = models.FloatField(default=0.0)
    startAmount = models.IntegerField(default=1)
    amount = models.IntegerField()
    
    dateLimit = models.DateTimeField(db_index=True)
    actual = models.BooleanField(default=True)
    
    
    # Status oferty modeluje pełny cykl życia (ACTIVE/MATCHED/EXPIRED/CANCELLED), co jednoznacznie rozróżnia intencję od rezultatu.
    # Dzięki temu w analizie/uczeniu model może łączyć wzorce zachowań (np. sekwencje zdarzeń i metryki) z konkretnymi wynikami rynkowymi oferty.
    STATUS_CHOICES = (
        ('active', 'ACTIVE'),
        ('matched', 'MATCHED'),
        ('expired', 'EXPIRED'),
        ('cancelled', 'CANCELLED'),
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='active', db_index=True)

    # [WHY] korelacja pod logi/JSONL - to samo co buyOffer
    request_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    session_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)

    # [WHY] analizy czasowe
    created_at = models.DateTimeField(default=timezone.now, editable=False)#auto_now_add=True)
    updated_at = models.DateTimeField(default=timezone.now)#auto_now=True)
    
    class Meta:
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gte=0), name='selloffer_amount_nonneg'),
            models.CheckConstraint(check=models.Q(startAmount__gte=0), name='selloffer_start_amount_nonneg'),
        ]
        indexes = [
            # [WHY] matcher szuka najniższych cen sprzedaży w spółce
            models.Index(fields=['company', 'status', 'minPrice']),
            models.Index(fields=['company', 'actual', 'minPrice']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"SELL #{self.pk} u={self.user} c={self.company} amt={self.amount} min={self.minPrice} [{self.status}]"