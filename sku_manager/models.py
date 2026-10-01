# sku_manager/models.py
from django.db import models
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
    CATEGORY_CHOICES = [
        ('APP', 'APP - Apparel / Clothing'),
        ('ACC', 'ACC - Accessories'),
        ('ELC', 'ELC - Electronics / Gadgets'),
        ('FTW', 'FTW - Footwear'),
        ('HOM', 'HOM - Home & Living'),
        ('BEA', 'BEA - Beauty & Care'),
        ('NCK', 'NCK - Necklace / Chain'),
        ('BGL', 'BGL - Bangles / Kada'),
        ('GEN', 'GEN - General Goods'),
    ]

    COLOR_CHOICES = [
        ('BLK', 'BLK - Black'),
        ('WHT', 'WHT - White'),
        ('BLU', 'BLU - Blue'),
        ('RED', 'RED - Red'),
        ('GRN', 'GRN - Green'),
        ('GLD', 'GLD - Gold'),
        ('SLV', 'SLV - Silver'),
        ('BRN', 'BRN - Brown'),
        ('MTC', 'MTC - Multi-Color'),
    ]

    # 1. Product Attributes
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default='GEN')
    style = models.CharField(max_length=20, default='STD')
    name = models.CharField(max_length=50, default='ITEM')
    color = models.CharField(max_length=20, choices=COLOR_CHOICES, default='BLK')
    size = models.CharField(max_length=20, default='FREE')
    number = models.CharField(max_length=10, default='001')
    sku = models.CharField(max_length=100, unique=True, editable=False)
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    is_listed = models.BooleanField(default=False)

    # 2. Aggregated Live Stock & Active Location
    batch_no = models.CharField(max_length=50, blank=True, default='')
    stock = models.PositiveIntegerField(default=0)
    storage_box = models.ForeignKey(StorageBox, on_delete=models.SET_NULL, null=True, blank=True, related_name='skus')
    section_name = models.CharField(max_length=50, blank=True, default='Section A')

    # 3. Base Pricing
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    @staticmethod
    def sanitize(value):
        return re.sub(r'[^A-Za-z0-9]', '', str(value or '')).upper()

    def save(self, *args, **kwargs):
        self.style = self.sanitize(self.style) or 'STD'
        self.name = self.sanitize(self.name) or 'ITEM'
        self.size = str(self.size or 'FREE').strip().upper()
        
        clean_num = self.sanitize(self.number) or '001'
        if clean_num.isdigit() and len(clean_num) < 3:
            clean_num = clean_num.zfill(3)
        self.number = clean_num

        self.sku = f"{self.category}-{self.style}-{self.name}-{self.color}-{self.size}-{self.number}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sku} ({self.name})"

class StockBatch(models.Model):
    """Tracks every batch inwarding entry with location and costs"""
    sku = models.ForeignKey(JewelrySKU, on_delete=models.CASCADE, related_name='batches')
    batch_no = models.CharField(max_length=50)
    quantity = models.PositiveIntegerField(default=1)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    storage_box = models.ForeignKey(StorageBox, on_delete=models.SET_NULL, null=True, blank=True)
    section_name = models.CharField(max_length=50, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

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