from rest_framework import serializers
from stockApp.models import StockRate

class StockRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockRate
        fields = '__all__'
