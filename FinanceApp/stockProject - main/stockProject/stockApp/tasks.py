
import datetime
import math
import time
from celery import shared_task, group
from .models import BuyOffer, SellOffer, BalanceUpdate,Transaction, Company, Stock, StockRate, TradeLog
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

@shared_task
def executeTransactions(companyIds):
    try:
        databaseTime = 0
        numberOfSellOffers = 0
        numberOfBuyOffers = 0
        startTime = time.time()
        for companyId in companyIds:
            dbStartTime = time.time()
            buyOffers = BuyOffer.objects.filter(company_id=companyId, actual=True).order_by('-maxPrice')
            sellOffers = SellOffer.objects.filter(company_id=companyId, actual=True).order_by('minPrice')
            dbEndTime = time.time()
            databaseTime += dbEndTime - dbStartTime
            numberOfBuyOffers += buyOffers.count()
            numberOfSellOffers += sellOffers.count()
            if buyOffers.count()== 0 or sellOffers.count() == 0:
                continue
            for buyOffer in buyOffers:
                for sellOffer in sellOffers:
                    buyer = buyOffer.user
                    seller = sellOffer.user
                    if (buyOffer.company == sellOffer.company and
                        buyOffer.amount > 0 and 
                        sellOffer.amount > 0 and 
                        buyOffer.maxPrice >= sellOffer.minPrice and
                        seller != buyer):
                        amountToTrade = min(buyOffer.amount, sellOffer.amount)
                        price = (buyOffer.maxPrice + sellOffer.minPrice) /2
                        totalPrice = round(amountToTrade * price,2)
                        with transaction.atomic():
                            if buyer.money >= totalPrice:
                                buyOffer.amount -= amountToTrade
                                sellOffer.amount -= amountToTrade

                                if buyOffer.amount == 0:
                                    buyOffer.actual = False
                                if sellOffer.amount == 0:
                                    sellOffer.actual = False
                                dbStartTime = time.time()    
                                buyOffer.save()
                                sellOffer.save()
                                dbEndTime = time.time()
                                databaseTime += dbEndTime - dbStartTime
                                buyerMoneyChange = -totalPrice
                                buyerMoneyAfterTransactionsChange = -(totalPrice - round(amountToTrade * buyOffer.maxPrice,2))
                                sellerMoneyChange = totalPrice
                                sellerMoneyAfterTransactionsChange = totalPrice
                                dbStartTime = time.time() 
                                BalanceUpdate.objects.create(
                                    user=buyer,
                                    changeAmount=buyerMoneyChange,
                                    changeType='money'
                                )
                                BalanceUpdate.objects.create(
                                    user=buyer,
                                    changeAmount=buyerMoneyAfterTransactionsChange,
                                    changeType='moneyAfterTransactions'
                                )
                                BalanceUpdate.objects.create(
                                    user=seller,
                                    changeAmount=sellerMoneyChange,
                                    changeType='money'
                                )
                                BalanceUpdate.objects.create(
                                    user=seller,
                                    changeAmount=sellerMoneyAfterTransactionsChange,
                                    changeType='moneyAfterTransactions'
                                )
                                buyStock, created = Stock.objects.get_or_create(user=buyOffer.user, company_id=companyId)
                                dbEndTime = time.time()
                                databaseTime += dbEndTime - dbStartTime
                                buyStock.amount += amountToTrade
                                dbStartTime = time.time() 
                                buyStock.save()
                                Transaction.objects.create(
                                    buyOffer=buyOffer,
                                    sellOffer=sellOffer,
                                    amount=amountToTrade,
                                    price=price,
                                    totalPrice=totalPrice
                                )
                                dbEndTime = time.time()
                                databaseTime += dbEndTime - dbStartTime
                            else:
                                continue               
        endTime = time.time()
        applicationTime = endTime - startTime
        TradeLog.objects.using('test').create(
            applicationTime=applicationTime,
            databaseTime=databaseTime,
            numberOfSellOffers=numberOfSellOffers,
            numberOfBuyOffers=numberOfBuyOffers,
            timestamp = datetime.datetime.now(),
            companyIds = companyIds
            )                            
        return companyIds
    except Exception as e:
        logger.error(f"Error executing transactions: {e}")
        raise e

@shared_task
def scheduleTransactions():
    companies = Company.objects.all()
    numCompanies = companies.count()
    groupSize = 1 + numCompanies // max(1,math.ceil(math.sqrt(numCompanies)))
    companyGroups = [companies[i:i + groupSize] for i in range(0, numCompanies, groupSize)]    
    tasks = group(executeTransactions.s([company.id for company in group]) for group in companyGroups)
    tasks.apply_async()

@shared_task
def updateStockRates():
    companies = StockRate.objects.values_list('company', flat=True).distinct()    
    for companyId in companies:
        buyOffers = BuyOffer.objects.filter(company_id=companyId, actual=True)
        sellOffers = SellOffer.objects.filter(company_id=companyId, actual=True)        
        buyPrices = buyOffers.values_list('maxPrice', flat=True)
        sellPrices = sellOffers.values_list('minPrice', flat=True)        
        allPrices = list(buyPrices) + list(sellPrices)        
        if allPrices:
            newAverageRate = sum(allPrices) / len(allPrices)
            try:
                lastStockRate = StockRate.objects.filter(company_id=companyId, actual=True).latest('dateInc')
                lastRate = lastStockRate.rate
                updatedRate = (lastRate + sum(allPrices)) / (len(allPrices) + 1)
                lastStockRate.actual = False
                lastStockRate.save()
            except StockRate.DoesNotExist:
                updatedRate = newAverageRate
            
            StockRate.objects.create(
                company_id=companyId,
                rate=updatedRate,
                dateInc=datetime.datetime.now()
            )

@shared_task
def processBalanceUpdates():
    updates = BalanceUpdate.objects.all()    
    with transaction.atomic():
        for update in updates:
            user = update.user
            if update.changeType == 'money':
                user.money += update.changeAmount
            elif update.changeType == 'moneyAfterTransactions':
                user.moneyAfterTransations += update.changeAmount
            user.save()
        BalanceUpdate.objects.filter(id__in=[update.id for update in updates]).delete()

@shared_task
def expireOffers():
    now = datetime.datetime.now()
    expiredBuyOffers = BuyOffer.objects.filter(actual=True, dateLimit__lt=now)
    for offer in expiredBuyOffers:
        buyer = offer.user
        buyerMoneyAfterTransactionsChange = round(offer.amount * offer.maxPrice,2)
        BalanceUpdate.objects.create(
                                    user=buyer,
                                    changeAmount=buyerMoneyAfterTransactionsChange,
                                    changeType='moneyAfterTransactions'
                                )
        offer.actual = False
        offer.save()

    expiredSellOffers = SellOffer.objects.filter(actual=True, dateLimit__lt=now)
    for offer in expiredSellOffers:
        seller = offer.user
        stock = Stock.objects.get(user=seller, company=offer.company)
        stock.amount += offer.amount
        offer.actual = False
        offer.save()
        stock.save()