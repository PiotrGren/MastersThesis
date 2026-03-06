from __future__ import absolute_import, unicode_literals

import os
from celery import Celery
from celery.schedules import schedule  # proste interwały w sekundach

# Domyślne ustawienia Django dla Celery
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stockProject.settings")

app = Celery("stockProject")

# Konfiguracja z Django (CELERY_*)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-odkrywanie zadań w aplikacjach (stockApp.tasks)
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"[CELERY DEBUG] Request: {self.request!r}")


# --------- Routing / kolejki (czytelne kolejki tematyczne) ---------
app.conf.task_queues = (
    # kolejki są tworzone automatycznie po pierwszym użyciu
)

app.conf.task_routes = {
    "stockApp.tasks.match_scheduler": {"queue": "transactions"},
    "stockApp.tasks.match_execute": {"queue": "transactions"},
    "stockApp.tasks.rates_update": {"queue": "stock_rates"},
    "stockApp.tasks.balances_apply": {"queue": "balance_updates"},
    "stockApp.tasks.offers_expire": {"queue": "expire_offers"},
}

# --------- Harmonogram (Celery Beat) ---------
# Częstotliwości pobieramy z ENV (sekundy); mają sensowne defaulty pod eksperymenty.
def _env_seconds(key: str, default: float) -> schedule:
    try:
        return schedule(float(os.getenv(key, default)))
    except Exception:
        return schedule(default)

app.conf.beat_schedule = {
    # 1) Orkiestracja dopasowań (kolejkuje match_execute)
    "match-scheduler": {
        "task": "stockApp.tasks.match_scheduler",
        "schedule": _env_seconds("SCHED_MATCH_S", 5.0),
        "options": {"queue": "transactions"},
        # kwargs bez parent_request_id (None) — to zadanie jest „systemowe”
    },

    # 2) Aktualizacje kursów
    "rates-update": {
        "task": "stockApp.tasks.rates_update",
        "schedule": _env_seconds("SCHED_RATES_S", 10.0),
        "options": {"queue": "stock_rates"},
    },

    # 3) Aplikacja zmian sald (księga zdarzeń)
    "balances-apply": {
        "task": "stockApp.tasks.balances_apply",
        "schedule": _env_seconds("SCHED_BALANCES_S", 7.5),
        "options": {"queue": "balance_updates"},
    },

    # 4) Wygaszanie przeterminowanych ofert
    "offers-expire": {
        "task": "stockApp.tasks.offers_expire",
        "schedule": _env_seconds("SCHED_EXPIRE_S", 60.0),
        "options": {"queue": "expire_offers"},
    },
}

# Strefa czasu (jeśli chcesz trzymać się UTC w logach – zostaw domyślne)
app.conf.timezone = os.getenv("CELERY_TIMEZONE", "UTC")
app.conf.enable_utc = True