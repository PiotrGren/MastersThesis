from django.db import models

class TradeLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    applicationTime = models.FloatField()
    databaseTime = models.FloatField()
    numberOfSellOffers = models.IntegerField()
    numberOfBuyOffers = models.IntegerField()
    companyIds = models.JSONField()
    
    # --- NOWE POD ANALIZĘ/AI ---
    # [WHY] korelacja zadania Celery i żądania, które uruchomiło przepływ (opcjonalne) - najwyżej usuniemy
    task_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    parent_request_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)

    # [WHY] jakościowe metryki cyklu (świetne dla klasyfikacji/sekwencji)
    matchedPairs = models.IntegerField(default=0)
    partialFills = models.IntegerField(default=0)
    rejectedOffers = models.IntegerField(default=0)

    # [WHY] szybkie feature’y czasowe
    queueTimeMs = models.FloatField(default=0.0)
    cycleTimeMs = models.FloatField(default=0.0)

    # [WHY] miejsce na agregaty per spółka/histogramy, bez migracji schematu przy zmianach
    details = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['task_id']),
            models.Index(fields=['parent_request_id']),
        ]