from rest_framework import serializers
from stockApp.models import CustomUser
import random

class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('username', 'password', 'name', 'surname', 'email')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        start_money = float(random.randint(2000, 10000))
        user = CustomUser(
            username=validated_data['username'],
            name=validated_data['name'],
            surname=validated_data['surname'],
            money=start_money,
            moneyAfterTransactions=start_money,
            role='ROLE_USER',
            email=validated_data['email'],
        )
        user.set_password(validated_data['password'])
        user.save()
        return user