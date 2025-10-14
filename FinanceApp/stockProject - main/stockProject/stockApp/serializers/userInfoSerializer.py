from rest_framework import serializers
from stockApp.models import CustomUser

class CustomUserInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        # bez hasła w "info"; dodajemy public_id pod korelację w logach
        fields = ('public_id', 'username', 'name', 'surname', 'email',
                  'money', 'moneyAfterTransactions', 'role')