from rest_framework import serializers
from stockApp.models import CustomUser

class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['name', 'surname', 'money', 'moneyAfterTransactions', 'role']

    def update(self, instance, validated_data):
        for field in ['name', 'surname', 'role']:
            if field in validated_data:
                setattr(instance, field, validated_data[field])

        if 'money' in validated_data:
            instance.money = validated_data['money']

        if 'moneyAfterTransactions' in validated_data:
            instance.moneyAfterTransactions = validated_data['moneyAfterTransactions']

        instance.save()
        return instance