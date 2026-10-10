from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import services
from .models import (
    Batch,
    BatchYield,
    Order,
    PreparationCost,
    Product,
    Sale,
    SellingUnit,
)


class BaseData(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('seller', password='pass12345')
        self.profile = self.user.profile
        self.profile.business_name = 'Test Produce'
        self.profile.onboarded = True
        self.profile.save()
        self.client.force_login(self.user)

        self.product = Product.objects.create(owner=self.user, name='Irish Potatoes')
        self.unit = SellingUnit.objects.create(
            product=self.product,
            measure=SellingUnit.Measure.LITRE,
            size=Decimal('5'),
            current_price=Decimal('3000'),
        )
        self.order = Order.objects.create(
            owner=self.user,
            product=self.product,
            quantity_kg=Decimal('200'),
            order_price=Decimal('180000'),
            opening_balance=Decimal('500000'),
            transport_to_market=Decimal('20000'),
            transport_from_market=Decimal('5000'),
            food_amount=Decimal('5000'),
        )


class OrderMathTests(BaseData):
    def test_order_math(self):
        self.assertEqual(self.order.price_per_kg, Decimal('900.00'))
        self.assertEqual(self.order.bags, Decimal('4.00'))
        self.assertEqual(self.order.expenses_total, Decimal('30000.00'))
        self.assertEqual(self.order.total_spent, Decimal('210000.00'))
        self.assertEqual(self.order.money_remaining, Decimal('290000.00'))

    def test_money_remaining_can_go_negative(self):
        self.order.opening_balance = Decimal('100000')
        self.order.save()
        self.assertEqual(self.order.money_remaining, Decimal('-110000.00'))


class BatchAndYieldTests(BaseData):
    def setUp(self):
        super().setUp()
        self.batch = Batch.objects.create(
            order=self.order, owner=self.user, received_date=timezone.localdate()
        )
        self.item = BatchYield.objects.create(
            batch=self.batch,
            selling_unit=self.unit,
            quantity_produced=30,
        )

    def test_potential_revenue_and_expected_profit(self):
        self.assertEqual(self.item.potential_revenue, Decimal('90000.00'))
        self.assertEqual(self.batch.produced_total, 30)
        self.assertEqual(self.batch.potential_revenue, Decimal('90000.00'))
        self.assertEqual(self.batch.expected_profit, Decimal('-120000.00'))
        self.assertFalse(self.batch.potential_is_profitable)

    def test_prep_cost_is_part_of_total_cost(self):
        PreparationCost.objects.create(
            batch=self.batch, description='Washing', amount=Decimal('8000')
        )
        self.assertEqual(self.batch.total_prep_cost, Decimal('8000'))
        self.assertEqual(self.batch.total_cost, Decimal('218000.00'))

    def test_sold_and_available_after_sale(self):
        Sale.objects.create(owner=self.user, yield_item=self.item, quantity=3,
                            unit_price=self.item.price)
        self.assertEqual(self.item.sold_quantity, 3)
        self.assertEqual(self.item.available_quantity, 27)
        self.assertEqual(self.batch.sold_total, 3)
        self.assertEqual(self.batch.available_total, 27)

    def test_revenue_made(self):
        Sale.objects.create(owner=self.user, yield_item=self.item, quantity=2,
                            unit_price=Decimal('3000'))
        self.assertEqual(self.item.revenue_made, Decimal('6000.00'))


class SaleAndLaybyTests(BaseData):
    def setUp(self):
        super().setUp()
        self.batch = Batch.objects.create(
            order=self.order, owner=self.user, received_date=timezone.localdate()
        )
        self.item = BatchYield.objects.create(
            batch=self.batch, selling_unit=self.unit, quantity_produced=10
        )

    def test_sale_amount(self):
        sale = Sale.objects.create(owner=self.user, yield_item=self.item,
                                   quantity=4, unit_price=self.item.price)
        self.assertEqual(sale.amount, Decimal('12000.00'))
        self.assertEqual(sale.unit_label, '5 Litre bucket')

    def test_layby_days_outstanding(self):
        sale = Sale.objects.create(
            owner=self.user,
            yield_item=self.item,
            quantity=1,
            unit_price=self.item.price,
            payment_method=Sale.Payment.LAYBY,
            customer_name='Mama',
            sale_date=timezone.localdate() - timezone.timedelta(days=5),
        )
        self.assertEqual(sale.days_outstanding, 5)
        self.assertFalse(sale.is_settled)

    def test_sales_totals_exclude_open_laybys_from_money_in(self):
        Sale.objects.create(owner=self.user, yield_item=self.item, quantity=2,
                            unit_price=self.item.price)
        Sale.objects.create(owner=self.user, yield_item=self.item, quantity=2,
                            unit_price=self.item.price,
                            payment_method=Sale.Payment.LAYBY, customer_name='John')
        totals = services.sales_totals(self.user)
        self.assertEqual(totals['cash_received'], Decimal('6000.00'))
        self.assertEqual(totals['layby_open'], Decimal('6000.00'))
        self.assertEqual(totals['money_in'], Decimal('6000.00'))
        self.assertEqual(totals['expected_in'], Decimal('12000.00'))


class OrderViewTests(BaseData):
    def test_create_order_form_saves_and_updates_prices(self):
        response = self.client.post(reverse('order_create'), {
            'product': self.product.pk,
            'order_date': timezone.localdate().isoformat(),
            'quantity_kg': '200',
            'order_price': '180000',
            'transport_to_market': '20000',
            'transport_from_market': '5000',
            'food_amount': '0',
            'other_amount': '0',
            'opening_balance': '200000',
            'notes': '',
            f'unit_price_{self.unit.pk}': '3500',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.filter(owner=self.user).count(), 2)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.current_price, Decimal('3500.00'))

    def test_receive_batch_creates_batch_and_yields(self):
        response = self.client.post(reverse('receive_batch', args=[self.order.pk]), {
            'received_date': timezone.localdate().isoformat(),
            'notes': '',
            f'yield_{self.unit.pk}': '38',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.order.batches.count(), 1)
        batch = self.order.batches.first()
        self.assertEqual(batch.yields.count(), 1)
        self.assertEqual(batch.yields.first().quantity_produced, 38)

    def test_receive_batch_requires_a_count(self):
        response = self.client.post(reverse('receive_batch', args=[self.order.pk]), {
            'received_date': timezone.localdate().isoformat(),
            'notes': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.order.batches.count(), 0)

    def test_delete_order_removes_it(self):
        response = self.client.post(reverse('order_delete', args=[self.order.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Order.objects.filter(pk=self.order.pk).exists())

    def test_cannot_delete_order_whose_stock_is_sold(self):
        batch = Batch.objects.create(
            order=self.order, owner=self.user, received_date=timezone.localdate()
        )
        item = BatchYield.objects.create(
            batch=batch, selling_unit=self.unit, quantity_produced=5
        )
        Sale.objects.create(owner=self.user, yield_item=item, quantity=2,
                            unit_price=self.unit.current_price)
        response = self.client.post(reverse('order_delete', args=[self.order.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())


class SellViewTests(BaseData):
    def setUp(self):
        super().setUp()
        self.batch = Batch.objects.create(
            order=self.order, owner=self.user, received_date=timezone.localdate()
        )
        self.item = BatchYield.objects.create(
            batch=self.batch, selling_unit=self.unit, quantity_produced=10
        )

    def test_cash_sale_records(self):
        response = self.client.post(reverse('sale_record'), {
            'yield_id': self.item.pk,
            'sale_date': timezone.localdate().isoformat(),
            'payment': 'cash',
            'quantity': '3',
            'next': reverse('sell'),
        })
        self.assertEqual(response.status_code, 302)
        sale = Sale.objects.get()
        self.assertEqual(sale.quantity, 3)
        self.assertEqual(sale.payment_method, Sale.Payment.CASH)
        self.assertEqual(sale.unit_price, Decimal('3000.00'))

    def test_layby_without_name_is_rejected(self):
        response = self.client.post(reverse('sale_record'), {
            'yield_id': self.item.pk,
            'sale_date': timezone.localdate().isoformat(),
            'payment': 'layby',
            'quantity': '1',
            'customer_name': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Sale.objects.count(), 0)

    def test_cannot_sell_more_than_available(self):
        response = self.client.post(reverse('sale_record'), {
            'yield_id': self.item.pk,
            'sale_date': timezone.localdate().isoformat(),
            'payment': 'cash',
            'quantity': '11',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Sale.objects.count(), 0)

    def test_settle_layby(self):
        sale = Sale.objects.create(
            owner=self.user, yield_item=self.item, quantity=1,
            unit_price=Decimal('3000'),
            payment_method=Sale.Payment.LAYBY, customer_name='Mama',
        )
        response = self.client.post(reverse('layby_settle', args=[sale.pk]))
        self.assertEqual(response.status_code, 302)
        sale.refresh_from_db()
        self.assertEqual(sale.layby_status, Sale.LaybyStatus.SETTLED)
        self.assertIsNotNone(sale.settled_at)


class ProfitReportTests(BaseData):
    def test_profit_report_counts_everything(self):
        batch = Batch.objects.create(
            order=self.order, owner=self.user, received_date=timezone.localdate()
        )
        PreparationCost.objects.create(
            batch=batch, description='Prep', amount=Decimal('5000')
        )
        item = BatchYield.objects.create(
            batch=batch, selling_unit=self.unit, quantity_produced=10
        )
        Sale.objects.create(owner=self.user, yield_item=item, quantity=10,
                            unit_price=Decimal('3000'))

        report = services.profit_report(self.user)
        self.assertEqual(report['total_spent'], Decimal('215000.00'))
        self.assertEqual(report['money_in'], Decimal('30000.00'))
        self.assertEqual(report['profit'], Decimal('-185000.00'))
        self.assertFalse(report['in_profit'])
        self.assertEqual(report['to_break_even'], Decimal('185000.00'))

    def test_stock_totals(self):
        batch = Batch.objects.create(
            order=self.order, owner=self.user, received_date=timezone.localdate()
        )
        item = BatchYield.objects.create(
            batch=batch, selling_unit=self.unit, quantity_produced=10
        )
        Sale.objects.create(owner=self.user, yield_item=item, quantity=4,
                            unit_price=self.unit.current_price)
        stock = services.stock_totals(self.user)
        self.assertEqual(stock['produced_buckets'], 10)
        self.assertEqual(stock['sold_buckets'], 4)
        self.assertEqual(stock['available_buckets'], 6)
        self.assertEqual(stock['potential_revenue'], Decimal('30000.00'))


class AccessTests(BaseData):
    def test_dashboard_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_dashboard_redirects_to_onboarding(self):
        self.profile.onboarded = False
        self.profile.save()
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, reverse('onboarding'))

    def test_cannot_open_another_users_order(self):
        other = User.objects.create_user('other', password='pass12345')
        other_product = Product.objects.create(owner=other, name='Maize')
        other_order = Order.objects.create(
            owner=other, product=other_product,
            quantity_kg=Decimal('50'), order_price=Decimal('1000'),
        )
        response = self.client.get(reverse('order_detail', args=[other_order.pk]))
        self.assertEqual(response.status_code, 404)


class OnboardingTests(TestCase):
    def test_register_creates_profile(self):
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': '',
            'password1': 'verystrongpass123',
            'password2': 'verystrongpass123',
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username='newuser')
        self.assertIsNotNone(user.profile)
        self.assertFalse(user.profile.onboarded)

    def test_onboarding_creates_product_and_selling_units(self):
        user = User.objects.create_user('fresh', password='pass12345')
        self.client.force_login(user)
        response = self.client.post(reverse('onboarding'), {
            'business_name': 'Fresh Produce',
            'phone': '099',
            'product_name': 'Irish Potatoes',
            'form-TOTAL_FORMS': '3',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-unit_type': 'litre:5',
            'form-0-label': '',
            'form-0-price': '3000',
            'form-1-unit_type': 'kg:50',
            'form-1-label': '',
            'form-1-price': '45000',
            'form-2-unit_type': '',
            'form-2-label': '',
            'form-2-price': '',
        })
        self.assertEqual(response.status_code, 302)
        user.profile.refresh_from_db()
        self.assertTrue(user.profile.onboarded)
        self.assertEqual(user.products.count(), 1)
        units = user.products.first().units.all()
        self.assertEqual(units.count(), 2)
        five = units.filter(measure=SellingUnit.Measure.LITRE).first()
        self.assertEqual(five.size, Decimal('5'))
        self.assertEqual(five.current_price, Decimal('3000.00'))

    def test_onboarding_requires_at_least_one_unit(self):
        user = User.objects.create_user('fresh2', password='pass12345')
        self.client.force_login(user)
        response = self.client.post(reverse('onboarding'), {
            'business_name': 'Fresh Produce',
            'phone': '099',
            'product_name': 'Irish Potatoes',
            'form-TOTAL_FORMS': '3',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-unit_type': '',
            'form-0-label': '',
            'form-0-price': '',
            'form-1-unit_type': '',
            'form-1-label': '',
            'form-1-price': '',
            'form-2-unit_type': '',
            'form-2-label': '',
            'form-2-price': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'at least one quantity')