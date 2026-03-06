# Spójny kanał błędów/wyjątków: aplikacja, Celery, integracje.
# 1 rekord = 1 zdarzenie (łatwy export do JSONL).
from django.db import models
import uuid

def gen_uuid_str():
    return str(uuid.uuid4())

class ErrorLog(models.Model):
    class Level(models.TextChoices):
        ERROR = 'ERROR', 'ERROR'
        WARN  = 'WARN',  'WARN'

    # Identyfikatory
    error_id = models.CharField(
        max_length=64,
        default=gen_uuid_str,
        unique=True,
        db_index=True,
        help_text="Unikalny identyfikator zdarzenia (UUID)."
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Czas wystąpienia błędu (UTC)."
    )

    # Klasyfikacja
    level = models.CharField(
        max_length=10,
        choices=Level.choices,
        default=Level.ERROR,
        db_index=True,
        help_text="Poziom błędu (ERROR/WARN)."
    )
    component = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Moduł/serwis (np. api/matcher/db/queue)."
    )

    # Korelacja z przepływem
    request_id = models.CharField(
        max_length=64,
        null=True, blank=True,
        db_index=True,
        help_text="Jeśli błąd dotyczy konkretnego żądania HTTP."
    )
    parent_request_id = models.CharField(
        max_length=64,
        null=True, blank=True,
        db_index=True,
        help_text="Jeśli błąd dot. transakcji powiązanej z żądaniem."
    )

    # Treść błędu
    error_code = models.CharField(
        max_length=64,
        null=True, blank=True,
        db_index=True,
        help_text="Skrócony kod (np. DB.TIMEOUT, VALIDATION)."
    )
    message = models.CharField(
        max_length=2048,
        help_text="Krótki opis błędu (1-2 zdania)."
    )
    # Uwaga: w JSONL new-line zostanie zapisany jako \n (OK)
    stack = models.TextField(
        null=True, blank=True,
        help_text="Opcjonalny stacktrace (tekst)."
    )
    context = models.JSONField(
        null=True, blank=True,
        help_text="Dodatkowy kontekst (np. parametry wejściowe)."
    )

    # Kontekst środowiska
    service_name = models.CharField(
        max_length=64, null=True, blank=True, db_index=True,
        help_text="Nazwa usługi (np. web/celery-worker)."
    )
    container_id = models.CharField(
        max_length=64, null=True, blank=True, db_index=True,
        help_text="Identyfikator kontenera przetwarzającego."
    )
    env = models.CharField(
        max_length=32, null=True, blank=True, db_index=True,
        help_text="Środowisko (dev/test/prod)."
    )
    service_version = models.CharField(
        max_length=64, null=True, blank=True, db_index=True,
        help_text="Wersja serwisu (tag/commit)."
    )

    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['level', 'timestamp']),
            models.Index(fields=['component', 'timestamp']),
            models.Index(fields=['request_id', 'timestamp']),
            models.Index(fields=['service_name', 'env', 'timestamp']),
        ]
        verbose_name = "Error Log"
        verbose_name_plural = "Error Logs"

    def __str__(self):
        return f"{self.timestamp} {self.level} {self.component}: {self.error_code or ''} {self.message[:60]}"
