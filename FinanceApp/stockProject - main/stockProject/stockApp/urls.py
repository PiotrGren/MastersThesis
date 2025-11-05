from django.urls import path, include
from rest_framework.routers import DefaultRouter

from stockApp.views.auth import SignUpView, SignInView
from stockApp.views.companies import CompanyViewSet, CompanyRatesView
from stockApp.views.offers import BuyOfferViewSet, SellOfferViewSet
from stockApp.views.user import FundsView, UserStocksView, UserInfoView, UsersMoneyCheckView

router = DefaultRouter()
router.register(r'companies', CompanyViewSet, basename='companies')
router.register(r'buyoffers', BuyOfferViewSet, basename='buyoffers')
router.register(r'selloffers', SellOfferViewSet, basename='selloffers')

urlpatterns = [
    # Auth
    path('api/signUp', SignUpView.as_view(), name='sign-up'),
    path('api/signIn', SignInView.as_view(), name='sign-in'),
    
    # User
    path('api/user/funds', FundsView.as_view(), name='user-funds'),
    path('api/user/stocks', UserStocksView.as_view(), name='user-stocks'),
    path('api/user/info', UserInfoView.as_view(), name='user-info'),
    path('api/users/money-check', UsersMoneyCheckView.as_view(), name='users-money-check'),

    # Companies
    path('api/companies/rates', CompanyRatesView.as_view(), name='company-rates'),

    # Router (companies list/create)
    path('api/', include(router.urls)),
]



#OLD
# urlpatterns = [
    # path('api/signIn', views.signIn, name='signIn'),
    # path('api/signUp', views.signUp, name='signUp'),
    # path('api/addCompany', views.createCompany, name='addCompany'),
    # path('api/companies', views.companies, name='companies'),
    # path('api/addBuyOffer', views.addBuyOffer, name='addBuyOffer'),
    # path('api/addSellOffer',views.addSellOffer, name='addSellOffer'),
    # path('api/user/buyOffers', views.buyOffers, name='buyOffers'),
    # path('api/user/sellOffers',views.sellOffers, name='sellOffers'),
    # path('api/deleteBuyOffer/<int:pk>', views.deleteBuyOffer, name='deleteBuyOffer'),
    # path('api/deleteSellOffer/<int:pk>', views.deleteSellOffer, name='deleteSellOffer'),
    # path('api/user/addMoney', views.addMoney, name='addMoney'),
    # path('api/user/stocks', views.getUserStocks, name='getUserStocks'),
    # path('api/user', views.getUserInfo, name='getUserInfo'),
    # path('api/deleteDb', views.deleteAllDb, name='deleteDb'),
    # path('api/usersMoneyCheck', views.getUsersMoneyCheck, name='getUsersMoneyCheck'),
    # path('api/getCompaniesStockRates', views.getCompaniesStockRates, name ='getCompaniesStockRates'),
# ]