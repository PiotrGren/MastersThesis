from django.db import models
from django.contrib.postgres.fields import JSONField


# [WHY] RequestLog zastąpi całkowicie marketLog oraz trafficLog w jedną spójną tabelę z kompleksowymi danymi, będzie to łatwiejsze do logowania i dane będą lepsze dla modelu (bardziej złożone i dokładne)

class RequestLog(models.Model):
    request_id = models.CharField(max_length=64, db_index=True)
    session_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    
    # Kontekst użytkownika (bez PII)
    user_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)   # np. CustomUser.public_id
    user_role = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    user_class = models.CharField(max_length=64, null=True, blank=True, db_index=True)

    # Czas i podstawy HTTP
    timestamp = models.DateTimeField(db_index=True)                 # czas przyjęcia żądania (UTC)
    api_method = models.CharField(max_length=8, db_index=True)      # GET/POST/...
    endpoint = models.CharField(max_length=2048)                    # pełna ścieżka
    endpoint_group = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    
    # Wynik HTTP
    http_status = models.IntegerField()
    success = models.BooleanField(default=False)

    # Czasy (ms)
    latency_ms_total = models.FloatField()
    app_time_ms = models.FloatField(null=True, blank=True)
    db_time_ms = models.FloatField(null=True, blank=True)
    queue_time_ms = models.FloatField(null=True, blank=True)
    network_time_ms = models.FloatField(null=True, blank=True)

    # Dodatkowy kontekst żądania
    response_size = models.IntegerField(null=True, blank=True)
    user_agent_hash = models.CharField(max_length=64, null=True, blank=True)
    client_ip_hash = models.CharField(max_length=64, null=True, blank=True)
    
    # Kontekst środowiska
    service_name = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    container_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    service_version = models.CharField(max_length=64, null=True, blank=True, db_index=True)

    # Surowe konteksty
    request_context = models.JSONField(null=True, blank=True)       # np. nagłówki, payload_size itp.
    error_context = models.JSONField(null=True, blank=True)         # komunikat/stack przy błędzie
    
    env = models.CharField(max_length=32, null=True, blank=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['request_id', 'timestamp']),
            models.Index(fields=['user_id', 'session_id', 'timestamp']),
            models.Index(fields=['endpoint_group', 'timestamp']),
            models.Index(fields=['service_name', 'env', 'timestamp']),
        ]
        verbose_name = "Request Log"
        verbose_name_plural = "Request Logs"

    def __str__(self):
        return f"{self.timestamp} {self.api_method} {self.endpoint} [{self.http_status}]"