from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from .models import DispatchLog, JewelrySKU, Platform, StockBatch


class SalesHoldTests(TestCase):
	def setUp(self):
		self.item = JewelrySKU.objects.create(name='Hold Test Product')
		self.platform = Platform.objects.create(name='Test Platform')

	def test_stock_sync_excludes_batches_on_hold(self):
		StockBatch.objects.create(
			sku=self.item,
			batch_no='HOLD-1',
			quantity=4,
			sales_enabled=False,
		)
		StockBatch.objects.create(
			sku=self.item,
			batch_no='SELL-1',
			quantity=2,
		)

		self.item.sync_stock_from_batches()

		self.item.refresh_from_db()
		self.assertEqual(self.item.stock, 2)

	def test_dispatch_skips_older_batch_on_hold(self):
		held_batch = StockBatch.objects.create(
			sku=self.item,
			batch_no='HOLD-1',
			quantity=4,
			sales_enabled=False,
		)
		sellable_batch = StockBatch.objects.create(
			sku=self.item,
			batch_no='SELL-1',
			quantity=2,
		)

		response = self.client.post(
			reverse('scan_dispatch', args=[self.item.sku]),
			{'platform_id': self.platform.pk},
		)

		held_batch.refresh_from_db()
		sellable_batch.refresh_from_db()
		self.item.refresh_from_db()
		self.assertEqual(response.status_code, 302)
		self.assertEqual(held_batch.quantity, 4)
		self.assertEqual(sellable_batch.quantity, 1)
		self.assertEqual(self.item.stock, 1)
		self.assertEqual(DispatchLog.objects.filter(sku=self.item).count(), 1)

	def test_toggle_sales_updates_sellable_stock(self):
		user = get_user_model().objects.create_user(username='stock-user', password='test-password')
		batch = StockBatch.objects.create(
			sku=self.item,
			batch_no='HOLD-1',
			quantity=4,
		)
		self.client.force_login(user)

		response = self.client.post(reverse('toggle_batch_sales', args=[batch.pk]))

		batch.refresh_from_db()
		self.item.refresh_from_db()
		self.assertEqual(response.status_code, 302)
		self.assertFalse(batch.sales_enabled)
		self.assertEqual(self.item.stock, 0)

		self.client.post(reverse('toggle_batch_sales', args=[batch.pk]))

		batch.refresh_from_db()
		self.item.refresh_from_db()
		self.assertTrue(batch.sales_enabled)
		self.assertEqual(self.item.stock, 4)
