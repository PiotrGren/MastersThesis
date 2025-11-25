from __future__ import annotations

import os
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from celery import shared_task
from django.db import transaction
from django.utils.timezone import now

from stockApp.models import (
    Company,
    Stock,
    StockRate,
    BuyOffer,
    SellOffer,
    BalanceUpdate,
    Transaction,
    TradeLog,
    ErrorLog,
)

# ========= Konfiguracja logów / kontekstu środowiska =========

LOG_DIR = Path(os.getenv("LOG_DIR", "/logs")).resolve()
TRADE_JSONL = LOG_DIR / os.getenv("TRADE_LOG_JSONL", "trade_log.jsonl")
ERROR_JSONL = LOG_DIR / os.getenv("ERROR_LOG_JSONL", "error_log.jsonl")

ENV = os.getenv("ENV", "dev")
SERVICE_NAME = os.getenv("SERVICE_NAME", "celery")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.1.0")
CONTAINER_ID = os.getenv("HOSTNAME", None)

EXPERIMENT_ID = os.getenv("EXPERIMENT_ID", None)
PHASE = os.getenv("PHASE", None)
SCENARIO = os.getenv("SCENARIO", None)


def _utc() -> str:
    return now().isoformat()


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        # nie blokuj taska gdy fs niedostępny
        pass


def _trade_jsonl(
    *,
    trade_id: str,
    parent_request_id: Optional[str],
    kind: str,
    cycle_time_ms: float,
    db_time_ms: Optional[float],
    queue_time_ms: Optional[float],
    matched_pairs: int = 0,
    partial_fills: int = 0,
    rejected_offers: int = 0,
    reason_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    row = {
        "trade_id": trade_id,
        "timestamp": _utc(),
        "kind": kind,  # np. MATCH_EXECUTE / RATES_UPDATE / BALANCES_APPLY / OFFERS_EXPIRE
        "parent_request_id": parent_request_id,
        "cycle_time_ms": round(cycle_time_ms, 2),
        "db_time_ms": round(db_time_ms, 2) if db_time_ms is not None else None,
        "queue_time_ms": round(queue_time_ms, 2) if queue_time_ms is not None else None,
        "matched_pairs": matched_pairs,
        "partial_fills": partial_fills,
        "rejected_offers": rejected_offers,
        "reason_code": reason_code,
        "service_name": SERVICE_NAME,
        "container_id": CONTAINER_ID,
        "env": ENV,
        "service_version": SERVICE_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "phase": PHASE,
        "scenario": SCENARIO,
        "details": details or {},
    }
    _append_jsonl(TRADE_JSONL, row)


def _error_jsonl(
    *,
    level: str,
    component: str,
    message: str,
    error_code: Optional[str] = None,
    request_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    row = {
        "error_id": str(uuid.uuid4()),
        "timestamp": _utc(),
        "level": level,
        "component": component,
        "request_id": request_id,
        "error_code": error_code,
        "message": message,
        "env": ENV,
        "service_version": SERVICE_VERSION,
        "container_id": CONTAINER_ID,
        "context": context or {},
    }
    _append_jsonl(ERROR_JSONL, row)


def _safe_update_single_actual_stockrate(company: Company, rate_value: float) -> StockRate:
    """
    Utrzymuje dokładnie jeden aktualny kurs (actual=True) na firmę.
    """
    # wygaszamy poprzednie
    StockRate.objects.filter(company=company, actual=True).update(actual=False)
    # dodajemy nowy
    sr = StockRate.objects.create(
        company=company,
        rate=float(rate_value),
        actual=True,
        dateInc=now(),
    )
    return sr


# ========= A) Scheduler dopasowań =========

@shared_task(bind=True, acks_late=True, time_limit=60, soft_time_limit=45)
def match_scheduler(self, *, parent_request_id: Optional[str] = None) -> str:
    """
    Układa paczki spółek i kolejkuje dopasowania (match_execute).
    parent_request_id: jeśli wywołane z widoku (API) – korelacja HTTP→Celery.
    """
    t0 = time.perf_counter()
    db_ms = 0.0

    try:
        t_db = time.perf_counter()
        company_ids = list(Company.objects.values_list("id", flat=True))
        db_ms += (time.perf_counter() - t_db) * 1000.0

        # Prosty batching po 10 spółek (wystarczy do eksperymentów)
        batch_size = int(os.getenv("MATCH_BATCH_SIZE", "10"))
        batches: List[List[int]] = [
            company_ids[i : i + batch_size] for i in range(0, len(company_ids), batch_size)
        ]

        for batch in batches:
            match_execute.delay(company_ids=batch, parent_request_id=parent_request_id)

        cycle_ms = (time.perf_counter() - t0) * 1000.0

        # JSONL (tylko meta)
        _trade_jsonl(
            trade_id=str(uuid.uuid4()),
            parent_request_id=parent_request_id,
            kind="MATCH_SCHEDULER",
            cycle_time_ms=cycle_ms,
            db_time_ms=db_ms,
            queue_time_ms=None,
            details={"batches": len(batches), "total_companies": len(company_ids)},
        )

        # wpis do DB (syntetyczny)
        TradeLog.objects.create(
            timestamp=now(),
            applicationTime=round(cycle_ms, 2),
            databaseTime=round(db_ms, 2),
            numberOfSellOffers=0,
            numberOfBuyOffers=0,
            companyIds=[int(x) for x in company_ids],
            parent_request_id=parent_request_id,
            details={"batches": len(batches)},
        )
        return "scheduled"

    except Exception as exc:
        msg = f"match_scheduler failed: {exc}"
        ErrorLog.objects.create(
            error_id=str(uuid.uuid4()),
            timestamp=now(),
            level="ERROR",
            component="celery",
            request_id=parent_request_id,
            parent_request_id=parent_request_id,
            error_code="EXCEPTION",
            message=msg,
            stack=None,
            context={"task": "match_scheduler"},
            env=ENV,
            service_version=SERVICE_VERSION,
            container_id=CONTAINER_ID,
        )
        _error_jsonl(level="ERROR", component="celery", message=msg, error_code="EXCEPTION",
                     request_id=parent_request_id, context={"task": "match_scheduler"})
        raise


# ========= B) Dopasowanie zleceń =========

@shared_task(bind=True, acks_late=True, time_limit=180, soft_time_limit=150)
def match_execute(
    self,
    *,
    company_ids: Iterable[int],
    parent_request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Dla paczki firm kojarzy oferty kupna/sprzedaży.
    Zbiera metryki: cycle_time_ms, db_time_ms, wyniki biznesowe, zapisuje TradeLog + JSONL.
    """
    t0 = time.perf_counter()
    db_ms = 0.0
    matched_pairs = 0
    partial_fills = 0
    rejected_offers = 0

    trade_id = str(uuid.uuid4())
    details: Dict[str, Any] = {"companies": list(company_ids)}

    try:
        # przykład banalnej logiki: dla każdej firmy paruj najtańszą sprzedaż z najdroższym kupnem
        for cid in company_ids:
            # Pobrania z DB
            t_db = time.perf_counter()
            company = Company.objects.get(pk=cid)
            sell_qs = SellOffer.objects.select_for_update().filter(company=company, actual=True).order_by("minPrice")
            buy_qs = BuyOffer.objects.select_for_update().filter(company=company, actual=True).order_by("-maxPrice")
            db_ms += (time.perf_counter() - t_db) * 1000.0

            with transaction.atomic():
                while sell_qs.exists() and buy_qs.exists():
                    t_db = time.perf_counter()
                    sell = sell_qs.first()
                    buy = buy_qs.first()
                    db_ms += (time.perf_counter() - t_db) * 1000.0
                    if sell is None or buy is None:
                        break

                    # warunek ceny
                    if buy.maxPrice < sell.minPrice:
                        # brak dopasowania cenowego
                        rejected_offers += 1
                        break

                    # wyznacz wolumen transakcji
                    amount = min(sell.amount, buy.amount)

                    # utwórz transakcję
                    t_db = time.perf_counter()
                    Transaction.objects.create(
                        buyOffer=buy, sellOffer=sell, amount=amount, price=sell.minPrice, totalPrice=sell.minPrice * amount
                    )
                    db_ms += (time.perf_counter() - t_db) * 1000.0

                    matched_pairs += 1
                    if amount < sell.amount or amount < buy.amount:
                        partial_fills += 1

                    # aktualizuj rezerwy i stany
                    t_db = time.perf_counter()
                    # kupujący: ściągamy z zarezerwowanej puli (moneyAfterTransactions — rezerwa była blokowana wcześniej)
                    buy.amount -= amount
                    if buy.amount == 0:
                        buy.actual = False
                    buy.save()

                    # sprzedający: odejmujemy akcje z wystawionej oferty
                    sell.amount -= amount
                    if sell.amount == 0:
                        sell.actual = False
                    sell.save()
                    db_ms += (time.perf_counter() - t_db) * 1000.0

                    # odśwież qs-y w pętli
                    t_db = time.perf_counter()
                    sell_qs = SellOffer.objects.select_for_update().filter(company=company, actual=True).order_by("minPrice")
                    buy_qs = BuyOffer.objects.select_for_update().filter(company=company, actual=True).order_by("-maxPrice")
                    db_ms += (time.perf_counter() - t_db) * 1000.0

        # podsumowanie
        details.update(
            {
                "matched_pairs": matched_pairs,
                "partial_fills": partial_fills,
                "rejected_offers": rejected_offers,
            }
        )

        cycle_ms = (time.perf_counter() - t0) * 1000.0

        # JSONL + DB
        _trade_jsonl(
            trade_id=trade_id,
            parent_request_id=parent_request_id,
            kind="MATCH_EXECUTE",
            cycle_time_ms=cycle_ms,
            db_time_ms=db_ms,
            queue_time_ms=None,  # możesz dodać obliczanie z self.request jeśli chcesz
            matched_pairs=matched_pairs,
            partial_fills=partial_fills,
            rejected_offers=rejected_offers,
            reason_code=None if rejected_offers == 0 else "NO_LIQUIDITY",
            details=details,
        )

        TradeLog.objects.create(
            timestamp=now(),
            applicationTime=round(cycle_ms, 2),
            databaseTime=round(db_ms, 2),
            numberOfSellOffers=0,  # nieużywane dalej – zostają dla zgodności starego modelu
            numberOfBuyOffers=0,
            companyIds=list(company_ids),
            parent_request_id=parent_request_id,
            matched_pairs=matched_pairs,
            partial_fills=partial_fills,
            rejected_offers=rejected_offers,
            reason_code=None if rejected_offers == 0 else "NO_LIQUIDITY",
            details=details,
        )

        return {
            "trade_id": trade_id,
            "cycle_time_ms": cycle_ms,
            "db_time_ms": db_ms,
            "matched_pairs": matched_pairs,
            "partial_fills": partial_fills,
            "rejected_offers": rejected_offers,
        }

    except Exception as exc:
        msg = f"match_execute failed: {exc}"
        ErrorLog.objects.create(
            error_id=str(uuid.uuid4()),
            timestamp=now(),
            level="ERROR",
            component="celery",
            request_id=parent_request_id,
            parent_request_id=parent_request_id,
            error_code="EXCEPTION",
            message=msg,
            stack=None,
            context={"task": "match_execute", "companies": list(company_ids)},
            env=ENV,
            service_version=SERVICE_VERSION,
            container_id=CONTAINER_ID,
        )
        _error_jsonl(level="ERROR", component="celery", message=msg, error_code="EXCEPTION",
                     request_id=parent_request_id, context={"task": "match_execute"})
        raise


# ========= C) Aktualizacja kursów =========

@shared_task(bind=True, acks_late=True, time_limit=120, soft_time_limit=90)
def rates_update(self, *, parent_request_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Aktualizuje kursy (StockRate) – utrzymuje dokładnie jeden actual=True na firmę.
    """
    t0 = time.perf_counter()
    db_ms = 0.0
    trade_id = str(uuid.uuid4())

    try:
        # prościutki trend: +- losowa szpilka wokół poprzedniego (dla demo)
        import random

        t_db = time.perf_counter()
        companies = list(Company.objects.all())
        db_ms += (time.perf_counter() - t_db) * 1000.0

        changed: List[Tuple[int, float]] = []
        for c in companies:
            t_db = time.perf_counter()
            last = StockRate.objects.filter(company=c, actual=True).order_by("-dateInc").first()
            db_ms += (time.perf_counter() - t_db) * 1000.0

            base = last.rate if last else random.uniform(10, 100)
            delta = random.uniform(-1.0, 1.0)
            new_rate = max(0.01, base + delta)

            t_db = time.perf_counter()
            _safe_update_single_actual_stockrate(c, new_rate)
            db_ms += (time.perf_counter() - t_db) * 1000.0

            changed.append((c.id, new_rate))

        cycle_ms = (time.perf_counter() - t0) * 1000.0

        _trade_jsonl(
            trade_id=trade_id,
            parent_request_id=parent_request_id,
            kind="RATES_UPDATE",
            cycle_time_ms=cycle_ms,
            db_time_ms=db_ms,
            queue_time_ms=None,
            details={"updated": changed[:20], "updated_total": len(changed)},
        )

        TradeLog.objects.create(
            timestamp=now(),
            applicationTime=round(cycle_ms, 2),
            databaseTime=round(db_ms, 2),
            numberOfSellOffers=0,
            numberOfBuyOffers=0,
            companyIds=[cid for cid, _ in changed],
            parent_request_id=parent_request_id,
            details={"updated_count": len(changed)},
        )

        return {"updated_count": len(changed), "cycle_time_ms": cycle_ms, "db_time_ms": db_ms}

    except Exception as exc:
        msg = f"rates_update failed: {exc}"
        ErrorLog.objects.create(
            error_id=str(uuid.uuid4()),
            timestamp=now(),
            level="ERROR",
            component="celery",
            request_id=parent_request_id,
            parent_request_id=parent_request_id,
            error_code="EXCEPTION",
            message=msg,
            stack=None,
            context={"task": "rates_update"},
            env=ENV,
            service_version=SERVICE_VERSION,
            container_id=CONTAINER_ID,
        )
        _error_jsonl(level="ERROR", component="celery", message=msg, error_code="EXCEPTION",
                     request_id=parent_request_id, context={"task": "rates_update"})
        raise


# ========= D) Zastosowanie operacji bilansowych =========

@shared_task(bind=True, acks_late=True, time_limit=120, soft_time_limit=90)
def balances_apply(self, *, parent_request_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Aplikuje oczekujące BalanceUpdate (księga zdarzeń).
    Preferuj flagę applied/applied_at; jeśli model ma tylko actual – użyj jej jako „niezastosowane”.
    """
    t0 = time.perf_counter()
    db_ms = 0.0
    trade_id = str(uuid.uuid4())

    applied = 0

    try:
        # wybierz do zastosowania
        t_db = time.perf_counter()
        qs = BalanceUpdate.objects.filter(actual=True)
        db_ms += (time.perf_counter() - t_db) * 1000.0

        for bu in qs.select_for_update():
            with transaction.atomic():
                t_db = time.perf_counter()
                user = bu.user
                if bu.changeType == "money":
                    user.money += float(bu.changeAmount)
                else:  # "moneyAfterTransactions"
                    # to jest nasza „rezerwa”
                    user.moneyAfterTransactions += float(bu.changeAmount)
                user.save()
                db_ms += (time.perf_counter() - t_db) * 1000.0

                # oznacz zastosowanie (preferowana flaga applied; wstecznie: actual=False)
                if hasattr(bu, "applied"):
                    bu.applied = True
                bu.actual = False
                setattr(bu, "applied_at", now())
                bu.save()
                applied += 1

        cycle_ms = (time.perf_counter() - t0) * 1000.0

        _trade_jsonl(
            trade_id=trade_id,
            parent_request_id=parent_request_id,
            kind="BALANCES_APPLY",
            cycle_time_ms=cycle_ms,
            db_time_ms=db_ms,
            queue_time_ms=None,
            details={"applied": applied},
        )

        TradeLog.objects.create(
            timestamp=now(),
            applicationTime=round(cycle_ms, 2),
            databaseTime=round(db_ms, 2),
            numberOfSellOffers=0,
            numberOfBuyOffers=0,
            companyIds=[],
            parent_request_id=parent_request_id,
            details={"applied": applied},
        )

        return {"applied": applied, "cycle_time_ms": cycle_ms, "db_time_ms": db_ms}

    except Exception as exc:
        msg = f"balances_apply failed: {exc}"
        ErrorLog.objects.create(
            error_id=str(uuid.uuid4()),
            timestamp=now(),
            level="ERROR",
            component="celery",
            request_id=parent_request_id,
            parent_request_id=parent_request_id,
            error_code="EXCEPTION",
            message=msg,
            stack=None,
            context={"task": "balances_apply"},
            env=ENV,
            service_version=SERVICE_VERSION,
            container_id=CONTAINER_ID,
        )
        _error_jsonl(level="ERROR", component="celery", message=msg, error_code="EXCEPTION",
                     request_id=parent_request_id, context={"task": "balances_apply"})
        raise


# ========= E) Wygaszanie ofert =========

@shared_task(bind=True, acks_late=True, time_limit=120, soft_time_limit=90)
def offers_expire(self, *, parent_request_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Oznacza przeterminowane oferty i zwraca rezerwy.
    """
    t0 = time.perf_counter()
    db_ms = 0.0
    trade_id = str(uuid.uuid4())

    expired_count = 0

    try:
        t_db = time.perf_counter()
        expired_buys = BuyOffer.objects.filter(actual=True, dateLimit__lt=now())
        expired_sells = SellOffer.objects.filter(actual=True, dateLimit__lt=now())
        db_ms += (time.perf_counter() - t_db) * 1000.0

        with transaction.atomic():
            # BUY: odblokuj rezerwę (moneyAfterTransactions)
            for bo in expired_buys.select_for_update():
                user = bo.user
                refund = float(bo.amount * bo.maxPrice)
                user.moneyAfterTransactions += refund
                user.save()
                bo.actual = False
                bo.save()
                expired_count += 1

            # SELL: zwróć akcje do stanu użytkownika
            for so in expired_sells.select_for_update():
                stock, _ = Stock.objects.get_or_create(user=so.user, company=so.company, defaults={"amount": 0})
                stock.amount += so.amount
                stock.save()
                so.actual = False
                so.save()
                expired_count += 1

        cycle_ms = (time.perf_counter() - t0) * 1000.0

        _trade_jsonl(
            trade_id=trade_id,
            parent_request_id=parent_request_id,
            kind="OFFERS_EXPIRE",
            cycle_time_ms=cycle_ms,
            db_time_ms=db_ms,
            queue_time_ms=None,
            rejected_offers=expired_count,
            reason_code="EXPIRED",
            details={"expired": expired_count},
        )

        TradeLog.objects.create(
            timestamp=now(),
            applicationTime=round(cycle_ms, 2),
            databaseTime=round(db_ms, 2),
            numberOfSellOffers=0,
            numberOfBuyOffers=0,
            companyIds=[],
            parent_request_id=parent_request_id,
            reason_code="EXPIRED",
            rejected_offers=expired_count,
            details={"expired": expired_count},
        )

        return {"expired": expired_count, "cycle_time_ms": cycle_ms, "db_time_ms": db_ms}

    except Exception as exc:
        msg = f"offers_expire failed: {exc}"
        ErrorLog.objects.create(
            error_id=str(uuid.uuid4()),
            timestamp=now(),
            level="ERROR",
            component="celery",
            request_id=parent_request_id,
            parent_request_id=parent_request_id,
            error_code="EXCEPTION",
            message=msg,
            stack=None,
            context={"task": "offers_expire"},
            env=ENV,
            service_version=SERVICE_VERSION,
            container_id=CONTAINER_ID,
        )
        _error_jsonl(level="ERROR", component="celery", message=msg, error_code="EXCEPTION",
                     request_id=parent_request_id, context={"task": "offers_expire"})
        raise