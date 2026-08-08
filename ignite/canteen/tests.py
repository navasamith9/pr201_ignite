from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from .models import CanteenOrder, MenuItem
from payments.models import Payment


@override_settings(ROOT_URLCONF='canteen.urls_for_tests')
class CanteenOrderTests(TestCase):
    def setUp(self):
        self.student = get_user_model().objects.create_user(username='student', password='test-pass-123')
        self.available_item = MenuItem.objects.create(
            name='Veg sandwich', category='Snacks', price=Decimal('45.00'), is_available=True
        )
        self.sold_out_item = MenuItem.objects.create(
            name='Cold coffee', category='Drinks', price=Decimal('55.00'), is_available=False
        )
        self.client.force_login(self.student)

    def test_checkout_creates_pending_payment_and_assigns_token(self):
        self.client.post(reverse('canteen:add_to_cart', args=[self.available_item.pk]))
        response = self.client.post(reverse('canteen:place_order'))

        order = CanteenOrder.objects.get()
        self.assertRedirects(response, reverse('canteen:checkout_order', args=[order.pk]), fetch_redirect_response=False)
        self.assertEqual(order.token_number, 1)
        self.assertEqual(order.total_amount, Decimal('45.00'))
        self.assertFalse(order.is_paid)
        self.assertEqual(order.items.get().item_name, 'Veg sandwich')
        self.assertEqual(Payment.objects.get().amount_paise, 4500)

        order.complete_payment(payment_reference='order_test', payment_id='payment_test')
        order.refresh_from_db()
        self.assertTrue(order.is_paid)

    def test_unavailable_item_cannot_be_added_or_ordered(self):
        self.client.post(reverse('canteen:add_to_cart', args=[self.sold_out_item.pk]))
        self.assertEqual(self.client.session.get('canteen_cart', {}), {})

        session = self.client.session
        session['canteen_cart'] = {str(self.sold_out_item.pk): 1}
        session.save()
        response = self.client.post(reverse('canteen:place_order'))

        self.assertRedirects(response, reverse('canteen:cart'), fetch_redirect_response=False)
        self.assertFalse(CanteenOrder.objects.exists())

    def test_canteen_admin_can_remove_an_unused_menu_item(self):
        staff = get_user_model().objects.create_user(
            username='canteen-staff', password='test-pass-123', is_canteen_admin=True
        )
        self.client.force_login(staff)

        response = self.client.post(reverse('canteen:delete_menu_item', args=[self.available_item.pk]))

        self.assertRedirects(response, reverse('canteen:staff_menu'), fetch_redirect_response=False)
        self.assertFalse(MenuItem.objects.filter(pk=self.available_item.pk).exists())

    def test_cart_item_can_be_removed_individually(self):
        self.client.post(reverse('canteen:add_to_cart', args=[self.available_item.pk]))
        response = self.client.post(reverse('canteen:remove_from_cart', args=[self.available_item.pk]))

        self.assertRedirects(response, reverse('canteen:cart'), fetch_redirect_response=False)
        self.assertEqual(self.client.session.get('canteen_cart'), {})
