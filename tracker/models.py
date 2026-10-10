from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone

ZERO = Decimal('0')
BAG_KG = Decimal('50')


class Product(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='products',
    )
    name = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'name'], name='unique_product_per_owner'
            )
        ]

    def __str__(self):
        return self.name

    @property
    def unit_count(self):
        return self.units.count()


class SellingUnit(models.Model):
    """A quantity the product is sold in, with its current selling price.

    e.g. "5 Litre bucket", "8 Litre bucket", "50 kg bag".
    """

    class Measure(models.TextChoices):
        LITRE = 'litre', 'Litres'
        KG = 'kg', 'Kilograms'
        OTHER = 'other', 'Other'

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='units'
    )
    measure = models.CharField(
        max_length=10, choices=Measure.choices, default=Measure.LITRE
    )
    size = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Size in litres or kilograms.',
    )
    label = models.CharField(
        max_length=60,
        blank=True,
        help_text='Used when the unit is a custom one.',
    )
    current_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
        help_text='The price you sell this unit at today.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['measure', 'size', 'created_at']

    def __str__(self):
        return f'{self.display_label} - {self.current_price}'

    @property
    def display_label(self):
        if self.label:
            return self.label
        if self.size is None:
            return 'Unit'
        if self.measure == self.Measure.KG:
            return f'{self.size:g} kg bag'
        if self.measure == self.Measure.LITRE:
            return f'{self.size:g} Litre bucket'
        return f'{self.size:g} unit'


class Order(models.Model):
    """Stock bought from a supplier, with everything spent around it."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders',
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name='orders'
    )
    order_date = models.DateField(default=timezone.localdate)
    quantity_kg = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='KGs ordered',
        help_text='Total kilograms ordered. 50kg is a standard bag.',
    )
    order_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(ZERO)],
        verbose_name='Price for total order',
        help_text='What the whole order of goods cost.',
    )
    opening_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        verbose_name='Money before order',
        help_text='Cash you had before buying.',
    )
    transport_to_market = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
        verbose_name='Transport to the market',
        help_text='Money to go to the market.',
    )
    transport_from_market = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
        verbose_name='Transport coming back',
        help_text='Money to come back.',
    )
    food_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
        verbose_name='Food on the way',
    )
    other_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
        verbose_name='Other costs',
    )
    other_description = models.CharField(
        max_length=150, blank=True, verbose_name='Other description'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-order_date', '-created_at']

    def __str__(self):
        return f'{self.quantity_kg}kg {self.product.name} on {self.order_date}'

    @property
    def bags(self):
        """How many standard 50kg bags the order roughly is."""
        if not self.quantity_kg:
            return ZERO
        return (self.quantity_kg / BAG_KG).quantize(Decimal('0.01'))

    @property
    def price_per_kg(self):
        if not self.quantity_kg:
            return ZERO
        return (self.order_price / self.quantity_kg).quantize(Decimal('0.01'))

    @property
    def expenses_total(self):
        return (
            self.transport_to_market
            + self.transport_from_market
            + self.food_amount
            + self.other_amount
        )

    @property
    def total_spent(self):
        return self.order_price + self.expenses_total

    @property
    def money_remaining(self):
        return self.opening_balance - self.total_spent

    @property
    def is_received(self):
        return self.batches.exists()


class Batch(models.Model):
    """Stock physically received at home and counted into selling units."""

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='batches'
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='batches',
    )
    received_date = models.DateField(default=timezone.localdate)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_date', '-created_at']

    def __str__(self):
        return f'Batch for {self.order} received {self.received_date}'

    @property
    def total_prep_cost(self):
        return self.prep_costs.aggregate(total=Sum('amount'))['total'] or ZERO

    @property
    def total_cost(self):
        return self.order.total_spent + self.total_prep_cost

    @property
    def produced_total(self):
        return sum(item.quantity_produced for item in self.yields.all())

    @property
    def potential_revenue(self):
        return sum(item.potential_revenue for item in self.yields.all())

    @property
    def sold_total(self):
        return sum(item.sold_quantity for item in self.yields.all())

    @property
    def available_total(self):
        return max(self.produced_total - self.sold_total, 0)

    @property
    def expected_profit(self):
        return self.potential_revenue - self.total_cost

    @property
    def potential_is_profitable(self):
        return self.expected_profit >= 0


class BatchYield(models.Model):
    """How many of one selling unit a received batch produced (counted)."""

    batch = models.ForeignKey(
        Batch, on_delete=models.CASCADE, related_name='yields'
    )
    selling_unit = models.ForeignKey(
        SellingUnit, on_delete=models.PROTECT, related_name='yields'
    )
    quantity_produced = models.PositiveIntegerField(
        help_text='Buckets / bags you counted from this batch.'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['selling_unit__size', 'selling_unit__created_at']

    def __str__(self):
        return f'{self.quantity_produced} x {self.selling_unit.display_label}'

    @property
    def price(self):
        return self.selling_unit.current_price

    @property
    def potential_revenue(self):
        return (self.price * self.quantity_produced).quantize(Decimal('0.01'))

    @property
    def sold_quantity(self):
        return self.sales.aggregate(total=Sum('quantity'))['total'] or 0

    @property
    def available_quantity(self):
        return max(self.quantity_produced - self.sold_quantity, 0)

    @property
    def revenue_made(self):
        return sum((sale.amount for sale in self.sales.all()), ZERO)


class PreparationCost(models.Model):
    """Extra costs to get the product ready for sale (washing, packaging...)."""

    batch = models.ForeignKey(
        Batch, on_delete=models.CASCADE, related_name='prep_costs'
    )
    description = models.CharField(
        max_length=150, help_text='What was required to prepare the product?'
    )
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(ZERO)]
    )
    spent_at = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-spent_at', '-created_at']

    def __str__(self):
        return f'{self.description} ({self.amount})'


class Sale(models.Model):
    class Payment(models.TextChoices):
        CASH = 'cash', 'Cash'
        LAYBY = 'layby', 'Layby'

    class LaybyStatus(models.TextChoices):
        OPEN = 'open', 'Awaiting payment'
        SETTLED = 'settled', 'Settled'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sales',
    )
    yield_item = models.ForeignKey(
        BatchYield, on_delete=models.PROTECT, related_name='sales'
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(
        max_length=10, choices=Payment.choices, default=Payment.CASH
    )
    customer_name = models.CharField(max_length=100, blank=True)
    customer_phone = models.CharField(max_length=30, blank=True)
    layby_status = models.CharField(
        max_length=10, choices=LaybyStatus.choices, default=LaybyStatus.OPEN
    )
    sale_date = models.DateField(default=timezone.localdate)
    settled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sale_date', '-created_at']

    def __str__(self):
        who = f' ({self.customer_name})' if self.customer_name else ''
        return (
            f'{self.quantity} x {self.unit_label} '
            f'{self.get_payment_method_display()}{who} on {self.sale_date}'
        )

    @property
    def unit_label(self):
        return self.yield_item.selling_unit.display_label

    @property
    def amount(self):
        return (Decimal(self.quantity) * self.unit_price).quantize(
            Decimal('0.01')
        )

    @property
    def is_layby(self):
        return self.payment_method == self.Payment.LAYBY

    @property
    def is_settled(self):
        return self.is_layby and self.layby_status == self.LaybyStatus.SETTLED

    @property
    def days_outstanding(self):
        return max((timezone.localdate() - self.sale_date).days, 0)
