from django.db import models

class TrafficLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    requestid = models.CharField(max_length=255)
    apiTime = models.FloatField()
    userClass = models.CharField(max_length=255,default='WebsiteActiveUser')
