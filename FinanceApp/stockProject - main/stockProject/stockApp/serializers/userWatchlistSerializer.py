from rest_framework import serializers
from stockApp.models import UserWatchlist

class UserWatchlistSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserWatchlist
        fields = ['id', 'user', 'company', 'added_at']
        read_only_fields = ['id', 'user', 'added_at']

    def create(self, validated_data):
        # Automatycznie pobierz użytkownika z requestu
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['user'] = request.user
        return super().create(validated_data)