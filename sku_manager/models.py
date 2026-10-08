# sku_manager/models.py  (simple stock version - NO batches)
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
    color_tag = models.CharField(max_length=20, default='#3B82F6')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class JewelrySKU(models.Model):
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

    # Simple stock: this number IS the stock (no batches)
    stock = models.PositiveIntegerField(default=0)
    storage_box = models.ForeignKey(StorageBox, on_delete=models.SET_NULL, null=True, blank=True, related_name='skus')
    section_name = models.CharField(max_length=50, blank=True, default='Main Slot')

    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        clean_cat = re.sub(r'[^A-Z0-9]', '', self.category.upper()) or 'GEN'
        clean_sty = re.sub(r'[^A-Z0-9]', '', self.style.upper()) or 'STD'
        clean_name = re.sub(r'[^A-Z0-9]', '', self.name.upper()) or 'ITEM'
        clean_col = re.sub(r'[^A-Z0-9]', '', self.color.upper()) or 'BLK'
        clean_size = re.sub(r'[^A-Z0-9]', '', self.size.upper()) or 'FREE'
        clean_num = str(self.number or '001').strip()
        if clean_num.isdigit() and len(clean_num) < 3:
            clean_num = clean_num.zfill(3)

        self.sku = f"{clean_cat}-{clean_sty}-{clean_name}-{clean_col}-{clean_size}-{clean_num}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sku} ({self.name})"


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
    tagline = models.CharField(max_length=150, blank=True, default='Universal Inventory & Dispatch')
    currency_symbol = models.CharField(max_length=10, default='₹')
    low_stock_threshold = models.PositiveIntegerField(default=5)
    support_contact = models.CharField(max_length=100, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj