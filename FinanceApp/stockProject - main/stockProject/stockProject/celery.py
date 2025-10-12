from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# ustawienie domyślnego modułu ustawień Django dla Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stockProject.settings')

app = Celery('stockProject')

# Konfiguracja Celery, używając ustawień Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Automatyczne odkrywanie zadań (tasks.py w aplikacjach Django)
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

app.conf.beat_schedule = {
    'schedule_transactions': {
        'task': 'stockApp.tasks.scheduleTransactions',
        'schedule': float(os.getenv("TRANSACTION_TIME")),
        'options': {'queue': 'transactions'}, 
    },
    'update_balance':{
        'task': 'stockApp.tasks.processBalanceUpdates',
        'schedule': 5.0,
        'options': {'queue': 'balance_updates'},
    },
    'update_stock_rates': {
        'task': 'stockApp.tasks.updateStockRates',
        'schedule': float(os.getenv("TRANSACTION_TIME")) / 2,  
        'options': {'queue': 'stock_rates'},
    },
    'expire-offers-every-minute': {
        'task': 'stockApp.tasks.expireOffers',
        'schedule': 60.0,
        'options': {'queue': 'expire_offers'},
    },
}
