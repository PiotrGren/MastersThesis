from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, BuyOffer, SellOffer, Company, Transaction, Stock, StockRate,BalanceUpdate

class UserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('name', 'surname', 'money', 'role','moneyAfterTransations')}),
    )

admin.site.register(CustomUser, UserAdmin)
admin.site.register(BuyOffer)
admin.site.register(SellOffer)
admin.site.register(StockRate)
admin.site.register(Stock)
admin.site.register(Company)
admin.site.register(Transaction)
admin.site.register(BalanceUpdate)

