from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from stockApp.serializers import BuyOfferSerializer
from stockApp.models import BuyOffer
import uuid

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def addBuyOffer(request):
    serializer = BuyOfferSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        data = serializer.data
        responseData = dict(data)
        responseData['requestId'] = str(uuid.uuid4())
        return Response(responseData, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def buyOffers(request):
    buyOffers = BuyOffer.objects.filter(user=request.user, actual = True)
    serializer = BuyOfferSerializer(buyOffers, many=True)
    data = serializer.data
    responseData = list(data)
    responseData.append({'requestId': str(uuid.uuid4())})
    return Response(responseData, status=status.HTTP_200_OK)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deleteBuyOffer(request,pk):
    try:
        buyOffer = BuyOffer.objects.get(pk=pk, user=request.user)
    except BuyOffer.DoesNotExist:
        return Response({'requestId': str(uuid.uuid4())},status=status.HTTP_404_NOT_FOUND)
    # Obliczenie kwoty, którą należy zwrócić do pola moneyAfterTransations
    totalCost = round(buyOffer.amount * buyOffer.maxPrice,2)

    # Aktualizacja pola moneyAfterTransations użytkownika
    user = request.user
    user.moneyAfterTransations += totalCost
    user.save()

    buyOffer.actual = False
    buyOffer.save()
    return Response({'requestId': str(uuid.uuid4())},status=status.HTTP_204_NO_CONTENT)