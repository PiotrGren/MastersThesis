from django.db import models
from .user import CustomUser

class BalanceUpdate(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='balance_updates')
    changeAmount = models.FloatField()
    
    # [WHY] spójne nazwy wartości, bez literówek (logi/JSONL będą miały stały enum)
    CHANGE_CHOICES = (
        ('money', 'money'),
        ('moneyAfterTransactions', 'moneyAfterTransactions'),
    )
    changeType = models.CharField(max_length=40, choices=CHANGE_CHOICES, db_index=True)
    
    createdAt = models.DateTimeField(auto_now_add=True)

    # [WHY] zamiast "actual" (niejednoznaczne) dodajemy flagę zastosowania pozycji księgi:
    # processBalanceUpdates ustawi applied=True + appliedAt, nic nie kasujemy → pełny audyt do AI
    applied = models.BooleanField(default=False, db_index=True)  # [WHY] index - szybkie filtrowanie batcha
    appliedAt = models.DateTimeField(null=True, blank=True)
    
    # [WHY] korelacja z żądaniem/API/scenariuszem testowym (opcjonalne pola)
    request_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    session_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'applied', 'changeType']),
            models.Index(fields=['createdAt']),
        ]