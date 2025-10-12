from django.db import models

class Cpu(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    cpuUsage = models.FloatField()
    memoryUsage = models.FloatField()
    contenerId = models.CharField()