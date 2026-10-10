from django.contrib import admin
from django.utils import timezone

from unfold.admin import ModelAdmin, TabularInline

from .models import (
    Batch,
    BatchYield,
    Order,
    PreparationCost,
    Product,
    Sale,
    SellingUnit,
)


class SellingUnitInline(TabularInline):
    model = SellingUnit
    extra = 1


class BatchInline(TabularInline):
    model = Batch
    extra = 0
    show_change_link = True


class BatchYieldInline(TabularInline):
    model = BatchYield
    extra = 0


class PrepCostInline(TabularInline):
    model = PreparationCost
    extra = 0


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ('name', 'owner', 'unit_count', 'order_count', 'created_at')
    search_fields = ('name', 'owner__username')
    ordering = ('name',)
    inlines = [SellingUnitInline]

    @admin.display(description='Selling units')
    def unit_count(self, obj):
        return obj.unit_count

    @admin.display(description='Orders')
    def order_count(self, obj):
        return obj.orders.count()


@admin.register(SellingUnit)
class SellingUnitAdmin(ModelAdmin):
    list_display = ('display_label', 'product', 'current_price', 'measure', 'size')
    list_filter = ('measure',)
    search_fields = ('label', 'product__name', 'product__owner__username')
    ordering = ('product', 'measure', 'size')

    @admin.display(description='Unit')
    def display_label(self, obj):
        return obj.display_label


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = (
        'order_date',
        'owner',
        'product',
        'quantity_kg',
        'order_price',
        'expenses_total',
        'total_spent',
        'money_remaining',
        'received',
    )
    list_filter = ('order_date', 'product')
    search_fields = ('owner__username', 'product__name', 'notes')
    date_hierarchy = 'order_date'
    ordering = ('-order_date', '-created_at')
    inlines = [BatchInline]
    readonly_fields = ('created_at',)

    @admin.display(boolean=True)
    def received(self, obj):
        return obj.is_received


@admin.register(Batch)
class BatchAdmin(ModelAdmin):
    list_display = (
        'received_date',
        'owner',
        'product',
        'produced_total',
        'total_cost',
        'potential_revenue',
    )
    list_filter = ('received_date',)
    search_fields = ('order__owner__username', 'order__product__name', 'notes')
    date_hierarchy = 'received_date'
    ordering = ('-received_date', '-created_at')
    inlines = [BatchYieldInline, PrepCostInline]
    readonly_fields = ('created_at',)

    @admin.display(description='Product')
    def product(self, obj):
        return obj.order.product


@admin.register(BatchYield)
class BatchYieldAdmin(ModelAdmin):
    list_display = (
        'batch',
        'selling_unit',
        'quantity_produced',
        'price',
        'potential_revenue',
        'sold_quantity',
        'available_quantity',
    )
    search_fields = ('batch__order__product__name', 'batch__order__owner__username')
    ordering = ('batch',)

    @admin.display(description='Price')
    def price(self, obj):
        return obj.price


@admin.register(PreparationCost)
class PreparationCostAdmin(ModelAdmin):
    list_display = ('spent_at', 'batch', 'description', 'amount')
    list_filter = ('spent_at',)
    search_fields = ('description', 'batch__order__owner__username')
    date_hierarchy = 'spent_at'
    ordering = ('-spent_at', '-created_at')


@admin.register(Sale)
class SaleAdmin(ModelAdmin):
    list_display = (
        'sale_date',
        'owner',
        'unit_label',
        'quantity',
        'unit_price',
        'amount',
        'payment_method',
        'customer_name',
        'customer_phone',
        'layby_status',
        'days_outstanding',
    )
    list_filter = ('payment_method', 'layby_status', 'sale_date')
    search_fields = ('customer_name', 'customer_phone', 'owner__username')
    date_hierarchy = 'sale_date'
    ordering = ('-sale_date', '-created_at')
    readonly_fields = ('created_at',)
    actions = ['mark_settled']

    @admin.display(description='Unit')
    def unit_label(self, obj):
        return obj.unit_label

    @admin.action(description='Mark selected laybys as settled')
    def mark_settled(self, request, queryset):
        updated = queryset.filter(
            payment_method=Sale.Payment.LAYBY,
            layby_status=Sale.LaybyStatus.OPEN,
        ).update(layby_status=Sale.LaybyStatus.SETTLED, settled_at=timezone.now())
        self.message_user(request, f'{updated} layby(s) settled.')
