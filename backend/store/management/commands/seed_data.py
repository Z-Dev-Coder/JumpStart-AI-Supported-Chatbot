"""
Management command: python manage.py seed_data

Creates demo accounts, categories, products, and mock orders.
Idempotent — safe to run multiple times.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from store.models import Category, Product, MockOrder, MockOrderItem
import uuid

User = get_user_model()


CATEGORIES = [
    {"name": "Electronics",   "slug": "electronics",   "icon": "cpu"},
    {"name": "Fashion",       "slug": "fashion",       "icon": "shirt"},
    {"name": "Accessories",   "slug": "accessories",   "icon": "watch"},
    {"name": "Home & Living", "slug": "home-living",   "icon": "home"},
    {"name": "Sports",        "slug": "sports",        "icon": "activity"},
    {"name": "Books",         "slug": "books",         "icon": "book-open"},
]


def product_image_path(slug):
    return f"products/{slug}.jpg"


PRODUCTS = [
    # Electronics — only Sony headphones on sale
    {"name": "Sony WH-1000XM5 Wireless Headphones", "slug": "sony-wh-1000xm5", "category_slug": "electronics", "description": "Industry-leading noise cancellation with Dual Noise Sensor technology. Up to 30 hours battery life with quick charge.", "price": "279.99", "original_price": "349.99", "stock": 45, "rating": 4.8, "review_count": 1247, "is_featured": True,
     "image_url": "https://img.vistek.net/prodimg/large/453472.jpg"},
    {"name": "Apple iPhone 16 Pro Max 256GB", "slug": "apple-iphone-16-pro-max", "category_slug": "electronics", "description": "Titanium design. A18 Pro chip. The most advanced iPhone ever made.", "price": "1199.00", "original_price": "1199.00", "stock": 12, "rating": 4.9, "review_count": 3421, "is_featured": True,
     "image_url": "https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/iphone-16-pro-finish-select-202409-6-9inch-deserttitanium?wid=900&hei=900&fmt=jpeg&qlt=90&.v=1724018469822"},
    {"name": "Samsung 55\" 4K QLED Smart TV", "slug": "samsung-55-qled-4k", "category_slug": "electronics", "description": "Quantum Dot technology delivers 100% colour volume. AI-powered upscaling for any content.", "price": "799.00", "original_price": "799.00", "stock": 8, "rating": 4.6, "review_count": 567, "is_featured": False,
     "image_url": "https://images.samsung.com/is/image/samsung/p6pim/us/qn55q8faafxza/gallery/us-qled-q8f-qn55q8faafxza-546800315?$product-details-jpg$"},
    {"name": "MacBook Pro 14\" M3 Chip", "slug": "macbook-pro-14-m3", "category_slug": "electronics", "description": "Up to 22 hours battery life. Stunning Liquid Retina XDR display.", "price": "1799.00", "original_price": "1799.00", "stock": 6, "rating": 4.9, "review_count": 892, "is_featured": True,
     "image_url": "https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/mbp14-spaceblack-select-202410?wid=900&hei=900&fmt=jpeg&qlt=90"},
    # Fashion — Wool Coat on sale
    {"name": "Classic Slim Fit Oxford Shirt", "slug": "classic-slim-fit-oxford-shirt", "category_slug": "fashion", "description": "Premium 100% cotton Oxford weave. Available in white, blue, and grey.", "price": "39.99", "original_price": "39.99", "stock": 120, "rating": 4.4, "review_count": 234, "is_featured": False,
     "image_url": "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?w=600&auto=format&fit=crop&q=80"},
    {"name": "Premium Wool Blend Coat", "slug": "premium-wool-blend-coat", "category_slug": "fashion", "description": "80% wool, 20% polyester. Double-breasted silhouette, tailored fit.", "price": "189.00", "original_price": "249.00", "stock": 25, "rating": 4.7, "review_count": 156, "is_featured": True,
     "image_url": "https://live.staticflickr.com/65535/51821892405_cda1033f35_b.jpg"},
    {"name": "Running Trainers — Air Boost Pro", "slug": "air-boost-pro-trainers", "category_slug": "fashion", "description": "Responsive foam midsole. Engineered mesh upper for breathability.", "price": "89.99", "original_price": "89.99", "stock": 78, "rating": 4.5, "review_count": 412, "is_featured": True,
     "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop&q=80"},
    # Accessories — no discounts
    {"name": "Fossil Gen 6 Smartwatch", "slug": "fossil-gen-6-smartwatch", "category_slug": "accessories", "description": "Wear OS by Google. Heart rate tracking, GPS, 3-day battery.", "price": "199.00", "original_price": "199.00", "stock": 30, "rating": 4.3, "review_count": 298, "is_featured": False,
     "image_url": "https://fossil.scene7.com/is/image/FossilPartners/FTW4061_main?wid=900&hei=900&fmt=jpg"},
    {"name": "Premium Leather Wallet", "slug": "premium-leather-wallet", "category_slug": "accessories", "description": "Full-grain Italian leather. RFID blocking. 8 card slots.", "price": "49.99", "original_price": "49.99", "stock": 200, "rating": 4.6, "review_count": 789, "is_featured": False,
     "image_url": "https://images.unsplash.com/photo-1627123424574-724758594e93?w=600&auto=format&fit=crop&q=80"},
    {"name": "Anker 65W USB-C Charging Hub", "slug": "anker-65w-usb-c-hub", "category_slug": "accessories", "description": "7-in-1 hub with HDMI 4K, 3× USB-A, SD/MicroSD, 65W PD.", "price": "35.99", "original_price": "35.99", "stock": 150, "rating": 4.7, "review_count": 1032, "is_featured": False,
     "image_url": "https://cdn.shopify.com/s/files/1/0493/9834/9974/files/Group2147226151_3840x.png?v=1762771229"},
    # Sports — Dumbbell set on sale
    {"name": "Yoga Mat Pro — Non-Slip 6mm", "slug": "yoga-mat-pro-6mm", "category_slug": "sports", "description": "Eco-friendly TPE material. 183cm × 61cm. Carrying strap included.", "price": "29.99", "original_price": "29.99", "stock": 300, "rating": 4.5, "review_count": 567, "is_featured": False,
     "image_url": "https://images.unsplash.com/photo-1601925260368-ae2f83cf8b7f?w=600&auto=format&fit=crop&q=80"},
    {"name": "Adjustable Dumbbell Set (5–52.5 kg)", "slug": "adjustable-dumbbell-set", "category_slug": "sports", "description": "Replaces 15 sets of weights. Dial adjustment system. Moulded plastic storage tray.", "price": "349.00", "original_price": "429.00", "stock": 18, "rating": 4.8, "review_count": 234, "is_featured": True,
     "image_url": "https://www.bowflex.com/on/demandware.static/-/Sites-nautilus-master-catalog/default/dwafb9bc5e/images/bowflex/selecttech/552/100131/bowflex-selecttech-552-dumbbell-set.png"},
    # Home & Living — no discounts
    {"name": "Scented Soy Candle Set — 3 Pack", "slug": "scented-soy-candle-set", "category_slug": "home-living", "description": "Hand-poured soy wax. Vanilla, lavender & sandalwood fragrances. 40-hour burn time each.", "price": "34.99", "original_price": "34.99", "stock": 180, "rating": 4.7, "review_count": 423, "is_featured": True,
     "image_url": "https://cdn.shopify.com/s/files/1/1198/8002/files/Calm_Grounded_Trio_-_Candle_Bundle.jpg?v=1780513670"},
    {"name": "Ceramic Plant Pot Set — 3 Sizes", "slug": "ceramic-plant-pot-set", "category_slug": "home-living", "description": "Minimalist matte finish. Drainage holes included. Perfect for succulents and herbs.", "price": "27.99", "original_price": "27.99", "stock": 95, "rating": 4.5, "review_count": 189, "is_featured": False,
     "image_url": "https://jm.com.sg/cdn/shop/collections/pot.png?crop=center&height=1200&v=1717333124&width=1200"},
    {"name": "Premium Cotton Throw Blanket", "slug": "premium-cotton-throw-blanket", "category_slug": "home-living", "description": "100% organic cotton. Machine washable. 130cm × 170cm. Available in 6 colours.", "price": "44.99", "original_price": "44.99", "stock": 75, "rating": 4.8, "review_count": 312, "is_featured": True,
     "image_url": "https://live.staticflickr.com/8313/7972508204_4b808ec83c_b.jpg"},
    # Books — Atomic Habits on sale
    {"name": "Atomic Habits — James Clear", "slug": "atomic-habits-james-clear", "category_slug": "books", "description": "The life-changing million-copy #1 bestseller. Build good habits, break bad ones.", "price": "10.99", "original_price": "16.99", "stock": 500, "rating": 4.9, "review_count": 8741, "is_featured": True,
     "image_url": "https://covers.openlibrary.org/b/isbn/0735211299-L.jpg"},
    {"name": "The Design of Everyday Things", "slug": "design-everyday-things", "category_slug": "books", "description": "Don Norman's essential guide to user-centred design. Required reading for designers.", "price": "15.99", "original_price": "15.99", "stock": 120, "rating": 4.7, "review_count": 2134, "is_featured": False,
     "image_url": "https://covers.openlibrary.org/b/isbn/0465050654-L.jpg"},
    {"name": "Deep Work — Cal Newport", "slug": "deep-work-cal-newport", "category_slug": "books", "description": "Rules for focused success in a distracted world. Master the art of deep concentration.", "price": "13.99", "original_price": "13.99", "stock": 200, "rating": 4.6, "review_count": 3210, "is_featured": False,
     "image_url": "https://covers.openlibrary.org/b/isbn/1455586692-L.jpg"},
]

MOCK_ORDERS = [
    {
        "order_number": "JS-2024-001",
        "status": "delivered",
        "can_return": True,
        "items": [
            {"product_slug": "sony-wh-1000xm5", "quantity": 1, "unit_price": "279.99", "purchase_channel": "online", "days_since_purchase": 10},
        ],
    },
    {
        "order_number": "JS-2024-002",
        "status": "dispatched",
        "can_cancel": True,
        "items": [
            {"product_slug": "classic-slim-fit-oxford-shirt", "quantity": 2, "unit_price": "39.99", "purchase_channel": "online", "days_since_purchase": 2},
            {"product_slug": "premium-leather-wallet", "quantity": 1, "unit_price": "49.99", "purchase_channel": "online", "days_since_purchase": 2},
        ],
    },
    {
        "order_number": "JS-2024-003",
        "status": "processing",
        "can_cancel": True,
        "items": [
            {"product_slug": "yoga-mat-pro-6mm", "quantity": 1, "unit_price": "29.99", "purchase_channel": "in_store", "days_since_purchase": 0},
        ],
    },
    {
        "order_number": "JS-2024-004",
        "status": "delivered",
        "can_return": True,
        "items": [
            {"product_slug": "macbook-pro-14-m3", "quantity": 1, "unit_price": "1799.00", "purchase_channel": "online", "days_since_purchase": 20},
        ],
    },
]


class Command(BaseCommand):
    help = "Seed demo data: users, categories, products, mock orders."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Delete existing seed data first")

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("Clearing existing seed data...")
            MockOrderItem.objects.all().delete()
            MockOrder.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            User.objects.filter(username__in=["customer_demo", "staff_demo", "admin_demo"]).delete()

        self._create_users()
        self._create_categories()
        self._create_products()
        self._create_orders()
        self.stdout.write(self.style.SUCCESS("Seed data created successfully!"))
        self.stdout.write("")
        self.stdout.write("Demo accounts:")
        self.stdout.write("  Customer  -> username: customer_demo  / password: demo1234!")
        self.stdout.write("  Staff     -> username: staff_demo     / password: demo1234!")
        self.stdout.write("  Admin     -> username: admin_demo     / password: demo1234!")

    def _create_users(self):
        DEMO_PASSWORD = "demo1234!"
        users = [
            {"username": "customer_demo", "email": "customer@jumpstart.demo", "first_name": "Alex", "last_name": "Chen", "role": "customer"},
            {"username": "staff_demo",    "email": "staff@jumpstart.demo",    "first_name": "Sarah", "last_name": "Johnson", "role": "staff"},
            {"username": "admin_demo",    "email": "admin@jumpstart.demo",    "first_name": "Jordan", "last_name": "Park",  "role": "admin"},
        ]
        for u in users:
            user, created = User.objects.get_or_create(
                username=u["username"],
                defaults={
                    "email": u["email"],
                    "first_name": u["first_name"],
                    "last_name": u["last_name"],
                    "role": u["role"],
                    "is_staff": u["role"] in ("staff", "admin"),
                    "is_superuser": u["role"] == "admin",
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
                self.stdout.write(f"  Created user: {user.username} ({user.role})")
            else:
                self.stdout.write(f"  Existing user: {user.username}")
        self._customer = User.objects.get(username="customer_demo")

    def _create_categories(self):
        self._cat_map = {}
        for c in CATEGORIES:
            cat, created = Category.objects.get_or_create(
                slug=c["slug"],
                defaults={"name": c["name"], "icon": c["icon"]},
            )
            self._cat_map[c["slug"]] = cat
            if created:
                self.stdout.write(f"  Created category: {cat.name}")

    def _create_products(self):
        self._product_map = {}
        for p in list(PRODUCTS):
            p = dict(p)
            cat_slug = p.pop("category_slug")
            p.pop("image_url", "")
            image_path = product_image_path(p["slug"])
            cat = self._cat_map.get(cat_slug)
            prod, created = Product.objects.get_or_create(
                slug=p["slug"],
                defaults={**p, "category": cat},
            )
            # Always update price/original_price and image so re-runs stay in sync
            update_fields = {
                "price": p["price"],
                "original_price": p["original_price"],
                "image": image_path,
            }
            Product.objects.filter(pk=prod.pk).update(**update_fields)
            prod.image = image_path
            self._product_map[prod.slug] = prod
            if created:
                self.stdout.write(f"  Created product: {prod.name}")
            else:
                self.stdout.write(f"  Updated product: {prod.name}")

    def _create_orders(self):
        for o in MOCK_ORDERS:
            total = sum(float(i["unit_price"]) * i["quantity"] for i in o["items"])
            order, created = MockOrder.objects.get_or_create(
                order_number=o["order_number"],
                defaults={
                    "customer": self._customer,
                    "status": o["status"],
                    "total_amount": f"{total:.2f}",
                    "can_cancel": o.get("can_cancel", False),
                    "can_return": o.get("can_return", False),
                },
            )
            if created:
                for item_data in o["items"]:
                    prod = self._product_map.get(item_data["product_slug"])
                    if prod:
                        MockOrderItem.objects.create(
                            order=order,
                            product=prod,
                            product_name=prod.name,
                            quantity=item_data["quantity"],
                            unit_price=item_data["unit_price"],
                            purchase_channel=item_data["purchase_channel"],
                            days_since_purchase=item_data["days_since_purchase"],
                        )
                self.stdout.write(f"  Created order: {order.order_number} ({order.status})")
