from typing import Dict, Any


def search_products(query: str) -> Dict[str, Any]:
    """Tool — category: 'product'. Product search / category-overview only —
    store lookups (hours, addresses) are answered from the knowledge base
    instead (jumpstart_kb.csv's Store Info rows), not this tool. Renamed
    from find_product_or_store (and dropped its search_type param) once
    store lookups moved to RAG — it never did anything but product search
    and the category-overview fallback, so the name and signature now
    describe what it actually does.
    """
    from store.models import Product, Category
    from django.db.models import Q

    # Tokenised search — the query is often a full sentence ("do you sell
    # Sony noise cancelling headphones"), so match on significant words and
    # rank by how many of them hit.
    STOPWORDS = {'the', 'and', 'you', 'your', 'for', 'with', 'have', 'sell',
                 'want', 'wants', 'know', 'buy', 'any', 'are', 'does', 'available','do',
                   'is', 'in', 'at', 'on', 'of', 'to', 'a', 'an',
                 'customer', 'looking', 'find', 'need', 'get', 'store', 'shop'}
    words = [w.strip('?.,!').lower() for w in query.split()]
    words = [w for w in words if len(w) > 2 and w not in STOPWORDS]

    # A generic "what do you sell"-style query has no product-identifying words
    # left once catalog-browsing filler is removed. Keyword-matching such a
    # sentence would surface essentially arbitrary items and misrepresent the
    # range — answer with a real category overview from the database instead.
    GENERIC_BROWSE_WORDS = {
        'what', 'kind', 'kinds', 'type', 'types', 'product', 'products',
        'item', 'items', 'thing', 'things', 'stuff', 'company', 'selling',
        'sale', 'sales', 'carry', 'offer', 'offers', 'range', 'catalog',
        'catalogue', 'variety', 'online', 'website', 'physical',
    }
    if not [w for w in words if w not in GENERIC_BROWSE_WORDS]:
        from django.db.models import Count, Min, Max
        categories = Category.objects.annotate(
            product_count=Count('products', filter=Q(products__is_active=True)),
            min_price=Min('products__price', filter=Q(products__is_active=True)),
            max_price=Max('products__price', filter=Q(products__is_active=True)),
        ).filter(product_count__gt=0).order_by('name')
        return {
            'tool': 'find_product_or_store',
            'success': True,
            'search_type': 'category_overview',
            'purchase_channels': ['online (website)', 'in-store (physical shops)'],
            'total_products': Product.objects.filter(is_active=True).count(),
            'results': [
                {
                    'category': c.name,
                    'products_available': c.product_count,
                    'price_range': f'${c.min_price}–${c.max_price}',
                }
                for c in categories
            ],
        }

    if words:
        q_obj = Q()
        for w in words:
            q_obj |= Q(name__icontains=w) | Q(description__icontains=w)
        candidates = Product.objects.filter(q_obj, is_active=True)[:20]
    else:
        candidates = Product.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query), is_active=True
        )[:20]

    def match_score(p):
        text = f'{p.name} {p.description}'.lower()
        return sum(1 for w in words if w in text)

    products = sorted(candidates, key=match_score, reverse=True)[:5]

    return {
        'tool': 'find_product_or_store',
        'success': len(products) > 0,
        'search_type': 'product',
        'count': len(products),
        'results': [
            {
                'name': p.name,
                'slug': p.slug,
                'price': str(p.price),
                'category': p.category.name if p.category else None,
                'in_stock': p.stock > 0,
                'rating': str(p.rating),
            }
            for p in products
        ],
    }
