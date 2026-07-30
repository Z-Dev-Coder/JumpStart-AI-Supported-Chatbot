from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Category, Product, MockOrder
from .serializers import (
    CategorySerializer, ProductSerializer, ProductDetailSerializer,
    ProductAdminSerializer, MockOrderSerializer,
)


class IsAdminUser(permissions.BasePermission):
    """Only admin manages the product catalog — staff work support cases, not stock."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin_user()


# ─── API Views ────────────────────────────────────────────────────────────────

class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]


class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True)
        category = self.request.query_params.get('category')
        search = self.request.query_params.get('q')
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        featured = self.request.query_params.get('featured')

        if category:
            qs = qs.filter(category__slug=category)
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        if min_price:
            qs = qs.filter(price__gte=min_price)
        if max_price:
            qs = qs.filter(price__lte=max_price)
        if featured == 'true':
            qs = qs.filter(is_featured=True)
        return qs


class ProductDetailView(generics.RetrieveAPIView):
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductDetailSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'slug'


# ─── Admin: Product Catalog Management ─────────────────────────────────────────

class AdminCategoryListCreateView(generics.ListCreateAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUser]


class AdminCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUser]


class AdminProductListCreateView(generics.ListCreateAPIView):
    queryset = Product.objects.all().select_related('category').order_by('-created_at')
    serializer_class = ProductAdminSerializer
    permission_classes = [IsAdminUser]


class AdminProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductAdminSerializer
    permission_classes = [IsAdminUser]


class OrderListView(generics.ListAPIView):
    serializer_class = MockOrderSerializer

    def get_queryset(self):
        return MockOrder.objects.filter(customer=self.request.user)


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = MockOrderSerializer
    lookup_field = 'order_number'

    def get_queryset(self):
        return MockOrder.objects.filter(customer=self.request.user)


# ─── Template Views ────────────────────────────────────────────────────────────

def _dashboard_redirect(request):
    """Staff and admin work in their dashboards, not the storefront."""
    from django.shortcuts import redirect
    if request.user.is_authenticated:
        if request.user.is_admin_user():
            return redirect('admin-dashboard')
        if request.user.is_support_staff():
            return redirect('staff-dashboard')
    return None


def home(request):
    redirect_response = _dashboard_redirect(request)
    if redirect_response:
        return redirect_response
    featured_products = Product.objects.filter(is_featured=True, is_active=True)[:8]
    categories = Category.objects.all()
    return render(request, 'store/home.html', {
        'featured_products': featured_products,
        'categories': categories,
    })


def products_page(request):
    redirect_response = _dashboard_redirect(request)
    if redirect_response:
        return redirect_response
    categories = Category.objects.all()
    return render(request, 'store/products.html', {'categories': categories})


def account_page(request):
    redirect_response = _dashboard_redirect(request)
    if redirect_response:
        return redirect_response
    return render(request, 'store/account.html', {})


# ─── HTMX Partials ────────────────────────────────────────────────────────────

def product_grid_partial(request):
    """HTMX partial for product grid with filters."""
    redirect_response = _dashboard_redirect(request)
    if redirect_response:
        return redirect_response
    qs = Product.objects.select_related('category').filter(is_active=True)
    category  = request.GET.get('category')
    search    = request.GET.get('q')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    featured  = request.GET.get('featured')
    min_rating = request.GET.get('min_rating')
    in_stock  = request.GET.get('in_stock')
    ordering  = request.GET.get('ordering', '-created_at')
    limit     = request.GET.get('limit')
    view_mode = request.GET.get('view_mode', 'grid')

    if category:
        qs = qs.filter(category__slug=category)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
    if min_price:
        try: qs = qs.filter(price__gte=float(min_price))
        except ValueError: pass
    if max_price:
        try: qs = qs.filter(price__lte=float(max_price))
        except ValueError: pass
    if featured == 'true':
        qs = qs.filter(is_featured=True)
    if min_rating:
        try: qs = qs.filter(rating__gte=float(min_rating))
        except ValueError: pass
    if in_stock == 'true':
        qs = qs.filter(stock__gt=0)
    if ordering == 'price_asc':
        qs = qs.order_by('price')
    elif ordering == 'price_desc':
        qs = qs.order_by('-price')
    elif ordering == 'rating':
        qs = qs.order_by('-rating')
    elif ordering:
        qs = qs.order_by(ordering)
    if limit:
        try: qs = qs[:int(limit)]
        except ValueError: pass

    total_count = qs.count() if not limit else None
    return render(request, 'partials/product_grid.html', {
        'products': qs,
        'view_mode': view_mode,
        'total_count': total_count,
    })


def product_detail_partial(request, slug):
    """HTMX partial for product detail modal."""
    redirect_response = _dashboard_redirect(request)
    if redirect_response:
        return redirect_response
    product = get_object_or_404(Product, slug=slug, is_active=True)
    return render(request, 'partials/product_detail_modal.html', {'product': product})


def categories_partial(request):
    """HTMX partial for category cards (home page)."""
    redirect_response = _dashboard_redirect(request)
    if redirect_response:
        return redirect_response
    categories = Category.objects.all()
    return render(request, 'partials/categories.html', {'categories': categories})


def category_filters_partial(request):
    """HTMX partial for category filter buttons (products sidebar)."""
    redirect_response = _dashboard_redirect(request)
    if redirect_response:
        return redirect_response
    categories = Category.objects.all()
    return render(request, 'partials/category_filters.html', {'categories': categories})


def service_worker(request):
    """Kill-switch service worker. This app doesn't use a service worker, but
    a stale one registered by some other project previously served on this
    localhost origin keeps requesting /service-worker.js (a persistent 404 in
    the logs). Serving this self-unregistering worker lets the browser replace
    the stale registration with one that immediately removes itself."""
    from django.http import HttpResponse
    js = (
        "self.addEventListener('install', () => self.skipWaiting());\n"
        "self.addEventListener('activate', async () => {\n"
        "  await self.registration.unregister();\n"
        "  const clients = await self.clients.matchAll({ type: 'window' });\n"
        "  clients.forEach((client) => client.navigate(client.url));\n"
        "});\n"
    )
    return HttpResponse(js, content_type='application/javascript')
