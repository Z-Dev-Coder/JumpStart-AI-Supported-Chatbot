from django.db import models
from django.conf import settings


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', null=True, blank=True)

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    short_description = models.CharField(max_length=300, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    image_2 = models.ImageField(upload_to='products/', null=True, blank=True)
    image_3 = models.ImageField(upload_to='products/', null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0)
    review_count = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'products'

    def __str__(self):
        return self.name

    def _get_image_url(self, field_name):
        image = getattr(self, field_name)
        if not image:
            return ''
        image_value = str(image)
        if image_value.startswith(('http://', 'https://', '/')):
            return image_value
        try:
            return image.url
        except ValueError:
            return image_value

    @property
    def image_url(self):
        return self._get_image_url('image')

    @property
    def image_2_url(self):
        return self._get_image_url('image_2')

    @property
    def image_3_url(self):
        return self._get_image_url('image_3')

    @property
    def discount_percent(self):
        if self.original_price and self.original_price > self.price:
            return int(((self.original_price - self.price) / self.original_price) * 100)
        return 0


class MockOrder(models.Model):
    class Status(models.TextChoices):
        PROCESSING = 'processing', 'Processing'
        CONFIRMED = 'confirmed', 'Confirmed'
        DISPATCHED = 'dispatched', 'Dispatched'
        OUT_FOR_DELIVERY = 'out_for_delivery', 'Out for Delivery'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'
        RETURN_REQUESTED = 'return_requested', 'Return Requested'
        RETURNED = 'returned', 'Returned'

    order_number = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROCESSING)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_delivery = models.DateField(null=True, blank=True)
    tracking_number = models.CharField(max_length=50, blank=True)
    shipping_address = models.TextField(blank=True)
    can_cancel = models.BooleanField(default=False)
    can_return = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mock_orders'
        ordering = ['-created_at']

    def __str__(self):
        return self.order_number


class MockOrderItem(models.Model):
    order = models.ForeignKey(MockOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_channel = models.CharField(max_length=20, default='online', choices=[('online', 'Online'), ('in_store', 'In Store')])
    days_since_purchase = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'mock_order_items'
