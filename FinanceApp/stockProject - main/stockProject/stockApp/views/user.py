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