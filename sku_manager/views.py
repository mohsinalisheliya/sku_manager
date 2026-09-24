# sku_manager/views.py
import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import JewelrySKU, Platform, PlatformPrice

DEFAULT_PLATFORMS = ['Flipkart', 'Amazon', 'Meesho', 'Website']

def get_or_seed_platforms():
    # Pehli baar run hone par default platforms auto-create honge
    if not Platform.objects.exists():
        for name in DEFAULT_PLATFORMS:
            Platform.objects.get_or_create(name=name)
    return Platform.objects.all().order_by('id')

def get_next_serial():
    latest = JewelrySKU.objects.order_by('-id').first()
    if not latest:
        return '001'
    try:
        return str(int(latest.number) + 1).zfill(3)
    except (ValueError, TypeError):
        return '001'

def sku_generate(request):
    platforms = get_or_seed_platforms()

    if request.method == 'POST':
        category = request.POST.get('category', '').strip()
        style = request.POST.get('style', '').strip()
        name = request.POST.get('name', '').strip()
        color = request.POST.get('color', '').strip()
        size = request.POST.get('size', '').strip()
        number = request.POST.get('number', '').strip()
        stock = request.POST.get('stock', '0').strip()
        purchase_price = request.POST.get('purchase_price', '0').strip()
        selling_price = request.POST.get('selling_price', '0').strip()
        image = request.FILES.get('image')

        try:
            item = JewelrySKU(
                category=category,
                style=style,
                name=name,
                color=color,
                size=size,
                number=number,
                stock=int(stock) if stock.isdigit() else 0,
                purchase_price=float(purchase_price) if purchase_price else 0.0,
                selling_price=float(selling_price) if selling_price else 0.0,
                image=image
            )
            item.save()

            # Dynamic Platform Prices Save
            for p in platforms:
                p_val = request.POST.get(f'platform_price_{p.id}', '').strip()
                if p_val:
                    PlatformPrice.objects.create(
                        sku=item,
                        platform=p,
                        price=float(p_val)
                    )

            messages.success(request, f"SKU '{item.sku}' with prices successfully saved!")
            return redirect('sku_inventory')
        except Exception as e:
            messages.error(request, f"Error saving SKU: {str(e)}")

    existing_skus = list(JewelrySKU.objects.values_list('sku', flat=True))
    return render(request, 'sku_manager/generator.html', {
        'is_edit': False,
        'next_serial': get_next_serial(),
        'existing_skus': existing_skus,
        'platforms': platforms,
        'active_page': 'generator',
    })

def sku_inventory(request):
    search_query = request.GET.get('q', '').strip()
    filter_status = request.GET.get('status', '').strip()
    platforms = get_or_seed_platforms()
    
    sku_list = JewelrySKU.objects.prefetch_related('platform_prices__platform').all()

    if search_query:
        sku_list = sku_list.filter(
            Q(sku__icontains=search_query) |
            Q(name__icontains=search_query) |
            Q(style__icontains=search_query) |
            Q(category__icontains=search_query)
        )

    if filter_status == 'listed':
        sku_list = sku_list.filter(is_listed=True)
    elif filter_status == 'unlisted':
        sku_list = sku_list.filter(is_listed=False)
    elif filter_status == 'out_of_stock':
        sku_list = sku_list.filter(stock=0)

    paginator = Paginator(sku_list, 10)
    page = request.GET.get('page')

    try:
        skus = paginator.page(page)
    except PageNotAnInteger:
        skus = paginator.page(1)
    except EmptyPage:
        skus = paginator.page(paginator.num_pages)

    return render(request, 'sku_manager/inventory.html', {
        'skus': skus,
        'platforms': platforms,
        'search_query': search_query,
        'filter_status': filter_status,
        'total_count': sku_list.count(),
        'active_page': 'inventory',
    })

def sku_edit(request, pk):
    item = get_object_or_404(JewelrySKU, pk=pk)
    platforms = get_or_seed_platforms()

    if request.method == 'POST':
        item.category = request.POST.get('category', '').strip()
        item.style = request.POST.get('style', '').strip()
        item.name = request.POST.get('name', '').strip()
        item.color = request.POST.get('color', '').strip()
        item.size = request.POST.get('size', '').strip()
        item.number = request.POST.get('number', '').strip()
        
        stock_val = request.POST.get('stock', '0').strip()
        item.stock = int(stock_val) if stock_val.isdigit() else 0

        p_price = request.POST.get('purchase_price', '0').strip()
        s_price = request.POST.get('selling_price', '0').strip()
        item.purchase_price = float(p_price) if p_price else 0.0
        item.selling_price = float(s_price) if s_price else 0.0

        if 'image' in request.FILES:
            item.image = request.FILES['image']

        try:
            item.save()

            # Update or create platform prices
            for p in platforms:
                p_val = request.POST.get(f'platform_price_{p.id}', '').strip()
                if p_val:
                    PlatformPrice.objects.update_or_create(
                        sku=item,
                        platform=p,
                        defaults={'price': float(p_val)}
                    )
                else:
                    PlatformPrice.objects.filter(sku=item, platform=p).delete()

            messages.success(request, f"SKU updated to '{item.sku}'!")
            return redirect('sku_inventory')
        except Exception as e:
            messages.error(request, f"Error updating SKU: {str(e)}")

    # Map existing prices for UI input values
    current_prices = {pp.platform_id: pp.price for pp in item.platform_prices.all()}
    existing_skus = list(JewelrySKU.objects.exclude(pk=pk).values_list('sku', flat=True))

    return render(request, 'sku_manager/generator.html', {
        'is_edit': True,
        'edit_item': item,
        'platforms': platforms,
        'current_prices': current_prices,
        'existing_skus': existing_skus,
        'active_page': 'generator',
    })

def add_platform(request):
    """Bina code badle naya platform UI se add karne ke liye"""
    if request.method == 'POST':
        name = request.POST.get('platform_name', '').strip()
        if name:
            Platform.objects.get_or_create(name=name)
            messages.success(request, f"Platform '{name}' added successfully!")
        else:
            messages.error(request, "Platform name cannot be empty.")
    return redirect(request.META.get('HTTP_REFERER', 'sku_generate'))

def sku_delete(request, pk):
    item = get_object_or_404(JewelrySKU, pk=pk)
    sku_val = item.sku
    item.delete()
    messages.info(request, f"SKU '{sku_val}' deleted.")
    return redirect('sku_inventory')

def toggle_listed(request, pk):
    item = get_object_or_404(JewelrySKU, pk=pk)
    item.is_listed = not item.is_listed
    item.save(update_fields=['is_listed', 'updated_at'])
    return redirect(request.META.get('HTTP_REFERER', 'sku_inventory'))

def adjust_stock(request, pk, action):
    item = get_object_or_404(JewelrySKU, pk=pk)
    if action == 'dec':
        item.stock = max(0, item.stock - 1)
    elif action == 'inc':
        item.stock += 1
    item.save(update_fields=['stock', 'updated_at'])
    return redirect(request.META.get('HTTP_REFERER', 'sku_inventory'))

def export_csv(request):
    platforms = Platform.objects.all().order_by('id')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="jewelry_inventory.csv"'

    writer = csv.writer(response)
    
    # Dynamic Headers with all platforms
    headers = ['SKU', 'Category', 'Style', 'Name', 'Color', 'Size', 'Stock', 'Purchase Price (Rs)', 'Base Sell Price (Rs)']
    for p in platforms:
        headers.append(f"{p.name} Price (Rs)")
    headers.extend(['Listed Status', 'Created At'])
    writer.writerow(headers)

    for obj in JewelrySKU.objects.prefetch_related('platform_prices__platform').all():
        price_map = {pp.platform_id: pp.price for pp in obj.platform_prices.all()}
        row = [
            obj.sku, obj.category, obj.style, obj.name,
            obj.color, obj.size, obj.stock,
            obj.purchase_price, obj.selling_price
        ]
        for p in platforms:
            row.append(price_map.get(p.id, ''))
        row.extend([
            'Listed' if obj.is_listed else 'Unlisted',
            obj.created_at.strftime("%Y-%m-%d %H:%M")
        ])
        writer.writerow(row)

    return response


# sku_manager/views.py ke andar add karein (ya update karein):
from django.db.models import Count

def platform_manager(request):
    """Dedicated Page to View and Add Marketplace Platforms"""
    # Default platforms seed agar pehle se nahi hain
    get_or_seed_platforms()

    if request.method == 'POST':
        name = request.POST.get('platform_name', '').strip()
        if name:
            obj, created = Platform.objects.get_or_create(name=name)
            if created:
                messages.success(request, f"Marketplace '{name}' successfully added!")
            else:
                messages.info(request, f"Marketplace '{name}' already exists.")
            return redirect('platform_manager')
        else:
            messages.error(request, "Marketplace name cannot be empty.")

    # Fetch all platforms with total products linked to each
    platforms = Platform.objects.annotate(linked_products=Count('platformprice')).order_by('-id')

    return render(request, 'sku_manager/platforms.html', {
        'platforms': platforms,
        'active_page': 'platforms',
    })

def platform_delete(request, pk):
    """Delete a marketplace platform"""
    platform = get_object_or_404(Platform, pk=pk)
    name = platform.name
    platform.delete()
    messages.info(request, f"Marketplace '{name}' and its linked pricing have been removed.")
    return redirect('platform_manager')