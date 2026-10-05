# sku_manager/models.py
from django.db import models
from django.db.models import Sum
import re

class Platform(models.Model):
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class StorageBox(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=100, blank=True, default='')
    color_tag = models.CharField(max_length=20, default='#F59E0B')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class JewelrySKU(models.Model):
    # 1. Product Attributes
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, default='General')
    style = models.CharField(max_length=50, blank=True, default='Standard')
    design_model = models.CharField(max_length=50, blank=True, default='')
    size = models.CharField(max_length=30, blank=True, default='Free Size')
    color = models.CharField(max_length=30, blank=True, default='Black')
    number = models.CharField(max_length=10, default='001')
    sku = models.CharField(max_length=100, unique=True, editable=False)
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    is_listed = models.BooleanField(default=True)

    # 2. Aggregated Live Stock & Active Location
    batch_no = models.CharField(max_length=50, blank=True, default='')
    stock = models.PositiveIntegerField(default=0)
    storage_box = models.ForeignKey(StorageBox, on_delete=models.SET_NULL, null=True, blank=True, related_name='skus')
    section_name = models.CharField(max_length=50, blank=True, default='Main Slot')

    # 3. Base Pricing
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    @staticmethod
    def sanitize(value):
        value = str(value or '').strip()
        return re.sub(r'[^A-Za-z0-9]', '', value).upper()

    def sync_stock_from_batches(self):
        """Calculates the live stock from active batches and refreshes the latest cached metadata."""
        total = self.batches.filter(status='active').aggregate(total=Sum('quantity'))['total'] or 0
        self.stock = max(0, int(total))

        latest_batch = self.batches.filter(status='active').order_by('-created_at').first()
        if latest_batch:
            self.purchase_price = latest_batch.purchase_price
            self.selling_price = latest_batch.selling_price
            self.batch_no = latest_batch.batch_no
            if latest_batch.storage_box:
                self.storage_box = latest_batch.storage_box
            if latest_batch.section_name:
                self.section_name = latest_batch.section_name

        self.save()

    def save(self, *args, **kwargs):
        if not self.sku:
            category_tag = re.sub(r'[^A-Z0-9]', '', self.category.upper())[:3] or 'GEN'
            style_tag = re.sub(r'[^A-Z0-9]', '', self.style.upper())[:3] or 'STD'
            name_tag = re.sub(r'[^A-Z0-9]', '', self.name.upper())[:4] or 'ITEM'
            color_tag = re.sub(r'[^A-Z0-9]', '', self.color.upper())[:3] or 'BLK'
            last_id = JewelrySKU.objects.order_by('-id').values_list('id', flat=True).first() or 0
            self.sku = f"{category_tag}-{style_tag}-{name_tag}-{color_tag}-{last_id + 1:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sku} ({self.name})"

class StockBatch(models.Model):
    """Tracks every batch inwarding entry with location and costs."""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('disabled', 'Disabled'),
    ]

    sku = models.ForeignKey(JewelrySKU, on_delete=models.CASCADE, related_name='batches')
    batch_no = models.CharField(max_length=50)
    quantity = models.PositiveIntegerField(default=1)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    storage_box = models.ForeignKey(StorageBox, on_delete=models.SET_NULL, null=True, blank=True)
    section_name = models.CharField(max_length=50, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.sku.sku} - Batch {self.batch_no} (+{self.quantity})"

class PlatformPrice(models.Model):
    sku = models.ForeignKey(JewelrySKU, on_delete=models.CASCADE, related_name='platform_prices')
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        unique_together = ('sku', 'platform')

class DispatchLog(models.Model):
    sku = models.ForeignKey(JewelrySKU, on_delete=models.CASCADE, related_name='dispatch_logs')
    platform = models.ForeignKey(Platform, on_delete=models.SET_NULL, null=True, blank=True)
    platform_name = models.CharField(max_length=50)
    quantity = models.PositiveIntegerField(default=1)
    sold_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    stock_after = models.PositiveIntegerField(default=0)
    dispatched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-dispatched_at']

class AppSettings(models.Model):
    brand_name = models.CharField(max_length=100, default='TATKAL PICK')
    tagline = models.CharField(max_length=150, blank=True, default='Universal Stock & Fast Dispatch')
    currency_symbol = models.CharField(max_length=10, default='₹')
    low_stock_threshold = models.PositiveIntegerField(default=5)
    support_contact = models.CharField(max_length=100, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj