from django.db import models

class Cpu(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    cpuUsage = models.FloatField()
    memoryUsage = models.FloatField()

    # Stare pole zostaje dla kompatybilności - trzeba sprawdzić czy jest gdzieś używane najpierw
    # contenerId = models.CharField(max_length=64, null=True, blank=True)

    # Nowe, poprawne pole z indeksami
    containerId = models.CharField(max_length=64, db_index=True)

    service = models.CharField(max_length=64, null=True, blank=True, db_index=True)   # np. web/celery
    env = models.CharField(max_length=32, null=True, blank=True, db_index=True)       # dev/test/prod

    class Meta:
        indexes = [
            models.Index(fields=['containerId', 'timestamp']),
            models.Index(fields=['service', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.timestamp} {self.service or ''} {self.containerId}"