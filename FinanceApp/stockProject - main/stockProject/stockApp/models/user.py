from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid


class CustomUser(AbstractUser):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True, editable=False)
    
    name = models.CharField(max_length=150)
    surname = models.CharField(max_length=150)
    
    money = models.FloatField(default=0.0)
    moneyAfterTransactions = models.FloatField(default=0.0)
    
    role = models.CharField(max_length=150)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.username} ({self.name} {self.surname})"

    @property
    def money_after_transactions(self) -> float:
        return self.moneyAfterTransactions