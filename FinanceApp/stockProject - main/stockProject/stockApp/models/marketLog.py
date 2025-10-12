from django.db import models

class MarketLog(models.Model):
    class ApiMethod(models.TextChoices):
        GET = 'GET', 'GET'
        POST = 'POST', 'POST'
        PUT = 'PUT', 'PUT'
        DELETE = 'DELETE', 'DELETE'

    timestamp = models.DateTimeField(auto_now_add=True)
    apiMethod = models.CharField(max_length=10, choices=ApiMethod.choices)
    applicationTime = models.FloatField()
    databaseTime = models.FloatField()
    endpointUrl = models.URLField()
    requestId = models.CharField(max_length=255)

