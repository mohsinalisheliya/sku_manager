# sku_manager/models.py
from django.db import models
import re

class Platform(models.Model):
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class JewelrySKU(models.Model):
    CATEGORY_CHOICES = [
        ('BGL', 'BGL - Bangles / Kadas'),
        ('BRC', 'BRC - Bracelet'),
        ('NCK', 'NCK - Necklace / Choker'),
        ('EAR', 'EAR - Earrings'),
        ('SET', 'SET - Complete Set / Combo'),
        ('JHK', 'JHK - Jhumkas'),
        ('RNG', 'RNG - Rings'),
        ('PAY', 'PAY - Anklet / Payal'),
        ('TIK', 'TIK - Maang Tikka'),
    ]

    COLOR_CHOICES = [
        ('GLD', 'GLD - Golden'),
        ('RBYGRN', 'RBYGRN - Ruby & Emerald Green'),
        ('GRN', 'GRN - Emerald Green'),
        ('MRN', 'MRN - Maroon / Ruby'),
        ('ROSE', 'ROSE - Rose Gold'),
        ('SLV', 'SLV - Silver / Rhodium'),
        ('MTC', 'MTC - Multi-Color'),
        ('WHT', 'WHT - White / Pearl'),
        ('BLK', 'BLK - Black'),
        ('BLU', 'BLU - Royal Blue'),
        ('PNK', 'PNK - Baby Pink'),
    ]

    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default='BGL')
    style = models.CharField(max_length=20, default='ADC')
    name = models.CharField(max_length=50, default='LOVE')
    color = models.CharField(max_length=20, choices=COLOR_CHOICES, default='GLD')
    size = models.CharField(max_length=20, default='2.4')
    number = models.CharField(max_length=10, default='001')
    
    sku = models.CharField(max_length=100, unique=True, editable=False)
    is_listed = models.BooleanField(default=False)
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)

    # Core Pricing Fields
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
        self.size = self.size.strip().upper()
        
        clean_num = self.sanitize(self.number) or '001'
        if clean_num.isdigit() and len(clean_num) < 3:
            clean_num = clean_num.zfill(3)
        self.number = clean_num

        self.sku = f"{self.category}-{self.style}-{self.name}-{self.color}-{self.size}-{self.number}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.sku


class PlatformPrice(models.Model):
    sku = models.ForeignKey(JewelrySKU, on_delete=models.CASCADE, related_name='platform_prices')
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        unique_together = ('sku', 'platform')

    def __str__(self):
        return f"{self.sku.sku} - {self.platform.name}: ₹{self.price}"