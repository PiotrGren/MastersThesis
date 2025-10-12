from rest_framework import serializers
from stockApp.models import CustomUser

class CustomUserInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('username', 'password', 'name', 'surname','email','money', 'moneyAfterTransations', 'role')
        extra_kwargs = {'password': {'write_only': True}}