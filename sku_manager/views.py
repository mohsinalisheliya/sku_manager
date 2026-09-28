# sku_manager/views.py
import csv
import io
import base64
import qrcode
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.db.models import Q, Count
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse
from .models import JewelrySKU, Platform, PlatformPrice, DispatchLog, StorageBox

DEFAULT_PLATFORMS = ['Flipkart', 'Amazon', 'Meesho', 'Website']
DEFAULT_BOXES = [
    ('Box 1', 'blue'),
    ('Box 2', 'amber'),
    ('Box 3', 'emerald'),
    ('Box 4', 'purple'),
]

def get_or_seed_platforms():
    if not Platform.objects.exists():
        for name in DEFAULT_PLATFORMS:
            Platform.objects.get_or_create(name=name)
    return Platform.objects.all().order_by('id')

def get_or_seed_boxes():
    if not StorageBox.objects.exists():
        for name, color in DEFAULT_BOXES:
            StorageBox.objects.get_or_create(name=name, defaults={'color_tag': color})
    return StorageBox.objects.all().order_by('name')

def get_next_serial():
    latest = JewelrySKU.objects.order_by('-id').first()
    if not latest:
        return '001'
    try:
        return str(int(latest.number) + 1).zfill(3)
    except (ValueError, TypeError):
        return '001'

# 1. Box Management Page
def box_manager(request):
    get_or_seed_boxes()

    if request.method == 'POST':
        name = request.POST.get('box_name', '').strip()
        color_tag = request.POST.get('color_tag', 'amber').strip()
        description = request.POST.get('description', '').strip()

        if name:
            box, created = StorageBox.objects.get_or_create(
                name=name,
                defaults={'color_tag': color_tag, 'description': description}
            )
            if created:
                messages.success(request, f"New storage box '{name}' added successfully!")
            else:
                messages.info(request, f"Storage box '{name}' already exists.")
            return redirect('box_manager')
        else:
            messages.error(request, "Box name cannot be empty.")

    boxes = StorageBox.objects.annotate(total_skus=Count('skus')).order_by('name')
    return render(request, 'sku_manager/boxes.html', {
        'boxes': boxes,
        'active_page': 'boxes',
    })

def box_delete(request, pk):
    box = get_object_or_404(StorageBox, pk=pk)
    name = box.name
    box.delete()
    messages.info(request, f"Storage box '{name}' deleted. Associated products are now unassigned.")
    return redirect('box_manager')

# 2. SKU Generator
def sku_generate(request):
    platforms = get_or_seed_platforms()
    boxes = get_or_seed_boxes()

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
        box_id = request.POST.get('storage_box')
        section_name = request.POST.get('section_name', 'Section A').strip()
        image = request.FILES.get('image')

        storage_box = StorageBox.objects.filter(pk=box_id).first() if box_id else None

        try:
            item = JewelrySKU(
                category=category,
                style=style,
                name=name,
                color=color,
                size=size,
                number=number,
                storage_box=storage_box,
                section_name=section_name,
                stock=int(stock) if stock.isdigit() else 0,
                purchase_price=float(purchase_price) if purchase_price else 0.0,
                selling_price=float(selling_price) if selling_price else 0.0,
                image=image
            )
            item.save()

            for p in platforms:
                p_val = request.POST.get(f'platform_price_{p.id}', '').strip()
                if p_val:
                    PlatformPrice.objects.create(sku=item, platform=p, price=float(p_val))

            box_label = storage_box.name if storage_box else "No Box"
            messages.success(request, f"SKU '{item.sku}' saved in {box_label} ({item.section_name})!")
            return redirect('sku_inventory')
        except Exception as e:
            messages.error(request, f"Error saving SKU: {str(e)}")

    existing_skus = list(JewelrySKU.objects.values_list('sku', flat=True))
    return render(request, 'sku_manager/generator.html', {
        'is_edit': False,
        'next_serial': get_next_serial(),
        'existing_skus': existing_skus,
        'platforms': platforms,
        'boxes': boxes,
        'active_page': 'generator',
    })

# 3. Inventory View
def sku_inventory(request):
    search_query = request.GET.get('q', '').strip()
    filter_status = request.GET.get('status', '').strip()
    filter_box = request.GET.get('box', '').strip()
    platforms = get_or_seed_platforms()
    boxes = get_or_seed_boxes()
    
    sku_list = JewelrySKU.objects.select_related('storage_box').prefetch_related('platform_prices__platform').all()

    if search_query:
        sku_list = sku_list.filter(
            Q(sku__icontains=search_query) |
            Q(name__icontains=search_query) |
            Q(storage_box__name__icontains=search_query) |
            Q(section_name__icontains=search_query)
        )

    if filter_box:
        sku_list = sku_list.filter(storage_box__id=filter_box)

    if filter_status == 'listed':
        sku_list = sku_list.filter(is_listed=True)
    elif filter_status == 'unlisted':
        sku_list = sku_list.filter(is_listed=False)
    elif filter_status == 'out_of_stock':
        sku_list = sku_list.filter(stock=0)

    paginator = Paginator(sku_list, 10)
    skus = paginator.get_page(request.GET.get('page'))

    return render(request, 'sku_manager/inventory.html', {
        'skus': skus,
        'platforms': platforms,
        'boxes': boxes,
        'search_query': search_query,
        'filter_status': filter_status,
        'filter_box': filter_box,
        'total_count': sku_list.count(),
        'active_page': 'inventory',
    })

# 4. SKU Edit
def sku_edit(request, pk):
    item = get_object_or_404(JewelrySKU, pk=pk)
    platforms = get_or_seed_platforms()
    boxes = get_or_seed_boxes()

    if request.method == 'POST':
        item.category = request.POST.get('category', '').strip()
        item.style = request.POST.get('style', '').strip()
        item.name = request.POST.get('name', '').strip()
        item.color = request.POST.get('color', '').strip()
        item.size = request.POST.get('size', '').strip()
        item.number = request.POST.get('number', '').strip()
        
        box_id = request.POST.get('storage_box')
        item.storage_box = StorageBox.objects.filter(pk=box_id).first() if box_id else None
        item.section_name = request.POST.get('section_name', 'Section A').strip()

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
            for p in platforms:
                p_val = request.POST.get(f'platform_price_{p.id}', '').strip()
                if p_val:
                    PlatformPrice.objects.update_or_create(sku=item, platform=p, defaults={'price': float(p_val)})
                else:
                    PlatformPrice.objects.filter(sku=item, platform=p).delete()

            messages.success(request, f"Updated '{item.sku}'!")
            return redirect('sku_inventory')
        except Exception as e:
            messages.error(request, f"Error updating SKU: {str(e)}")

    current_prices = {pp.platform_id: pp.price for pp in item.platform_prices.all()}
    existing_skus = list(JewelrySKU.objects.exclude(pk=pk).values_list('sku', flat=True))

    return render(request, 'sku_manager/generator.html', {
        'is_edit': True,
        'edit_item': item,
        'platforms': platforms,
        'boxes': boxes,
        'current_prices': current_prices,
        'existing_skus': existing_skus,
        'active_page': 'generator',
    })

# 5. Scan Dispatch View
def scan_dispatch(request, sku):
    item = get_object_or_404(JewelrySKU.objects.select_related('storage_box'), sku=sku)
    platforms = get_or_seed_platforms()
    price_map = {pp.platform_id: pp.price for pp in item.platform_prices.all()}

    if request.method == 'POST':
        platform_id = request.POST.get('platform_id')
        platform = get_object_or_404(Platform, pk=platform_id)
        
        if item.stock <= 0:
            messages.error(request, f"Out of stock: Cannot dispatch '{item.sku}'!")
            return redirect('scan_dispatch', sku=item.sku)

        item.stock -= 1
        item.save(update_fields=['stock', 'updated_at'])

        sold_price = price_map.get(platform.id, item.selling_price)
        DispatchLog.objects.create(
            sku=item,
            platform=platform,
            platform_name=platform.name,
            quantity=1,
            sold_price=sold_price,
            stock_after=item.stock
        )

        messages.success(request, f"✓ Dispatched 1 unit for {platform.name}! Stock left: {item.stock}")
        return redirect('scan_dispatch', sku=item.sku)

    platform_data = [{'platform': p, 'price': price_map.get(p.id, item.selling_price)} for p in platforms]
    recent_logs = item.dispatch_logs.all()[:5]

    return render(request, 'sku_manager/dispatch.html', {
        'item': item,
        'platforms': platform_data,
        'recent_logs': recent_logs,
    })

# 6. Label Printing View
def sku_print_label(request, pk):
    item = get_object_or_404(JewelrySKU.objects.select_related('storage_box'), pk=pk)
    dispatch_url = request.build_absolute_uri(reverse('scan_dispatch', args=[item.sku]))

    qr = qrcode.QRCode(version=1, box_size=6, border=1)
    qr.add_data(dispatch_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    return render(request, 'sku_manager/label_print.html', {
        'item': item,
        'qr_base64': qr_base64,
        'dispatch_url': dispatch_url,
    })

# Standard actions
def sku_scanner(request):
    return render(request, 'sku_manager/scanner.html', {'active_page': 'scanner'})

def sku_delete(request, pk):
    item = get_object_or_404(JewelrySKU, pk=pk)
    item.delete()
    messages.info(request, "SKU deleted.")
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

def platform_manager(request):
    get_or_seed_platforms()
    if request.method == 'POST':
        name = request.POST.get('platform_name', '').strip()
        if name:
            Platform.objects.get_or_create(name=name)
            messages.success(request, f"Platform '{name}' saved.")
        return redirect('platform_manager')
    platforms = Platform.objects.annotate(linked_products=Count('platformprice')).order_by('-id')
    return render(request, 'sku_manager/platforms.html', {'platforms': platforms, 'active_page': 'platforms'})

def platform_delete(request, pk):
    get_object_or_404(Platform, pk=pk).delete()
    return redirect('platform_manager')

def dispatch_logs(request):
    logs = DispatchLog.objects.select_related('sku').all()
    page = request.GET.get('page')
    page_logs = Paginator(logs, 20).get_page(page)
    return render(request, 'sku_manager/dispatch_logs.html', {
        'logs': page_logs,
        'total_dispatches': logs.count(),
        'active_page': 'dispatch_logs',
    })

def sku_qr_download(request, pk):
    item = get_object_or_404(JewelrySKU, pk=pk)
    dispatch_url = request.build_absolute_uri(reverse('scan_dispatch', args=[item.sku]))
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(dispatch_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    response = HttpResponse(buffer.getvalue(), content_type="image/png")
    response['Content-Disposition'] = f'attachment; filename="QR_{item.sku}.png"'
    return response

def export_csv(request):
    platforms = Platform.objects.all().order_by('id')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="jewelry_inventory.csv"'
    writer = csv.writer(response)
    headers = ['SKU', 'Category', 'Style', 'Name', 'Color', 'Size', 'Stock', 'Storage Box', 'Section', 'Cost', 'MRP']
    for p in platforms:
        headers.append(f"{p.name} Price")
    headers.extend(['Listed Status', 'Created At'])
    writer.writerow(headers)

    for obj in JewelrySKU.objects.select_related('storage_box').prefetch_related('platform_prices__platform').all():
        price_map = {pp.platform_id: pp.price for pp in obj.platform_prices.all()}
        row = [
            obj.sku, obj.category, obj.style, obj.name, obj.color, obj.size, obj.stock,
            obj.storage_box.name if obj.storage_box else 'Unassigned', obj.section_name,
            obj.purchase_price, obj.selling_price
        ]
        for p in platforms:
            row.append(price_map.get(p.id, ''))
        row.extend(['Listed' if obj.is_listed else 'Unlisted', obj.created_at.strftime("%Y-%m-%d %H:%M")])
        writer.writerow(row)
    return response