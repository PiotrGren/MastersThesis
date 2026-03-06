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


NEWS_TEMPLATES = [
    ("Quarterly Report Exceeds Expectations", "POSITIVE"),
    ("New Product Launch Announced", "POSITIVE"),
    ("CEO Steps Down Amid Controversy", "NEGATIVE"),
    ("Supply Chain Disruptions Expected", "NEGATIVE"),
    ("Company Exploring Merger Options", "NEUTRAL"),
    ("Routine Maintenance on Main Facilities", "NEUTRAL"),
]


class Command(BaseCommand):
    help = "Bootstrap market with initial companies, stock rates, and market news"

    def handle(self, *args, **options):
        created = 0

        for name in COMPANY_NAMES:
            company, is_created = Company.objects.get_or_create(name=name)

            if is_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Created company: {name}"))
            else:
                self.stdout.write(f"Company already exists: {name}")

            # Tworzenie początkowego kursu akcji
            has_actual = StockRate.objects.filter(company=company, actual=True).exists()
            if not has_actual:
                rate = round(random.uniform(20.0, 400.0), 2)
                StockRate.objects.create(
                    company=company,
                    rate=rate,
                    actual=True,
                    dateInc=timezone.now(),
                )

            # Tworzenie początkowych newsów (jeśli nie istnieją)
            if not MarketNews.objects.filter(company=company).exists():
                num_news = random.randint(1, 3)
                for _ in range(num_news):
                    title, sentiment = random.choice(NEWS_TEMPLATES)
                    MarketNews.objects.create(
                        company=company,
                        title=f"{name}: {title}",
                        content="This is an automatically generated news placeholder for the simulation.",
                        sentiment=sentiment
                    )
                self.stdout.write(self.style.SUCCESS(f"Created {num_news} news for {name}"))

        self.stdout.write(self.style.SUCCESS(f"Market bootstrap complete. Created {created} new companies."))

"""
class Command(BaseCommand):
    help = "Bootstrap market with initial companies, stock rates, and market news"

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
        ))"""