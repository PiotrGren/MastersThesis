from rest_framework import status, viewsets, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
import random

from stockApp.models import BuyOffer, SellOffer
from stockApp.serializers import BuyOfferSerializer, SellOfferSerializer
from stockApp.views.mixins import OfferLifecycleMixin, RequestContextMixin


class BuyOfferViewSet(OfferLifecycleMixin, viewsets.ViewSet):
    """
    /api/buyoffers/      [GET, POST]
    /api/buyoffers/{pk}/ [DELETE]
    - GET     : lista aktywnych zleceń kupna użytkownika
    - POST    : tworzy zlecenie kupna (walidacje & rezerwy w serializerze)
    - DELETE  : anuluje zlecenie (zwrot niewykorzystanej rezerwy pieniędzy)
    Uwaga: brak requestId w body – nagłówek X-Request-ID doda middleware.
    """
    permission_classes = [IsAuthenticated]

    # GET /api/buyoffers/
    def list(self, request):
        qs = BuyOffer.objects.filter(user=request.user, status='active')  # legacy: actual=True obsłuży tasks
        data = BuyOfferSerializer(qs, many=True, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_200_OK)

    # POST /api/buyoffers/
    def create(self, request):
        serializer = BuyOfferSerializer(data=request.data, context=self.get_serializer_context())
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        offer = serializer.save()
        return Response(BuyOfferSerializer(offer).data, status=status.HTTP_201_CREATED)
    
    # PUT /api/buyoffers/{pk}/
    def update(self, request, pk=None):
        offer = get_object_or_404(BuyOffer, pk=pk, user=request.user)
        # partial=True pozwala na częściową aktualizację (np. tylko zmiana ilości)
        serializer = BuyOfferSerializer(offer, data=request.data, partial=True, context=self.get_serializer_context())
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # DELETE /api/buyoffers/{pk}/
    def destroy(self, request, pk=None):
        offer = get_object_or_404(BuyOffer, pk=pk, user=request.user)
        self.cancel_buy_offer(offer)  # status='cancelled', actual=False, BalanceUpdate (+$ rezerwy)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SellOfferViewSet(OfferLifecycleMixin, viewsets.ViewSet):
    """
    /api/selloffers/      [GET, POST]
    /api/selloffers/{pk}/ [DELETE]
    - GET     : lista aktywnych zleceń sprzedaży użytkownika
    - POST    : tworzy zlecenie sprzedaży (walidacje & rezerwacja akcji w serializerze)
    - DELETE  : anuluje zlecenie (oddaje niewykorzystane akcje do Stock)
    Uwaga: brak requestId w body – nagłówek X-Request-ID doda middleware.
    """
    permission_classes = [IsAuthenticated]

    # GET /api/selloffers/
    def list(self, request):
        qs = SellOffer.objects.filter(user=request.user, status='active')
        data = SellOfferSerializer(qs, many=True, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_200_OK)

    # POST /api/selloffers/
    def create(self, request):
        serializer = SellOfferSerializer(data=request.data, context=self.get_serializer_context())
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        offer = serializer.save()
        return Response(SellOfferSerializer(offer).data, status=status.HTTP_201_CREATED)
    
    # PUT /api/selloffers/{pk}/
    def update(self, request, pk=None):
        offer = get_object_or_404(SellOffer, pk=pk, user=request.user)
        serializer = SellOfferSerializer(offer, data=request.data, partial=True, context=self.get_serializer_context())
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # DELETE /api/selloffers/{pk}/
    def destroy(self, request, pk=None):
        offer = get_object_or_404(SellOffer, pk=pk, user=request.user)
        self.cancel_sell_offer(offer)  # status='cancelled', actual=False, zwrot akcji do Stock
        return Response(status=status.HTTP_204_NO_CONTENT)
    

class BuyOfferCalculateView(RequestContextMixin, APIView):
    """
    POST /api/buyoffers/calculate/
    Zwraca szacunkowy koszt transakcji (Mock). Nie tworzy prawdziwej oferty.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # AI uczy się na samej obecności tego zapytania, nie na jego wyniku.
        return Response({
            "estimated_cost": random.uniform(100.0, 5000.0),
            "broker_fee": 5.50,
            "status": "calculation_complete"
        }, status=status.HTTP_200_OK)
    



""" 
OLD buyOffer.py


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
"""

""" 
OLD sellOffer.py


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
"""