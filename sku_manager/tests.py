from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from .models import DispatchLog, JewelrySKU, Platform, StockBatch, StorageBox
from .views import COLOR_PALETTE


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


class BoxManagerColorTests(TestCase):
	def setUp(self):
		user = get_user_model().objects.create_user(username='box-user', password='test-password')
		self.client.force_login(user)
		self.url = reverse('box_manager')

	def test_palette_contains_72_unique_swatches_and_marks_used_colors(self):
		used_color = COLOR_PALETTE[0]
		StorageBox.objects.create(name='Existing Box', color_tag=used_color)

		response = self.client.get(self.url)

		self.assertEqual(len(COLOR_PALETTE), 72)
		self.assertEqual(len(set(COLOR_PALETTE)), 72)
		swatches = response.context['color_swatches']
		self.assertEqual(len(swatches), 72)
		used_swatch = next(swatch for swatch in swatches if swatch['hex'] == used_color)
		self.assertTrue(used_swatch['is_taken'])
		self.assertEqual(used_swatch['used_by'], 'Existing Box')

	def test_creates_box_with_valid_custom_color(self):
		response = self.client.post(self.url, {
			'box_name': 'Custom Box',
			'color_tag': '#123456',
			'description': 'Test location',
		})

		self.assertRedirects(response, self.url)
		self.assertTrue(StorageBox.objects.filter(name='Custom Box', color_tag='#123456').exists())

	def test_rejects_invalid_color_duplicate_name_and_duplicate_color(self):
		StorageBox.objects.create(name='Existing Box', color_tag='#A1B2C3')
		invalid_submissions = [
			{'box_name': 'Invalid Color', 'color_tag': 'not-a-color'},
			{'box_name': 'existing box', 'color_tag': '#123456'},
			{'box_name': 'Duplicate Color', 'color_tag': '#A1B2C3'},
		]

		for submission in invalid_submissions:
			with self.subTest(submission=submission):
				response = self.client.post(self.url, submission)
				self.assertRedirects(response, self.url)

		self.assertEqual(StorageBox.objects.count(), 1)
