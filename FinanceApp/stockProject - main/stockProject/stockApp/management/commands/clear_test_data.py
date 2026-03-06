from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.conf import settings

from stockApp.models import (
    Company, Stock, BalanceUpdate, BuyOffer, SellOffer,
    CustomUser, Transaction, StockRate, Cpu, MarketLog,
    TradeLog, TrafficLog
)

class Command(BaseCommand):
    help = (
        "Czyści dane środowiska dev/test. "
        "Domyślnie NIE usuwa logów na innych aliasach DB. "
        "Użyj --include-logs aby wyczyścić też tabele logowe, "
        "a --db-alias=<alias> aby wskazać alias (np. test)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Wymaga do wykonania; zapobiega przypadkowemu uruchomieniu."
        )
        parser.add_argument(
            "--include-logs",
            action="store_true",
            help="Czyści również tabele logowe na wskazanym aliasie."
        )
        parser.add_argument(
            "--db-alias",
            default=None,
            help="Alias bazy dla logów (np. 'test')."
        )

    def handle(self, *args, **options):
        if not options["force"]:
            raise CommandError("Użyj flagi --force, aby potwierdzić czyszczenie.")

        # Twarde zabezpieczenie środowiska — czyść tylko w DEV/TEST
        if not settings.DEBUG:
            raise CommandError("Wyłączone na produkcji (settings.DEBUG=False).")

        db_alias = options.get("db_alias")
        include_logs = options.get("include_logs", False)

        self.stdout.write(self.style.WARNING("Rozpoczynam czyszczenie danych (dev/test)..."))

        with transaction.atomic():
            admin_ids = list(CustomUser.objects.filter(is_superuser=True).values_list("id", flat=True))

            BuyOffer.objects.all().delete()
            SellOffer.objects.all().delete()
            Stock.objects.all().delete()
            Company.objects.all().delete()
            BalanceUpdate.objects.all().delete()
            Transaction.objects.all().delete()
            StockRate.objects.all().delete()

            CustomUser.objects.exclude(id__in=admin_ids).delete()

            self.stdout.write(self.style.SUCCESS("Wyczyszczono: oferty, spółki, stany, bilanse, transakcje, kursy, userów (bez adminów)."))

            if include_logs:
                if not db_alias:
                    raise CommandError("Podaj --db-alias=<alias> (np. --db-alias=test) razem z --include-logs.")
                Cpu.objects.using(db_alias).all().delete()
                MarketLog.objects.using(db_alias).all().delete()
                TradeLog.objects.using(db_alias).all().delete()
                TrafficLog.objects.using(db_alias).all().delete()
                self.stdout.write(self.style.SUCCESS(f"Wyczyszczono logi na aliasie '{db_alias}'."))

        self.stdout.write(self.style.SUCCESS("Zakończone."))
