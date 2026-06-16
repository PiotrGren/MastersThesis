from django.utils import timezone
from rest_framework import serializers
from rest_framework import serializers
from stockApp.models import SellOffer, Stock, StockRate
import random
from .helpers import _get_request_id, _get_session_id

class SellOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellOffer
        fields = ['id', 'company', 'startAmount', 'amount', 'minPrice', 'dateLimit', 'status']
        read_only_fields = ['id', 'minPrice', 'dateLimit', 'status']

    def validate(self, attrs):
        if attrs.get('amount', 0) <= 0:
            raise serializers.ValidationError("Amount must be > 0.")
        if attrs.get('startAmount', 0) <= 0:
            raise serializers.ValidationError("startAmount must be > 0.")
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user
        company = validated_data['company']
        amount = validated_data['amount']

        try:
            latest = StockRate.objects.filter(company=company, actual=True).latest('dateInc')
            current_rate = latest.rate
        except StockRate.DoesNotExist:
            raise serializers.ValidationError("No stock rate available for the selected company.")

        try:
            stock = Stock.objects.get(user=user, company=company)
        except Stock.DoesNotExist:
            raise serializers.ValidationError("You do not own shares of this company.")

        if stock.amount < amount:
            raise serializers.ValidationError("You do not have enough shares.")

        # widełki ceny (sell): 0.90 .. 1.05 * last
        min_price = 0.90 * current_rate
        max_price = 1.05 * current_rate
        calculated_price = round(random.uniform(min_price, max_price), 2)

        date_limit = timezone.now() + timezone.timedelta(minutes=3)

        sell = SellOffer.objects.create(
            user=user,
            company=company,
            stock=stock,
            startAmount=validated_data['startAmount'],
            amount=amount,
            minPrice=calculated_price,
            dateLimit=date_limit,
            actual=True,
            status='active',
            request_id=_get_request_id(request),
            session_id=_get_session_id(request),
        )

        # blokujemy posiadane akcje pod ofertę
        stock.amount -= amount
        stock.save(update_fields=['amount'])

        return sell