from django.db import models
from .company import Company
from django.db.models import Q


class StockRate(models.Model):
    actual = models.BooleanField(default=True)
    rate = models.FloatField(default=0.0)
    
    # [WHY] dodałem indeks db - szybkie sortowanie po najświeższych kursach
    dateInc = models.DateTimeField(db_index = True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='rates')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['company'], condition=Q(actual=True),
                name='uniq_stockrate_actual_per_company'
            ),
        ]
        indexes = [
            models.Index(fields=['company', 'dateInc']),
            models.Index(fields=['company', 'actual']),
        ]
        
    def __str__(self):
        return f"{self.company} @ {self.rate} ({'actual' if self.actual else 'hist'})"