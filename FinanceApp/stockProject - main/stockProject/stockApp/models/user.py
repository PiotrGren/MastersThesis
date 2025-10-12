from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    name = models.CharField(max_length=150)
    surname = models.CharField(max_length=150)
    money = models.FloatField(default=0.0)
    moneyAfterTransations = models.FloatField(default=0.0)
    role = models.CharField(max_length=150)

    def __str__(self):
        return f"{self.username} ({self.name} {self.surname})"
