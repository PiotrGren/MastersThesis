from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from stockApp.models import Stock, CustomUser, Company
from stockApp.models import UserWatchlist
from stockApp.serializers import UserWatchlistSerializer
from stockApp.serializers import UserUpdateSerializer, StockSerializer, CustomUserInfoSerializer
from stockApp.views.mixins import RequestContextMixin

import random 
import uuid


class FundsView(RequestContextMixin, APIView):
    """
    PUT /api/user/funds
    Aktualizuje dane użytkownika (np. dodanie środków).
    Wcześniej: addMoney()
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, *args, **kwargs):
        user = request.user
        serializer = UserUpdateSerializer(user, data=request.data, partial=True, context=self.get_serializer_context())

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserStocksView(RequestContextMixin, APIView):
    """
    GET /api/user/stocks
    Zwraca wszystkie akcje użytkownika z amount > 0.
    Wcześniej: getUserStocks()
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        stocks = Stock.objects.filter(user=request.user, amount__gt=0)
        serializer = StockSerializer(stocks, many=True, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserInfoView(RequestContextMixin, APIView):
    """
    GET /api/user/info
    Zwraca dane aktualnie zalogowanego użytkownika.
    Wcześniej: getUserInfo()
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        serializer = CustomUserInfoSerializer(request.user, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)


class UsersMoneyCheckView(RequestContextMixin, APIView):
    """
    GET /api/users/money-check
    Dla celów testowych (publiczne API) — średnia ilość środków wszystkich użytkowników.
    Wcześniej: getUsersMoneyCheck()
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        admin_users = CustomUser.objects.filter(is_superuser=True)
        users = CustomUser.objects.exclude(id__in=admin_users.values_list('id', flat=True)).all()

        if not users.exists():
            return Response({"detail": "No non-admin users found."}, status=status.HTTP_404_NOT_FOUND)

        total_money = sum(u.money for u in users)
        total_after = sum(u.moneyAfterTransactions for u in users)
        count = users.count()

        avg_money = round(total_money / count, 2)
        avg_after = round(total_after / count, 2)

        return Response({"money": avg_money, "moneyAT": avg_after}, status=status.HTTP_200_OK)
    

class DebugAirdropView(RequestContextMixin, APIView):
    """
    POST /api/debug/airdrop
    DEBUG ONLY: Rozdaje użytkownikowi losowe akcje na start (IPO),
    żeby miał co sprzedawać w symulacji.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        
        # Zabezpieczenie: Jeśli użytkownik już coś ma, nie dajemy więcej
        if Stock.objects.filter(user=user, amount__gt=0).exists():
            return Response(
                {'message': 'User already has stocks', 'requestId': str(uuid.uuid4())}, 
                status=status.HTTP_200_OK
            )

        # Pobierz wszystkie firmy
        companies = list(Company.objects.all())
        if not companies:
            return Response(
                {'error': 'No companies in market'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Wylosuj ile firm posiada user (np. od 0 do 3)
        # 0 oznacza, że user startuje tylko z gotówką (ważny przypadek dla ML)
        number_of_companies = random.choices([0, 1, 2, 3], weights=[10, 40, 30, 20], k=1)[0]
        
        created_stocks_info = []

        if number_of_companies > 0:
            assigned_companies = random.sample(companies, k=min(number_of_companies, len(companies)))
            
            for company in assigned_companies:
                # Losowa ilość akcji (Integery, np. 100 - 5000)
                amount = random.randint(100, 5000)
                
                Stock.objects.create(
                    user=user,
                    company=company,
                    amount=amount
                )
                created_stocks_info.append(f"{company.name}: {amount}")

        return Response({
            'message': 'Airdrop successful', 
            'stocks_assigned': created_stocks_info,
            'requestId': str(uuid.uuid4())
        }, status=status.HTTP_201_CREATED)


class UserWatchlistView(RequestContextMixin, APIView):
    """
    POST /api/user/watchlist/
    Dodaje spółkę do obserwowanych.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = UserWatchlistSerializer(data=request.data, context=self.get_serializer_context())
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PortfolioAnalysisView(RequestContextMixin, APIView):
    """
    GET /api/user/portfolio-analysis/
    Zwraca sztuczną poradę analityczną dla CarefulTradera.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response({
            "advice": random.choice(["Buy tech stocks", "Sell holding", "Wait for market correction"]),
            "risk_level": "medium",
            "cash_to_stock_ratio": round(random.uniform(0.1, 0.9), 2)
        }, status=status.HTTP_200_OK)


class TradeHistoryView(RequestContextMixin, APIView):
    """
    GET /api/user/trade-history/
    Sztuczna historia transakcji do wywoływania po zakupie.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response({
            "recent_trades": [
                {"type": "BUY", "amount": 10, "status": "COMPLETED"},
                {"type": "SELL", "amount": 5, "status": "COMPLETED"}
            ]
        }, status=status.HTTP_200_OK)


class UserSettingsView(RequestContextMixin, APIView):
    """
    POST /api/user/settings/
    Mock dla zapisywania opcji profilu (wprowadza szum).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        return Response({"message": "Settings updated successfully."}, status=status.HTTP_200_OK)

"""
OLD

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from stockApp.serializers import UserUpdateSerializer, StockSerializer, CustomUserInfoSerializer
from stockApp.models import Stock, CustomUser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
import uuid

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def addMoney(request):
    user = request.user
    serializer = UserUpdateSerializer(user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        data = serializer.data
        responseData = dict(data)
        responseData['requestId'] = str(uuid.uuid4())
        return Response(responseData, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def getUserStocks(request):
    stocks= Stock.objects.filter(user=request.user, amount__gt = 0)
    serializer = StockSerializer(stocks, many=True)
    data = serializer.data
    responseData = list(data)
    responseData.append({'requestId': str(uuid.uuid4())})
    return Response(responseData, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def getUserInfo(request):
    user = request.user
    serializer = CustomUserInfoSerializer(user)
    data = serializer.data
    responseData = dict(data)
    responseData['requestId'] = str(uuid.uuid4())
    return Response(responseData, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([AllowAny])
def getUsersMoneyCheck(request):
    admin_users = CustomUser.objects.filter(is_superuser=True)
    users = CustomUser.objects.exclude(id__in=admin_users.values_list('id', flat=True)).all()
    money = 0 
    moneyat = 0
    for user in users:
        money += user.money
        moneyat += user.moneyAfterTransations
    money = money / users.count()
    moneyat = moneyat / users.count()
    return Response({"money":money,"moneyAT": moneyat,'requestId': str(uuid.uuid4())}, status = status.HTTP_200_OK)
"""