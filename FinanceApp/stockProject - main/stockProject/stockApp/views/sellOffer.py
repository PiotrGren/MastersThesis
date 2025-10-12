from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from stockApp.serializers import SellOfferSerializer
from stockApp.models import SellOffer, Stock
import uuid

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def addSellOffer(request):
    serializer = SellOfferSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        data = serializer.data
        responseData = dict(data)
        responseData['requestId'] = str(uuid.uuid4())
        return Response(responseData, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sellOffers(request):
    sellOffers = SellOffer.objects.filter(user=request.user, actual = True)
    serializer = SellOfferSerializer(sellOffers, many=True)
    data = serializer.data
    responseData = list(data)
    responseData.append({'requestId': str(uuid.uuid4())})
    return Response(responseData, status=status.HTTP_200_OK)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deleteSellOffer(request, pk):
    try:
        sellOffer = SellOffer.objects.get(pk=pk, user=request.user)
    except SellOffer.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    try:
        stock = Stock.objects.get(user=request.user, company=sellOffer.company)
        stock.amount += sellOffer.amount
        stock.save()
    except Stock.DoesNotExist:
        Stock.objects.create(user=request.user, company=sellOffer.company, amount=sellOffer.amount)
    sellOffer.actual = False
    sellOffer.save()
    return Response({'requestId': str(uuid.uuid4())},status=status.HTTP_204_NO_CONTENT)