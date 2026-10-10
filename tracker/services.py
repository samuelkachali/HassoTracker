"""Aggregate money maths used by the dashboard, sell page and summary."""

from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum

from .models import BatchYield, Order, PreparationCost, Sale

ZERO = Decimal('0')
COST_FIELD = DecimalField(max_digits=14, decimal_places=2)


def _sum(qs, expression):
    return qs.annotate(_line=expression).aggregate(total=Sum('_line'))['total'] or ZERO


def _total(qs):
    return qs.aggregate(total=Sum('amount'))['total'] or ZERO


def spending_totals(user):
    aggregates = Order.objects.filter(owner=user).aggregate(
        goods=Sum('order_price'),
        to_market=Sum('transport_to_market'),
        from_market=Sum('transport_from_market'),
        food=Sum('food_amount'),
        other=Sum('other_amount'),
    )
    goods = aggregates['goods'] or ZERO
    transport = (aggregates['to_market'] or ZERO) + (
        aggregates['from_market'] or ZERO
    )
    food = aggregates['food'] or ZERO
    other = aggregates['other'] or ZERO
    expenses_total = transport + food + other
    prep_total = _total(PreparationCost.objects.filter(batch__owner=user))
    return {
        'goods_cost': goods,
        'transport_total': transport,
        'food_total': food,
        'other_total': other,
        'expenses_total': expenses_total,
        'prep_total': prep_total,
        'total_spent': goods + expenses_total + prep_total,
        'order_count': Order.objects.filter(owner=user).count(),
    }


def sales_totals(user):
    sales = Sale.objects.filter(owner=user)
    cash_qs = sales.filter(payment_method=Sale.Payment.CASH)
    settled_qs = sales.filter(
        payment_method=Sale.Payment.LAYBY,
        layby_status=Sale.LaybyStatus.SETTLED,
    )
    open_qs = sales.filter(
        payment_method=Sale.Payment.LAYBY,
        layby_status=Sale.LaybyStatus.OPEN,
    )
    expression = ExpressionWrapper(
        F('quantity') * F('unit_price'), output_field=COST_FIELD
    )
    cash = _sum(cash_qs, expression)
    layby_settled = _sum(settled_qs, expression)
    layby_open = _sum(open_qs, expression)
    return {
        'cash_received': cash,
        'layby_settled': layby_settled,
        'layby_open': layby_open,
        'layby_open_count': open_qs.count(),
        'cash_buckets': cash_qs.aggregate(t=Sum('quantity'))['t'] or 0,
        'money_in': cash + layby_settled,
        'expected_in': cash + layby_settled + layby_open,
    }


def stock_totals(user):
    yields_qs = BatchYield.objects.filter(batch__owner=user)
    produced = yields_qs.aggregate(produced=Sum('quantity_produced'))['produced'] or 0
    potential = yields_qs.annotate(
        potential=ExpressionWrapper(
            F('quantity_produced') * F('selling_unit__current_price'),
            output_field=COST_FIELD,
        )
    ).aggregate(total=Sum('potential'))['total'] or ZERO
    sold = (
        Sale.objects.filter(owner=user).aggregate(total=Sum('quantity'))['total']
        or 0
    )
    return {
        'produced_buckets': produced,
        'sold_buckets': sold,
        'available_buckets': max(produced - sold, 0),
        'potential_revenue': potential,
    }


def day_totals(user, day):
    sales = Sale.objects.filter(owner=user, sale_date=day)
    cash_qs = sales.filter(payment_method=Sale.Payment.CASH)
    layby_qs = sales.filter(payment_method=Sale.Payment.LAYBY)
    expression = ExpressionWrapper(
        F('quantity') * F('unit_price'), output_field=COST_FIELD
    )
    return {
        'sales': sales.select_related(
            'yield_item',
            'yield_item__selling_unit',
            'yield_item__batch',
            'yield_item__batch__order',
            'yield_item__batch__order__product',
        ),
        'cash_amount': _sum(cash_qs, expression),
        'cash_buckets': cash_qs.aggregate(t=Sum('quantity'))['t'] or 0,
        'layby_amount': _sum(layby_qs, expression),
        'layby_buckets': layby_qs.aggregate(t=Sum('quantity'))['t'] or 0,
    }


def profit_report(user):
    spend = spending_totals(user)
    sales = sales_totals(user)
    balance = sales['money_in'] - spend['total_spent']
    return {
        **spend,
        **sales,
        'profit': balance,
        'in_profit': balance >= 0,
        'to_break_even': max(-balance, ZERO),
        'projected_profit': sales['expected_in'] - spend['total_spent'],
    }