from rest_framework import serializers
from stockApp.models import CustomUser

class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('username', 'password', 'name', 'surname','email')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = CustomUser(
            username=validated_data['username'],
            name=validated_data['name'],
            surname=validated_data['surname'],
            money=10000.0,
            moneyAfterTransations=10000.0,
            role='ROLE_USER',
            email=validated_data['email']
        )
        user.set_password(validated_data['password'])
        user.save()
        return user