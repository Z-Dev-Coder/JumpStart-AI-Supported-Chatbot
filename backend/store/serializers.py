from rest_framework import serializers
from .models import Category, Product, MockOrder, MockOrderItem


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'icon', 'description', 'image']


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    discount_percent = serializers.IntegerField(read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'short_description', 'price', 'original_price',
                  'discount_percent', 'image', 'rating', 'review_count',
                  'is_featured', 'category_name', 'stock']

    def get_image(self, obj):
        return obj.image_url


class ProductDetailSerializer(ProductSerializer):
    image_2 = serializers.SerializerMethodField()
    image_3 = serializers.SerializerMethodField()

    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields + ['description', 'image_2', 'image_3', 'created_at']

    def get_image_2(self, obj):
        return obj.image_2_url

    def get_image_3(self, obj):
        return obj.image_3_url


class ProductAdminSerializer(serializers.ModelSerializer):
    """Writable serializer for admin product management — category is settable by id."""
    class Meta:
        model = Product
        fields = ['id', 'category', 'name', 'slug', 'description', 'short_description',
                  'price', 'original_price', 'image', 'image_2', 'image_3', 'stock',
                  'rating', 'review_count', 'is_featured', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class MockOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField()
    product_image = serializers.SerializerMethodField()

    class Meta:
        model = MockOrderItem
        fields = ['id', 'product_name', 'product_image', 'quantity', 'unit_price', 'purchase_channel', 'days_since_purchase']

    def get_product_image(self, obj):
        return obj.product.image_url if obj.product else None


class MockOrderSerializer(serializers.ModelSerializer):
    items = MockOrderItemSerializer(many=True, read_only=True)
    delivery_tracking = serializers.SerializerMethodField()

    class Meta:
        model = MockOrder
        fields = ['id', 'order_number', 'status', 'total_amount', 'estimated_delivery',
                  'tracking_number', 'shipping_address', 'delivery_tracking',
                  'can_cancel', 'can_return', 'created_at', 'items']

    def get_delivery_tracking(self, obj):
        from tools.order_tool import DELIVERY_DATA
        return DELIVERY_DATA.get(obj.tracking_number)
