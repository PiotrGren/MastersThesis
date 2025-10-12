from django.db import models

class Cpu(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    cpuUsage = models.FloatField()
    memoryUsage = models.FloatField()
    
    # [WHY] poprawa literówki + dłuższe ID (docker/k8s)
    contenerId = models.CharField(max_length=64, db_index=True)

    # [WHY] opcjonalne, ale użyteczne w korelacjach
    service = models.CharField(max_length=64, null=True, blank=True, db_index=True)   # np. web/celery/redis
    env = models.CharField(max_length=32, null=True, blank=True, db_index=True)       # dev/test/prod

    class Meta:
        indexes = [
            models.Index(fields=['containerId', 'timestamp']),
            models.Index(fields=['service', 'timestamp']),
        ]