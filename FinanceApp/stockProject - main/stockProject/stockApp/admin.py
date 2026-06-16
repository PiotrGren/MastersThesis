from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, BuyOffer, SellOffer, Company, Transaction, Stock, StockRate,BalanceUpdate

class UserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('name', 'surname', 'money', 'role','moneyAfterTransations')}),
    )

# stockApp/admin.py
from django.contrib import admin
from .models.errorLog import ErrorLog

@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp','level','component','error_code','request_id','service_name','env')
    list_filter = ('level','component','service_name','env')
    search_fields = ('message','error_code','request_id','parent_request_id','container_id')


admin.site.register(CustomUser, UserAdmin)
admin.site.register(BuyOffer)
admin.site.register(SellOffer)
admin.site.register(StockRate)
admin.site.register(Stock)
admin.site.register(Company)
admin.site.register(Transaction)
admin.site.register(BalanceUpdate)

