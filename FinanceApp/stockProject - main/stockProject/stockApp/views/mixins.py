# Mixins pomocnicze dla CBV:
# - RequestContextMixin: wyciąga request_id/session_id z nagłówków + wstrzykuje request do serializerów.
# - LatestRateMixin: bezpiecznie pobiera najnowszy kurs (StockRate.actual=True) dla spółki.
# - OfferLifecycleMixin: ujednolica anulowanie ofert (status/actual) oraz zwroty rezerw/akcji przez BalanceUpdate.
#
# UWAGA: middleware i tak loguje RequestLog/JSONL; te mixins nie "logują", tylko dbają o spójność domeny.

from typing import Optional, Dict, Any
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from stockApp.models import StockRate, Stock, BalanceUpdate, BuyOffer, SellOffer



class RequestContextMixin:
    """
    Zapewnia:
        - self.request_id / self.session_id z nagłówków (X-Request-ID, X-Session-ID)
        - przekazanie requestu do serializerów (get_serializer_context)
    Nie generuje nowych ID - tym zajmuje się middleware
    """
    
    # --- Nazwy nagłówków, które sprawdzamy (w tym fallback do META) ---
    REQUEST_ID_HEADERS = ("HTTP_X_REQUEST_ID", "X-Request-ID")
    SESSION_ID_HEADERS = ("HTTP_X_SESSION_ID", "X-Session-ID")
    
    @property
    def request_id(self) -> Optional[str]:
        req = getattr(self, "request", None)
        if not req:
            return None
        for key in self.REQUEST_ID_HEADERS:
            val = req.META.get(key) or req.headers.get(key)
            if val:
                return str(val)
        return None
    
    @property
    def session_id(self) -> Optional[str]:
        req = getattr(self, "request", None)
        if not req:
            return None
        for key in self.SESSION_ID_HEADERS:
            val = req.META.get(key) or req.headers.get(key)
            if val:
                return str(val)
        return None
    
    def get_serializer_context(self) -> Dict[str, Any]:
        """
        Wstrzykujemy request do serializerów, żeby miały dostęp do usera i nagłówków.
        """
        base = super().get_serializer_context() if hasattr(super(), "get_serializer_context") else {}
        base['request'] = getattr(self, 'request', None)
        return base
    
    
    
class LatestRateMixin:
    """
    Helper do bezpiecznego pobrania bieżącego kursu spółki (StockRate.actual=True).
    """
    def get_latest_rate(self, company) -> float:
        """
        Zwraca rate (float) dla najnowszego rekordu StockRate z actual=True
        Wyrzuca ValidationError gdy brak kursu.
        """
        try:
            latest = StockRate.objects.filter(company=company, actual=True).latest('dateInc')
            return float(latest.rate)
        except StockRate.DoesNotExist:
            raise serializers.ValidationError(f"No stock rate available for the selected company.")
        
        

class OfferLifecycleMixin(RequestContextMixin):
    """
    Wspólne operacje na cyklu życia ofert:
        - anulowanie oferty kupna: status='cancelled', actual=False + zwrot rezerwy przez BalanceUpdate
        - anulowanie oferty sprzedaży: status='cancelled', actual=False + oddanie akcji do Stock
    Wszystko w transakcji, bez zmian sald/akcji w magiczny sposób jak wcześniej
    """
    
    def _now(self):
        return timezone.now()
    
    @transaction.atomic
    def cancel_buy_offer(self, offer: BuyOffer) -> BuyOffer:
        """
        Zwrot rezerwy: startAmount * maxPrice (lub pozostała amount * maxPrice - zależy od polityki).
        Przyjmujemy zwrot kwoty za POZOSTAŁĄ ilość (offer.amount), aby audyt był spójny z tym, co faktycznie nie zostało zrealizowane.
        """
        if offer.status != "active":
            return offer
        
        refundable_amount = max(0, int(offer.amount))
        refund_value = round(float(offer.maxPrice) * refundable_amount, 2)
        
        # Wpis księgowy - oferta wraca na moneyAfterTransactions
        if refund_value > 0:
            BalanceUpdate.objects.create(
                user=offer.user,
                changeAmount=refund_value,
                changeType='moneyAfterTransactions',
                request_id=self.request_id,
                session_id=self.session_id,
            )
            
        # Oznacz ofertę jako anulowaną
        offer.status = 'cancelled'
        offer.actual = False
        offer.updated_at = self._now() if hasattr(offer, 'updated_at') else offer.updated_at
        offer.save(update_fields=['status', 'actual'] + (['updated_at'] if hasattr(offer, 'updated_at') else []))
        return offer
    
    
    
    @transaction.atomic
    def cancel_sell_offer(self, offer: SellOffer) -> SellOffer:
        """
        Oddanie niewykorzystanych akcji do Stock użytkownika (za pozostałą ilość).
        """
        if offer.status != "active":
            return offer
        
        remaining = max(0, int(offer.amount))
        if remaining > 0:
            stock, _ = Stock.objects.get_or_create(user=offer.user, company=offer.company)
            stock.amount = int(stock.amount) + remaining
            stock.save(update_fields=['amount'])
            
        # Oznacz ofertę jako anulowaną
        offer.status = 'cancelled'
        offer.actual = False
        offer.updated_at = self._now() if hasattr(offer, 'updated_at') else offer.updated_at
        offer.save(update_fields=['status', 'actual'] + (['updated_at'] if hasattr(offer, 'updated_at') else []))
        return offer
    
    # Szybkie helpery odpowiedzi
    def ok(self, data: dict, *, status_code: int = status.HTTP_200_OK) -> Response:
        return Response(data, status=status_code)
    
    def bad(self, message:str, *, status_code: int = status.HTTP_400_BAD_REQUEST) -> Response:
        return Response({"detail": message}, status=status_code)
        