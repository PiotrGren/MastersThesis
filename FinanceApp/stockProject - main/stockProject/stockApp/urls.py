from django.urls import path, include
from rest_framework.routers import DefaultRouter

from stockApp.views.auth import SignUpView, SignInView
from stockApp.views.companies import CompanyViewSet, CompanyRatesView, CompanyNewsView, MarketSentimentView
from stockApp.views.offers import BuyOfferViewSet, SellOfferViewSet, BuyOfferCalculateView
from stockApp.views.user import (
    FundsView, UserStocksView, UserInfoView, UsersMoneyCheckView, DebugAirdropView,
    UserWatchlistView, PortfolioAnalysisView, TradeHistoryView, UserSettingsView
)


router = DefaultRouter()
router.register(r'companies', CompanyViewSet, basename='companies')
router.register(r'buyoffers', BuyOfferViewSet, basename='buyoffers')
router.register(r'selloffers', SellOfferViewSet, basename='selloffers')

urlpatterns = [
    # Auth
    path('signUp/', SignUpView.as_view(), name='sign-up'),
    path('signIn/', SignInView.as_view(), name='sign-in'),
    
    # User (Core)
    path('user/funds/', FundsView.as_view(), name='user-funds'),
    path('user/stocks/', UserStocksView.as_view(), name='user-stocks'),
    path('user/info/', UserInfoView.as_view(), name='user-info'),
    path('users/money-check/', UsersMoneyCheckView.as_view(), name='users-money-check'),
    
    # User
    path('user/watchlist/', UserWatchlistView.as_view(), name='user-watchlist'),
    path('user/portfolio-analysis/', PortfolioAnalysisView.as_view(), name='portfolio-analysis'),
    path('user/trade-history/', TradeHistoryView.as_view(), name='trade-history'),
    path('user/settings/', UserSettingsView.as_view(), name='user-settings'),
    
    # Airdrop
    path('debug/airdrop/', DebugAirdropView.as_view(), name='debug-airdrop'),

    # Market & Companies
    path('market/sentiment/', MarketSentimentView.as_view(), name='market-sentiment'),
    path('companies/rates/', CompanyRatesView.as_view(), name='company-rates'),
    path('companies/<int:pk>/news/', CompanyNewsView.as_view(), name='company-news'),

    # OffersW
    path('buyoffers/calculate/', BuyOfferCalculateView.as_view(), name='buyoffers-calculate'),

    # Router (companies list/create, offers list/create/update/delete)
    path('', include(router.urls)),
]






"""
# OLD
# ===========
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from stockApp.views.auth import SignUpView, SignInView
from stockApp.views.companies import CompanyViewSet, CompanyRatesView
from stockApp.views.offers import BuyOfferViewSet, SellOfferViewSet
from stockApp.views.user import FundsView, UserStocksView, UserInfoView, UsersMoneyCheckView, DebugAirdropView


router = DefaultRouter()
router.register(r'companies', CompanyViewSet, basename='companies')
router.register(r'buyoffers', BuyOfferViewSet, basename='buyoffers')
router.register(r'selloffers', SellOfferViewSet, basename='selloffers')

urlpatterns = [
    # Auth
    path('signUp/', SignUpView.as_view(), name='sign-up'),
    path('signIn/', SignInView.as_view(), name='sign-in'),
    
    # User
    path('user/funds/', FundsView.as_view(), name='user-funds'),
    path('user/stocks/', UserStocksView.as_view(), name='user-stocks'),
    path('user/info/', UserInfoView.as_view(), name='user-info'),
    path('users/money-check/', UsersMoneyCheckView.as_view(), name='users-money-check'),
    
    # Airdrop
    path('debug/airdrop/', DebugAirdropView.as_view(), name='debug-airdrop'),

    # Companies
    path('companies/rates/', CompanyRatesView.as_view(), name='company-rates'),

    # Router (companies list/create)
    path('', include(router.urls)),
]"""
