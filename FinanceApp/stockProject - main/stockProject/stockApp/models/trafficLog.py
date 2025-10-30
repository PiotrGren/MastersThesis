from django.db import models

class TrafficLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    requestId = models.CharField(max_length=64, db_index=True)  # [WHY] nazwa spójna z resztą
    apiTime = models.FloatField()
    userClass = models.CharField(max_length=255, default='WebsiteActiveUser', db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['userClass', 'timestamp']),
        ]