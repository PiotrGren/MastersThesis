from rest_framework import serializers
from stockApp.models import CustomUser

class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['name', 'surname', 'money', 'role']
    
    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.surname = validated_data.get('surname', instance.surname)
        instance.money += validated_data.get('money', instance.money)
        instance.moneyAfterTransations += validated_data.get('moneyAfterTransations', instance.moneyAfterTransations)
        instance.role = validated_data.get('role', instance.role)
        instance.save()
        return instance