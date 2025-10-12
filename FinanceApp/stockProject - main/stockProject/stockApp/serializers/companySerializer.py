from rest_framework import serializers
from stockApp.models import Company

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = '__all__'

        def create(self, validated_data):
            company = Company(
                name = validated_data['name'],
                )
            return company