from django.core.management.base import BaseCommand
from django.utils import timezone
import random

from stockApp.models import Company, StockRate


COMPANY_NAMES = [
    "AlphaTech",
    "BetaSoft",
    "GammaIndustries",
    "DeltaSystems",
    "EpsilonEnergy",
    "ZetaLogistics",
    "EtaFinance",
    "ThetaHealth",
    "IotaMotors",
    "KappaRetail",
    "LambdaAI",
    "MuNetworks",
    "NuCloud",
    "XiAnalytics",
    "OmicronLabs",
    "PiRobotics",
    "RhoSecurity",
    "SigmaTrading",
    "TauBiotech",
    "UpsilonMedia",
]


class Command(BaseCommand):
    help = "Bootstrap market with initial companies and stock rates"

    def handle(self, *args, **options):
        created = 0

        for name in COMPANY_NAMES:
            company, is_created = Company.objects.get_or_create(name=name)

            if is_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Created company: {name}"))
            else:
                self.stdout.write(f"Company already exists: {name}")

            # ensure exactly one actual StockRate
            has_actual = StockRate.objects.filter(company=company, actual=True).exists()

            if not has_actual:
                rate = round(random.uniform(20.0, 400.0), 2)
                StockRate.objects.create(
                    company=company,
                    rate=rate,
                    actual=True,
                    dateInc=timezone.now(),
                )
                self.stdout.write(f"  -> created initial rate: {rate}")

        self.stdout.write(self.style.SUCCESS(
            f"\nBootstrap finished. Companies ensured: {len(COMPANY_NAMES)}, newly created: {created}"
        ))