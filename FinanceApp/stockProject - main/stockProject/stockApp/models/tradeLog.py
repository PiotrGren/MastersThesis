from django.db import models

class TradeLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    applicationTime = models.FloatField()
    databaseTime = models.FloatField()
    numberOfSellOffers = models.IntegerField()
    numberOfBuyOffers = models.IntegerField()
    companyIds = models.JSONField()
