from django.db import models
from .user import CustomUser
from .stock import Stock
from .company import Company

class SellOffer(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    minPrice = models.FloatField(default=0.0)
    startAmount = models.IntegerField(default=1)
    amount = models.IntegerField()
    dateLimit = models.DateTimeField()
    actual = models.BooleanField(default=True)