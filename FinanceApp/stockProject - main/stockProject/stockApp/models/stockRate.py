from django.db import models
from .company import Company

class StockRate(models.Model):
    actual = models.BooleanField(default=True)
    rate = models.FloatField(default=0.0)
    dateInc = models.DateTimeField()
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
