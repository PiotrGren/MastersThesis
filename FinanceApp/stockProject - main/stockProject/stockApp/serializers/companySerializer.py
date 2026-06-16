from rest_framework import serializers
from stockApp.models import Company
from django.utils.text import slugify

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'slug']

    def create(self, validated_data):
        name = validated_data['name']
        slug = validated_data.get('slug') or slugify(name)
        company = Company.objects.create(name=name, slug=slug)
        return company