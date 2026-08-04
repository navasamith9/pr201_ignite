from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'amount_paise', 'currency', 'provider', 'status', 'provider_order_id', 'created_at')
    list_filter = ('provider', 'status', 'currency')
    search_fields = ('user__username', 'user__email', 'provider_order_id', 'provider_payment_id')
    readonly_fields = ('created_at', 'paid_at', 'provider_order_id', 'provider_payment_id', 'provider_signature')
