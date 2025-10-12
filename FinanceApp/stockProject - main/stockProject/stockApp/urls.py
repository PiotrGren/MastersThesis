from django.urls import path
from . import views

urlpatterns = [
    path('api/signIn', views.signIn, name='signIn'),
    path('api/signUp', views.signUp, name='signUp'),
    path('api/addCompany', views.createCompany, name='addCompany'),
    path('api/companies', views.companies, name='companies'),
    path('api/addBuyOffer', views.addBuyOffer, name='addBuyOffer'),
    path('api/addSellOffer',views.addSellOffer, name='addSellOffer'),
    path('api/user/buyOffers', views.buyOffers, name='buyOffers'),
    path('api/user/sellOffers',views.sellOffers, name='sellOffers'),
    path('api/deleteBuyOffer/<int:pk>', views.deleteBuyOffer, name='deleteBuyOffer'),
    path('api/deleteSellOffer/<int:pk>', views.deleteSellOffer, name='deleteSellOffer'),
    path('api/user/addMoney', views.addMoney, name='addMoney'),
    path('api/user/stocks', views.getUserStocks, name='getUserStocks'),
    path('api/user', views.getUserInfo, name='getUserInfo'),
    path('api/deleteDb', views.deleteAllDb, name='deleteDb'),
    path('api/usersMoneyCheck', views.getUsersMoneyCheck, name='getUsersMoneyCheck'),
    path('api/getCompaniesStockRates', views.getCompaniesStockRates, name ='getCompaniesStockRates'),
]