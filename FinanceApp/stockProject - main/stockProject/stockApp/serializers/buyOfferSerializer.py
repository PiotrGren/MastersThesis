import random
from django.utils import timezone
from rest_framework import serializers
from ..models import BuyOffer, StockRate, BalanceUpdate
from .helpers import _get_request_id, _get_session_id

class BuyOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = BuyOffer
        fields = ['id', 'company', 'startAmount', 'amount', 'maxPrice', 'dateLimit', 'status']  # na zewnątrz trzymamy minimalny interfejs
        read_only_fields = ['id', 'maxPrice', 'dateLimit', 'status']

    def validate(self, attrs):
        if attrs.get('amount', 0) <= 0:
            raise serializers.ValidationError("Amount must be > 0.")
        if attrs.get('startAmount', 0) <= 0:
            raise serializers.ValidationError("startAmount must be > 0.")
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user
        amount = validated_data['amount']
        company = validated_data['company']

        # najnowszy "actual" kurs
        try:
            latest = StockRate.objects.filter(company=company, actual=True).latest('dateInc')
            current_rate = latest.rate
        except StockRate.DoesNotExist:
            raise serializers.ValidationError("No stock rate available for the selected company.")

        # widełki ceny (buy): 0.95 .. 1.10 * last
        min_price = 0.95 * current_rate
        max_price = 1.10 * current_rate
        calculated_price = round(random.uniform(min_price, max_price), 2)

        total_cost = calculated_price * amount
        # pole zgodne z MODELEM: moneyAfterTransactions
        if user.moneyAfterTransactions < total_cost:
            raise serializers.ValidationError("Insufficient funds to cover this transaction.")

        # rezerwacja środków (księga zdarzeń)
        BalanceUpdate.objects.create(
            user=user,
            changeAmount=-total_cost,
            changeType='moneyAfterTransactions',
            request_id=_get_request_id(request),
            session_id=_get_session_id(request),
        )

        date_limit = timezone.now() + timezone.timedelta(minutes=3)

        buy = BuyOffer.objects.create(
            user=user,
            company=company,
            startAmount=validated_data['startAmount'],
            amount=amount,
            maxPrice=calculated_price,
            dateLimit=date_limit,
            actual=True,                   # dla kompatybilności
            status='active',               # nowa semantyka
            request_id=_get_request_id(request),
            session_id=_get_session_id(request),
        )
        return buy