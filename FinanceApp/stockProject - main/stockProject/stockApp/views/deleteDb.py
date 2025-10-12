from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from stockApp.models import Company, Stock, BalanceUpdate, BuyOffer, SellOffer, CustomUser,Transaction, StockRate,Cpu,MarketLog,TradeLog,TrafficLog

@api_view(['GET'])
@permission_classes([AllowAny])
def deleteAllDb(request):
    admin_users = CustomUser.objects.filter(is_superuser=True)
    BuyOffer.objects.all().delete()
    SellOffer.objects.all().delete()
    Stock.objects.all().delete()
    Company.objects.all().delete()
    BalanceUpdate.objects.all().delete()
    Transaction.objects.all().delete()
    StockRate.objects.all().delete()
    CustomUser.objects.exclude(id__in=admin_users.values_list('id', flat=True)).delete()
    Cpu.objects.using('test').all().delete()
    MarketLog.objects.using('test').all().delete()
    TradeLog.objects.using('test').all().delete()
    TrafficLog.objects.using('test').all().delete()
    return Response({"message": "All non-admin data has been deleted."}, status=200)