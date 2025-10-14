from django.db import models

class MarketLog(models.Model):
    class ApiMethod(models.TextChoices):
        GET = 'GET', 'GET'
        POST = 'POST', 'POST'
        PUT = 'PUT', 'PUT'
        DELETE = 'DELETE', 'DELETE'

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    apiMethod = models.CharField(max_length=10, choices=ApiMethod.choices, db_index=True)
    applicationTime = models.FloatField()
    databaseTime = models.FloatField()
    
    # [WHY] URLField bywa zbyt restrykcyjny / za krótki; CharField jest bezpieczniejszy do surowych ścieżek
    endpointUrl = models.CharField(max_length=2048)
    
    # [WHY] korelacja HTTP↔oferty↔transakcje; indeks pod joiny/log export
    requestId = models.CharField(max_length=64, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['requestId', 'timestamp']),
            models.Index(fields=['apiMethod', 'timestamp']),
        ]