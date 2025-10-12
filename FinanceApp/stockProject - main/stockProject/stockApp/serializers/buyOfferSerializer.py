import datetime
import random
from rest_framework import serializers
from stockApp.models import BuyOffer, StockRate, BalanceUpdate

class BuyOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = BuyOffer
        fields = ['company', 'startAmount', 'amount']
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user
        amount = validated_data['amount']
        company = validated_data['company']
        try:
            latestStockRate = StockRate.objects.filter(company=company, actual=True).latest('dateInc')
            currentRate = latestStockRate.rate
        except StockRate.DoesNotExist:
            print("add offer stock error")
            raise serializers.ValidationError("No stock rate available for the selected company.")
        minPrice = 0.95 * currentRate
        maxPrice = 1.1 * currentRate
        calculatedPrice = round(random.uniform(minPrice, maxPrice), 2)
        totalCost = calculatedPrice * amount
        if user.moneyAfterTransations < totalCost:
            print('buy offer money error')
            raise serializers.ValidationError("You do not have enough money to cover this transaction.")
        BalanceUpdate.objects.create(
            user = user,
            changeAmount = -totalCost,
            changeType = 'moneyAfterTransactions',
        )
        dateLimit = datetime.datetime.now() + datetime.timedelta(minutes=3)
        buyOffer = BuyOffer.objects.create(
            user=request.user,
            actual=True,
            maxPrice= calculatedPrice,
            dateLimit = dateLimit,
            **validated_data
        )
        return buyOffer