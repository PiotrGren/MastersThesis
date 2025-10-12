from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from stockApp.models import Company, Stock, StockRate
from rest_framework import status
import random
from datetime import datetime
import uuid
from stockApp.serializers import CompanySerializer, StockRateSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def companies(request):
    companies = Company.objects.all()
    serializer = CompanySerializer(companies, many=True)
    data = serializer.data
    responseData = list(data)
    responseData.append({'requestId': str(uuid.uuid4())})
    return Response(responseData, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def getCompaniesStockRates(request):
    numberOfRates = request.data['numberOfRates']
    companies = Company.objects.all()
    stockRates = []
    for company in companies:
        companyStockRates = StockRate.objects.filter(company=company).order_by('-dateInc')[:numberOfRates]
        stockRates.extend(companyStockRates)
    serializer = StockRateSerializer(stockRates, many=True)
    data = serializer.data
    responseData = list(data)
    responseData.append({'requestId': str(uuid.uuid4())})
    return Response(responseData, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def createCompany(request):
    serializer = CompanySerializer(data=request.data)
    if serializer.is_valid():
        name = serializer.validated_data.get('name')
        if Company.objects.filter(name=name).exists():
            return Response({'error': 'Company with this name already exists.'}, status=status.HTTP_400_BAD_REQUEST)
        company = serializer.save()
        stockRateData = {
            'actual': True,
            'rate': random.uniform(5.0, 100.0),
            'dateInc': datetime.now(),
            'company': company.pk  # lub company.pk
        }
        stockRateSerializer = StockRateSerializer(data=stockRateData)
        if stockRateSerializer.is_valid():
            stockRateSerializer.save()
            Stock.objects.create(amount=10000, user = request.user, company=company)
            requestId = str(uuid.uuid4())
            return Response({'message': 'Company created successfully.', 'requestId':requestId}, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
