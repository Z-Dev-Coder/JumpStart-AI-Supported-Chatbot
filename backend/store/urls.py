from django.urls import path
from . import views

urlpatterns = [
    path('categories/', views.CategoryListView.as_view(), name='api-categories'),
    path('products/', views.ProductListView.as_view(), name='api-products'),
    path('products/<slug:slug>/', views.ProductDetailView.as_view(), name='api-product-detail'),
    path('orders/', views.OrderListView.as_view(), name='api-orders'),
    path('orders/<str:order_number>/', views.OrderDetailView.as_view(), name='api-order-detail'),

    # Admin: product catalog management
    path('admin/categories/', views.AdminCategoryListCreateView.as_view(), name='api-admin-categories'),
    path('admin/categories/<int:pk>/', views.AdminCategoryDetailView.as_view(), name='api-admin-category-detail'),
    path('admin/products/', views.AdminProductListCreateView.as_view(), name='api-admin-products'),
    path('admin/products/<int:pk>/', views.AdminProductDetailView.as_view(), name='api-admin-product-detail'),
]
