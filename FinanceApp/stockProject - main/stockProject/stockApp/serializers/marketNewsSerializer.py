from rest_framework import serializers
from stockApp.models import MarketNews

class MarketNewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketNews
        fields = ['id', 'company', 'title', 'content', 'sentiment', 'created_at']
        read_only_fields = ['id', 'created_at']