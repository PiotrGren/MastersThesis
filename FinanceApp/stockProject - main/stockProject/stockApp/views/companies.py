import random
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from stockApp.models import Company, Stock, StockRate, MarketNews
from stockApp.serializers import CompanySerializer, StockRateSerializer, MarketNewsSerializer
from stockApp.views.mixins import RequestContextMixin, LatestRateMixin


class CompanyViewSet(RequestContextMixin, viewsets.ViewSet):
    """
    /api/companies [GET, POST]
    - GET  : lista spółek
    - POST : tworzy spółkę + startowy kurs (actual=True) i startowy stan akcji dla request.user
    Uwaga: brak requestId w body — X-Request-ID doda middleware.
    """
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        qs = Company.objects.all()
        data = CompanySerializer(qs, many=True, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_200_OK)

    def create(self, request):
        serializer = CompanySerializer(data=request.data, context=self.get_serializer_context())
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        name = serializer.validated_data.get("name")                            # type: ignore[reportOptionalMemberAccess]
        if Company.objects.filter(name=name).exists():
            return Response({"detail": "Company with this name already exists."}, status=status.HTTP_400_BAD_REQUEST)

        company = serializer.save()

        # --- Startowy kurs (actual=True, TZ-aware) ---
        initial_rate = round(random.uniform(5.0, 100.0), 2)
        rate_payload = {
            "actual": True,
            "rate": initial_rate,
            "dateInc": timezone.now(),
            "company": company.pk,           # type: ignore[reportOptionalMemberAccess]
        }
        rate_ser = StockRateSerializer(data=rate_payload)
        if not rate_ser.is_valid():
            # cofamy spółkę, by nie zostawiać sieroty (prosto, bez transakcji globalnej)
            company.delete()                # type: ignore[reportOptionalMemberAccess]
            return Response(rate_ser.errors, status=status.HTTP_400_BAD_REQUEST)
        rate_ser.save()

        # 3) startowy stan akcji dla właściciela (jak w starym kodzie)
       # Stock.objects.create(amount=10000, user=request.user, company=company)

        return Response({"message": "Company created successfully."}, status=status.HTTP_201_CREATED)


class CompanyRatesView(RequestContextMixin, APIView):
    """
    GET /api/companies/rates?n=<int>
    Zwraca ostatnie 'n' kursów dla każdej spółki (flat lista, jak w starym API – tylko bez requestId w body).
    - Parametr 'n' w query params; domyślnie 1.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            n = int(request.query_params.get("n", 1))
        except ValueError:
            return Response({"detail": "Parameter 'n' must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
        if n <= 0:
            return Response({"detail": "Parameter 'n' must be > 0."}, status=status.HTTP_400_BAD_REQUEST)

        companies = Company.objects.all()
        rates = []
        for company in companies:
            qs = StockRate.objects.filter(company=company).order_by("-dateInc")[:n]
            rates.extend(qs)

        data = StockRateSerializer(rates, many=True).data
        return Response(data, status=status.HTTP_200_OK)


class CompanyNewsView(RequestContextMixin, APIView):
    """
    GET /api/companies/{id}/news/
    Zwraca wiadomości dla konkretnej spółki.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None, *args, **kwargs):
        # Pobiera 5 najnowszych newsów z bazy dla danej spółki
        news = MarketNews.objects.filter(company_id=pk).order_by('-created_at')[:5]
        serializer = MarketNewsSerializer(news, many=True, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)


class MarketSentimentView(RequestContextMixin, APIView):
    """
    GET /api/market/sentiment/
    Mock globalnego wskaźnika strachu/chciwości.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response({
            "overall_trend": random.choice(["BULLISH", "BEARISH", "NEUTRAL"]),
            "fear_and_greed_index": random.randint(10, 90)
        }, status=status.HTTP_200_OK)

"""
OLD
 
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
"""