from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('service-worker.js', views.service_worker, name='service-worker'),
    path('products/', views.products_page, name='products'),
    path('account/', views.account_page, name='account'),
    # HTMX partials
    path('partials/products/', views.product_grid_partial, name='product-grid-partial'),
    path('partials/products/<slug:slug>/', views.product_detail_partial, name='product-detail-partial'),
    path('partials/categories/', views.categories_partial, name='categories-partial'),
    path('partials/categories/filters/', views.category_filters_partial, name='category-filters-partial'),
]
