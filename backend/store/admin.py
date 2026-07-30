from django.contrib import admin
from .models import Category, Product, MockOrder, MockOrderItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'icon']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'stock', 'is_featured', 'is_active']
    list_filter = ['category', 'is_active', 'is_featured']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


class MockOrderItemInline(admin.TabularInline):
    model = MockOrderItem
    extra = 0


@admin.register(MockOrder)
class MockOrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'customer', 'status', 'total_amount', 'created_at']
    list_filter = ['status']
    search_fields = ['order_number']
    inlines = [MockOrderItemInline]
