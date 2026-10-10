from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import onboarded_required

from . import services
from .forms import (
    BatchForm,
    OrderForm,
    PreparationCostForm,
    ProductForm,
    SellingUnitForm,
)
from .models import Batch, BatchYield, Order, PreparationCost, Product, Sale, SellingUnit


def _parse_day(value):
    if value:
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError:
            pass
    return timezone.localdate()


def _unit_price_fields(request, product):
    """Extract posted current prices for a product's selling units."""
    for unit in product.units.all():
        value = request.POST.get(f'unit_price_{unit.pk}')
        if value is None or value == '':
            continue
        try:
            price = Decimal(value)
        except (InvalidOperation, ValueError, TypeError):
            continue
        if price >= 0:
            unit.current_price = price
            unit.save(update_fields=['current_price'])


def _products_with_units(user):
    return (
        Product.objects.filter(owner=user)
        .prefetch_related('units')
        .order_by('name')
    )


# ---------------------------------------------------------------- dashboard

@onboarded_required
def dashboard(request):
    user = request.user
    today = timezone.localdate()
    context = {
        'report': services.profit_report(user),
        'stock': services.stock_totals(user),
        'day': services.day_totals(user, today),
        'today': today,
        'recent_sales': Sale.objects.filter(owner=user).select_related(
            'yield_item',
            'yield_item__selling_unit',
            'yield_item__batch__order__product',
        )[:8],
        'open_laybys': Sale.objects.filter(
            owner=user,
            payment_method=Sale.Payment.LAYBY,
            layby_status=Sale.LaybyStatus.OPEN,
        ).select_related('yield_item__selling_unit')[:5],
        'product_count': Product.objects.filter(owner=user).count(),
        'order_count': Order.objects.filter(owner=user).count(),
    }
    return render(request, 'tracker/dashboard.html', context)


# ------------------------------------------------ products & selling units

@onboarded_required
def products(request):
    form = ProductForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        product = form.save(commit=False)
        product.owner = request.user
        try:
            product.save()
        except Exception:
            messages.error(request, 'You already have a product with that name.')
        else:
            messages.success(
                request, f'Product "{product.name}" added. Now add its selling units.'
            )
            return redirect('products')

    context = {
        'products': _products_with_units(request.user),
        'product_form': form,
        'unit_form': SellingUnitForm(),
    }
    return render(request, 'tracker/products.html', context)


@require_POST
@onboarded_required
def unit_add(request, pk):
    product = get_object_or_404(Product, pk=pk, owner=request.user)
    form = SellingUnitForm(request.POST)
    if form.is_valid() and not form.cleaned_data.get('is_empty'):
        form.to_selling_unit(product).save()
        messages.success(request, f'"{form.cleaned_data["label"] or ""}" added'.strip())
        messages.success(request, 'Selling unit added.')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{field}: {error}')
    return redirect('products')


@require_POST
@onboarded_required
def unit_update(request, pk):
    unit = get_object_or_404(SellingUnit, pk=pk, product__owner=request.user)
    value = request.POST.get('price')
    try:
        price = Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        price = None
    if price is not None and price >= 0:
        unit.current_price = price
        unit.save(update_fields=['current_price'])
        messages.success(request, f'{unit.display_label} price updated.')
    else:
        messages.error(request, 'Enter a valid price.')
    return redirect('products')


@require_POST
@onboarded_required
def unit_delete(request, pk):
    unit = get_object_or_404(SellingUnit, pk=pk, product__owner=request.user)
    try:
        unit.delete()
    except ProtectedError:
        messages.error(
            request,
            f'"{unit.display_label}" already has stock or sales - you can edit '
            'its price instead.',
        )
    else:
        messages.success(request, f'"{unit.display_label}" removed.')
    return redirect('products')


# ---------------------------------------------------------------- orders

@onboarded_required
def order_list(request):
    orders = (
        Order.objects.filter(owner=request.user)
        .select_related('product')
        .prefetch_related('batches')
    )
    return render(request, 'tracker/order_list.html', {'orders': orders})


def _order_form_context(user, form):
    return {
        'form': form,
        'products': _products_with_units(user),
    }


@onboarded_required
def order_create(request):
    initial = {}
    product_id = request.GET.get('product')
    if product_id:
        initial['product'] = Product.objects.filter(
            owner=request.user, pk=product_id
        ).first()
    form = OrderForm(request.POST or None, user=request.user, initial=initial)
    if request.method == 'POST' and form.is_valid():
        order = form.save(commit=False)
        order.owner = request.user
        order.save()
        _unit_price_fields(request, order.product)
        messages.success(
            request,
            'Order saved. When the stock arrives, receive it and count the buckets.',
        )
        return redirect('order_detail', pk=order.pk)

    return render(
        request,
        'tracker/order_form.html',
        {**_order_form_context(request.user, form), 'editing': False},
    )


@onboarded_required
def order_edit(request, pk):
    order = get_object_or_404(
        Order.objects.select_related('product'), pk=pk, owner=request.user
    )
    form = OrderForm(request.POST or None, instance=order, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        _unit_price_fields(request, order.product)
        messages.success(request, 'Order updated.')
        return redirect('order_detail', pk=order.pk)

    return render(
        request,
        'tracker/order_form.html',
        {
            **_order_form_context(request.user, form),
            'order': order,
            'editing': True,
        },
    )


@require_POST
@onboarded_required
def order_delete(request, pk):
    order = get_object_or_404(
        Order.objects.prefetch_related('batches__yields__sales'),
        pk=pk,
        owner=request.user,
    )
    try:
        order.delete()
    except ProtectedError:
        messages.error(
            request,
            'Cannot delete this order - its stock has already been sold. '
            'Remove those sales first, or leave the order in place.',
        )
    else:
        messages.success(request, 'Order removed.')
    return redirect('order_list')


@onboarded_required
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.select_related('product').prefetch_related(
            'batches__yields__selling_unit',
            'batches__yields__sales',
            'batches__prep_costs',
        ),
        pk=pk,
        owner=request.user,
    )
    context = {
        'order': order,
        'batch_form': BatchForm(),
        'prep_form': PreparationCostForm(),
        'units': order.product.units.all(),
    }
    return render(request, 'tracker/order_detail.html', context)


@require_POST
@onboarded_required
def receive_batch(request, pk):
    order = get_object_or_404(
        Order.objects.select_related('product'), pk=pk, owner=request.user
    )
    form = BatchForm(request.POST)
    units = order.product.units.all()
    if form.is_valid():
        counts = {}
        for unit in units:
            raw = request.POST.get(f'yield_{unit.pk}')
            if raw in (None, ''):
                continue
            try:
                amount = int(raw)
            except (ValueError, TypeError):
                continue
            if amount > 0:
                counts[unit.pk] = amount
        if not counts:
            messages.error(
                request,
                'Count the buckets this delivery produced and enter at least one.',
            )
        else:
            batch = form.save(commit=False)
            batch.order = order
            batch.owner = request.user
            batch.save()
            for unit in units:
                if unit.pk in counts:
                    BatchYield.objects.create(
                        batch=batch,
                        selling_unit=unit,
                        quantity_produced=counts[unit.pk],
                    )
            messages.success(
                request,
                f'Stock received - {sum(counts.values())} units counted. '
                'Potential outcome is now visible below.',
            )
            return redirect('order_detail', pk=order.pk)
    else:
        messages.error(request, 'Could not receive the stock. Check the date.')
    return redirect('order_detail', pk=order.pk)


# ------------------------------------------------------ preparation costs

@require_POST
@onboarded_required
def prep_add(request, pk):
    batch = get_object_or_404(Batch, pk=pk, owner=request.user)
    form = PreparationCostForm(request.POST)
    if form.is_valid():
        cost = form.save(commit=False)
        cost.batch = batch
        cost.save()
        messages.success(request, 'Preparation cost added.')
    else:
        messages.error(request, 'Could not save the preparation cost.')
    return redirect('order_detail', pk=batch.order_id)


@require_POST
@onboarded_required
def prep_delete(request, pk):
    cost = get_object_or_404(PreparationCost, pk=pk, batch__owner=request.user)
    order_pk = cost.batch.order_id
    cost.delete()
    messages.success(request, 'Preparation cost removed.')
    return redirect('order_detail', pk=order_pk)


# ---------------------------------------------------------------- selling

@onboarded_required
def sell(request):
    user = request.user
    selected = _parse_day(request.GET.get('date'))
    day = services.day_totals(user, selected)

    yields = (
        BatchYield.objects.filter(batch__owner=user)
        .select_related(
            'selling_unit',
            'batch',
            'batch__order',
            'batch__order__product',
        )
        .order_by('batch__order__product__name', 'selling_unit__size')
    )
    prev_day = selected.fromordinal(selected.toordinal() - 1)
    next_day = selected.fromordinal(selected.toordinal() + 1)
    today = timezone.localdate()

    context = {
        'yields': yields,
        'day': day,
        'selected': selected,
        'prev_day': prev_day,
        'next_day': next_day,
        'today': today,
        'day_title': (
            'Today'
            if selected == today
            else ('Tomorrow' if selected > today else '')
            or selected.strftime('%A'),
        ),
        'is_past': selected < today,
        'has_batches': Batch.objects.filter(owner=user).exists(),
        'has_yields': yields.exists(),
        'selected_date_iso': selected.isoformat(),
    }
    return render(request, 'tracker/sell.html', context)


@require_POST
@onboarded_required
def sale_record(request):
    user = request.user
    back = request.POST.get('next') or ''
    selected = _parse_day(request.POST.get('sale_date'))

    yield_item = get_object_or_404(
        BatchYield.objects.select_related('batch__order', 'selling_unit'),
        pk=request.POST.get('yield_id'),
        batch__owner=user,
    )

    try:
        quantity = int(request.POST.get('quantity') or 0)
    except ValueError:
        quantity = 0
    payment = request.POST.get('payment', Sale.Payment.CASH)
    name = (request.POST.get('customer_name') or '').strip()
    phone = (request.POST.get('customer_phone') or '').strip()

    def fail(message):
        messages.error(request, message)
        target = f'?date={selected.isoformat()}' if back else ''
        return redirect(back + target if back else 'sell')

    if quantity < 1:
        return fail('Enter at least 1 unit.')
    if payment not in Sale.Payment.values:
        return fail('Choose CASH or LAYBY.')
    if quantity > yield_item.available_quantity:
        return fail(
            f'Only {yield_item.available_quantity} x '
            f'{yield_item.selling_unit.display_label} available.'
        )
    if payment == Sale.Payment.LAYBY and not name:
        return fail('A layby needs the customer name.')

    Sale.objects.create(
        owner=user,
        yield_item=yield_item,
        quantity=quantity,
        unit_price=yield_item.price,
        payment_method=payment,
        customer_name=name,
        customer_phone=phone,
        sale_date=selected,
    )
    label = yield_item.selling_unit.display_label
    if payment == Sale.Payment.CASH:
        counted = services.day_totals(user, selected)['cash_amount']
        messages.success(
            request,
            f'Recorded {quantity} x {label} for cash '
            f'({counted:,.0f} MWK counted today).',
        )
    else:
        messages.success(
            request,
            f'Layby recorded: {quantity} x {label} for {name}.',
        )
    target = f'?date={selected.isoformat()}' if back else ''
    return redirect(back + target if back else 'sell')


@require_POST
@onboarded_required
def sale_delete(request, pk):
    sale = get_object_or_404(Sale, pk=pk, owner=request.user)
    selected = sale.sale_date
    if sale.is_layby and sale.is_settled:
        messages.error(request, 'A settled layby cannot be deleted here.')
    else:
        sale.delete()
        messages.success(request, 'Sale removed.')
    return redirect(f'/sell/?date={selected.isoformat()}')


# ---------------------------------------------------------------- layby

@onboarded_required
def layby_list(request):
    user = request.user
    status = request.GET.get('status', 'open')
    sales = Sale.objects.filter(
        owner=user, payment_method=Sale.Payment.LAYBY
    ).select_related('yield_item', 'yield_item__selling_unit', 'yield_item__batch__order__product')

    if status == 'settled':
        sales = sales.filter(layby_status=Sale.LaybyStatus.SETTLED)
    elif status == 'all':
        pass
    else:
        status = 'open'
        sales = sales.filter(layby_status=Sale.LaybyStatus.OPEN)

    totals = services.sales_totals(user)
    context = {
        'sales': sales,
        'status': status,
        'totals': totals,
        'open_total': totals['layby_open'],
        'settled_total': totals['layby_settled'],
    }
    return render(request, 'tracker/layby.html', context)


@require_POST
@onboarded_required
def layby_settle(request, pk):
    sale = get_object_or_404(
        Sale,
        pk=pk,
        owner=request.user,
        payment_method=Sale.Payment.LAYBY,
    )
    if sale.layby_status == Sale.LaybyStatus.OPEN:
        sale.layby_status = Sale.LaybyStatus.SETTLED
        sale.settled_at = timezone.now()
        sale.save(update_fields=['layby_status', 'settled_at'])
        messages.success(
            request,
            f'Layby settled: {sale.quantity} x {sale.unit_label}.',
        )
    else:
        messages.info(request, 'This layby is already settled.')
    return redirect('layby')


# ---------------------------------------------------------------- summary

@onboarded_required
def summary(request):
    user = request.user
    report = services.profit_report(user)
    stock = services.stock_totals(user)
    orders = (
        Order.objects.filter(owner=user)
        .select_related('product')
        .order_by('-order_date')[:20]
    )
    context = {
        'report': report,
        'stock': stock,
        'orders': orders,
    }
    return render(request, 'tracker/summary.html', context)