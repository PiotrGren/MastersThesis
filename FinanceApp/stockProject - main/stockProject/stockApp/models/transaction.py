from django.db import models
from .sellOffer import SellOffer
from .buyOffer import BuyOffer

class Transaction(models.Model):
    buyOffer = models.ForeignKey(BuyOffer, on_delete=models.CASCADE)
    sellOffer = models.ForeignKey(SellOffer, on_delete=models.CASCADE)
    amount = models.IntegerField()
    price = models.FloatField()
    totalPrice = models.FloatField()
    transacionDate = models.DateTimeField(auto_now_add=True)
