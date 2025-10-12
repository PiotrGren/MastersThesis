from django.db import models
from .user import CustomUser

class BalanceUpdate(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    changeAmount = models.FloatField()
    changeType = models.CharField(max_length=40, choices=[('money', 'Money'), ('moneyAfterTransactions', 'Money After Transactions')])
    createdAt = models.DateTimeField(auto_now_add=True)
    actual = models.BooleanField(default=True)
