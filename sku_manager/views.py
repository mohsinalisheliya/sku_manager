# sku_manager/views.py
import csv
import io
import base64
import re
import qrcode
from datetime import datetime
from decimal import Decimal
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Count
from django.urls import reverse
from django.utils import timezone

from .models import JewelrySKU, Platform, PlatformPrice, StorageBox, StockBatch, DispatchLog, AppSettings

DEFAULT_PLATFORMS = ['Flipkart', 'Amazon', 'Meesho', 'Website']

def get_or_seed_platforms():
    if not Platform.objects.exists():
        for name in DEFAULT_PLATFORMS:
            Platform.objects.get_or_create(name=name)
    return Platform.objects.all().order_by('id')

def get_all_boxes():
    return StorageBox.objects.all().order_by('name')

def get_next_serial():
    last_item = JewelrySKU.objects.order_by('-id').first()
    if not last_item:
        return '001'
    try:
        parts = last_item.sku.split('-')
        last_num = int(parts[-1])
        return str(last_num + 1).zfill(3)
    except (ValueError, IndexError):
        return str(last_item.id + 1).zfill(3)

# --- Authentication Views ---
def user_login(request):
    if request.user.is_authenticated:
        return redirect('inventory_list')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            next_url = request.POST.get('next') or request.GET.get('next') or 'inventory_list'
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password. Please try again.")
    return render(request, 'sku_manager/login.html')

def user_logout(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('login')

# --- PART 1: Product Master (Add Form + Listing Table) ---

@login_required(login_url='login')
def product_master(request, pk=None):
    """
    Unified Product Studio: Handles both Add New Product & Edit Product Details
    """
    is_edit = pk is not None
    product = get_object_or_404(JewelrySKU, pk=pk) if is_edit else None

    if request.method == 'POST':
        category = request.POST.get('category', '').strip().upper()
        style = request.POST.get('style', '').strip().upper()
        name = request.POST.get('name', '').strip().upper()
        design_model = request.POST.get('design_model', '').strip()
        color = request.POST.get('color', '').strip().upper()
        size = request.POST.get('size', '').strip().upper()
        number = request.POST.get('number', '').strip()

        if not name:
            messages.error(request, "Product name is required.")
        else:
            if is_edit:
                # Update existing product
                product.category = category or product.category
                product.style = style or product.style
                product.name = name or product.name
                product.design_model = design_model
                product.color = color or product.color
                product.size = size or product.size
                if number:
                    product.number = number.zfill(3) if number.isdigit() and len(number) < 3 else number

                if request.FILES.get('image'):
                    product.image = request.FILES['image']

                product.save()
                messages.success(request, f"✓ Product '{product.sku}' updated successfully!")
                return redirect('product_list')
            else:
                # Create new product
                if not number:
                    number = get_next_serial()
                number = number.zfill(3) if number.isdigit() and len(number) < 3 else number

                new_product = JewelrySKU(
                    category=category or 'GEN',
                    style=style or 'STD',
                    name=name,
                    design_model=design_model,
                    color=color or 'BLK',
                    size=size or 'FREE',
                    number=number,
                    image=request.FILES.get('image'),
                    stock=0
                )
                new_product.save()
                messages.success(request, f"✓ Product created successfully! SKU: {new_product.sku}")
                return redirect('product_master')

    # Exclude current SKU from duplicate detection during edit
    if is_edit:
        existing_skus = list(JewelrySKU.objects.exclude(pk=pk).values_list('sku', flat=True))
    else:
        existing_skus = list(JewelrySKU.objects.values_list('sku', flat=True))

    products_count = JewelrySKU.objects.count()

    return render(request, 'sku_manager/products.html', {
        'is_edit': is_edit,
        'product': product,
        'existing_skus': existing_skus,
        'next_serial': product.number if is_edit else get_next_serial(),
        'products_count': products_count,
        'active_page': 'products',
    })


@login_required(login_url='login')
def product_edit_details(request, pk):
    product = get_object_or_404(JewelrySKU, pk=pk)

    if request.method == 'POST':
        product.category = request.POST.get('category', product.category).strip().upper()
        product.style = request.POST.get('style', product.style).strip().upper()
        product.name = request.POST.get('name', product.name).strip().upper()
        product.design_model = request.POST.get('design_model', '').strip()
        product.color = request.POST.get('color', product.color).strip().upper()
        product.size = request.POST.get('size', product.size).strip().upper()
        product.number = request.POST.get('number', product.number).strip() or product.number

        if request.FILES.get('image'):
            product.image = request.FILES['image']

        product.save()
        messages.success(request, f"✓ Details updated for {product.sku}!")
        return redirect('product_master')

    existing_skus = list(JewelrySKU.objects.exclude(pk=pk).values_list('sku', flat=True))

    return render(request, 'sku_manager/product_edit.html', {
        'product': product,
        'existing_skus': existing_skus,
        'active_page': 'products',
    })


@login_required(login_url='login')
def product_list_view(request):
    """Product Listing with Search & Server-Side Pagination"""
    search_query = request.GET.get('q', '').strip()
    limit_raw = request.GET.get('limit', '10')

    try:
        limit = int(limit_raw)
    except (ValueError, TypeError):
        limit = 10
    limit = max(5, min(limit, 100))

    products = JewelrySKU.objects.all().order_by('-created_at')

    if search_query:
        products = products.filter(
            Q(sku__icontains=search_query) |
            Q(name__icontains=search_query) |
            Q(category__icontains=search_query) |
            Q(style__icontains=search_query) |
            Q(color__icontains=search_query) |
            Q(design_model__icontains=search_query)
        )

    total_count = products.count()
    paginator = Paginator(products, limit)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'sku_manager/product_list.html', {
        'products': page_obj,
        'page_obj': page_obj,
        'search_query': search_query,
        'limit': limit,
        'total_count': total_count,
        'active_page': 'products',
    })

@login_required(login_url='login')
def product_delete_secure(request, pk):
    """Delete a product only after confirming the current user's password."""
    product = get_object_or_404(JewelrySKU, pk=pk)

    if request.method == 'POST':
        entered_password = request.POST.get('delete_password', '').strip()
        if request.user.check_password(entered_password):
            sku_name = product.sku
            product.delete()
            messages.success(request, f"Product '{sku_name}' was permanently deleted.")
        else:
            messages.error(request, 'Access denied: incorrect password. Product was not deleted.')

    return redirect('product_list')

# --- PART 2: Inventory List (FIXES EMPTY TABLE) ---
@login_required(login_url='login')
def inventory_list(request):
    threshold = AppSettings.get_settings().low_stock_threshold

    for sku in JewelrySKU.objects.all():
        sku.sync_stock_from_batches()

    items = (JewelrySKU.objects.select_related('storage_box')
             .annotate(total_batches=Count('batches', distinct=True),
                       active_batches=Count('batches', filter=Q(batches__status='active'), distinct=True))
             .order_by('-id'))

    out_count = items.filter(stock=0).count()
    low_count = items.filter(stock__gt=0, stock__lte=threshold).count()
    ok_count = items.filter(stock__gt=threshold).count()

    return render(request, 'sku_manager/inventory.html', {
        'items': items,
        'total_count': out_count + low_count + ok_count,
        'out_count': out_count,
        'low_count': low_count,
        'ok_count': ok_count,
        'threshold': threshold,
        'active_page': 'inventory',
    })

sku_inventory = inventory_list

# --- PART 2: Add / Edit Stock (Same Page for Both) ---
@login_required(login_url='login')
def stock_action(request, pk):
    item = get_object_or_404(JewelrySKU, pk=pk)
    item.sync_stock_from_batches()

    platforms = get_or_seed_platforms()
    boxes = get_all_boxes()
    active_batches = item.batches.filter(status='active').order_by('-created_at')

    batch_id_to_edit = request.GET.get('edit_batch')
    selected_batch = item.batches.filter(pk=batch_id_to_edit).first() if batch_id_to_edit else None
    is_edit = selected_batch is not None

    if request.method == 'POST':
        action_mode = request.POST.get('action_mode', 'new_batch')
        batch_no = request.POST.get('batch_no', '').strip() or f"BAT-{datetime.now().strftime('%y%m%d%H%M')}"
        stock_raw = request.POST.get('stock_qty', '0').strip()
        stock_qty = int(stock_raw) if stock_raw.isdigit() else 0

        p_cost = request.POST.get('purchase_price', '0').strip()
        s_price = request.POST.get('selling_price', '0').strip()
        purchase_price = Decimal(p_cost) if p_cost else Decimal('0.00')
        selling_price = Decimal(s_price) if s_price else Decimal('0.00')

        box_choice = request.POST.get('box_choice', 'previous')
        storage_box = None
        if box_choice == 'new':
            new_box_name = request.POST.get('new_box_name', '').strip()
            if new_box_name:
                storage_box, _ = StorageBox.objects.get_or_create(
                    name=new_box_name,
                    defaults={'color_tag': request.POST.get('new_box_color', '#3B82F6').strip()}
                )
        else:
            box_id = request.POST.get('existing_box_id', '').strip()
            storage_box = StorageBox.objects.filter(pk=box_id).first() if box_id else None

        section_name = request.POST.get('section_name', '').strip() or 'Main Compartment'

        with transaction.atomic():
            if action_mode == 'edit_batch' and selected_batch:
                selected_batch.batch_no = batch_no
                selected_batch.quantity = stock_qty
                selected_batch.purchase_price = purchase_price
                selected_batch.selling_price = selling_price
                selected_batch.storage_box = storage_box
                selected_batch.section_name = section_name
                if stock_qty > 0:
                    selected_batch.status = 'active'
                    selected_batch.finished_at = None
                else:
                    selected_batch.status = 'disabled'
                    selected_batch.finished_at = timezone.now()
                selected_batch.save()
                messages.success(request, f"Batch '{batch_no}' updated! Units: {stock_qty}")
            else:
                StockBatch.objects.create(
                    sku=item,
                    batch_no=batch_no,
                    quantity=stock_qty,
                    purchase_price=purchase_price,
                    selling_price=selling_price,
                    storage_box=storage_box,
                    section_name=section_name,
                    status='active' if stock_qty > 0 else 'disabled',
                    finished_at=timezone.now() if stock_qty == 0 else None,
                )
                messages.success(request, f"Added new Batch '{batch_no}' with {stock_qty} units!")

            for platform in platforms:
                p_val = request.POST.get(f'platform_price_{platform.id}', '').strip()
                if p_val:
                    PlatformPrice.objects.update_or_create(
                        sku=item,
                        platform=platform,
                        defaults={'price': Decimal(p_val)},
                    )
                else:
                    PlatformPrice.objects.filter(sku=item, platform=platform).delete()

            item.sync_stock_from_batches()
        return redirect('inventory_list')

    current_prices = {pp.platform_id: pp.price for pp in item.platform_prices.all()}

    return render(request, 'sku_manager/stock_action.html', {
        'item': item,
        'platforms': platforms,
        'boxes': boxes,
        'selected_batch': selected_batch,
        'active_batches': active_batches,
        'all_batches_count': item.batches.count(),
        'current_prices': current_prices,
        'suggested_batch': f"BAT-{datetime.now().strftime('%y%m%d%H%M')}",
        'is_edit': is_edit,
        'active_page': 'inventory',
    })


@login_required(login_url='login')
def product_batches_view(request, pk):
    item = get_object_or_404(JewelrySKU, pk=pk)
    item.sync_stock_from_batches()

    batches = item.batches.select_related('storage_box').order_by('-created_at')
    active_units = sum(batch.quantity for batch in batches if batch.status == 'active')
    platforms = get_or_seed_platforms()
    platform_prices = {price.platform_id: price.price for price in item.platform_prices.all()}

    return render(request, 'sku_manager/product_batches.html', {
        'item': item,
        'product': item,
        'batches': batches,
        'active_units': active_units,
        'total_batches': batches.count(),
        'boxes': get_all_boxes(),
        'platforms': platforms,
        'platform_prices': platform_prices,
        'suggested_batch': f"BAT-{datetime.now().strftime('%y%m%d-%H%M')}",
        'active_page': 'inventory',
    })


@login_required(login_url='login')
def update_universal_threshold(request):
    if request.method == 'POST':
        raw_threshold = request.POST.get('low_stock_threshold', '').strip()
        if raw_threshold.isdigit() and int(raw_threshold) >= 1:
            settings_obj = AppSettings.get_settings()
            settings_obj.low_stock_threshold = int(raw_threshold)
            settings_obj.save(update_fields=['low_stock_threshold', 'updated_at'])
            messages.success(request, 'Low-stock threshold updated.')
        else:
            messages.error(request, 'Enter a whole-number threshold of at least 1.')
    return redirect('inventory_list')


@login_required(login_url='login')
def toggle_product_status(request, pk):
    product = get_object_or_404(JewelrySKU, pk=pk)
    if request.method == 'POST':
        product.is_listed = not product.is_listed
        product.save(update_fields=['is_listed', 'updated_at'])
        messages.success(request, f"Sales status updated for {product.sku}.")
    return redirect('product_batches', pk=product.pk)


@login_required(login_url='login')
def delete_batch(request, batch_id):
    batch = get_object_or_404(StockBatch.objects.select_related('sku'), pk=batch_id)
    product_id = batch.sku_id
    if request.method == 'POST':
        batch.delete()
        messages.success(request, 'Batch deleted.')
    return redirect('product_batches', pk=product_id)


@login_required(login_url='login')
def last_stock_api(request, pk):
    item = get_object_or_404(JewelrySKU, pk=pk)
    item.sync_stock_from_batches()
    return JsonResponse({'stock': item.stock})


# --- Storage Units & Platforms ---
@login_required(login_url='login')
def box_manager(request):
    existing_boxes = StorageBox.objects.annotate(total_skus=Count('skus')).order_by('name')
    if request.method == 'POST':
        name = request.POST.get('box_name', '').strip()
        color_tag = request.POST.get('color_tag', '#3B82F6').strip().upper()
        description = request.POST.get('description', '').strip()
        if name:
            StorageBox.objects.get_or_create(name=name, defaults={'color_tag': color_tag, 'description': description})
            messages.success(request, f"Storage unit '{name}' created!")
            return redirect('box_manager')

    return render(request, 'sku_manager/boxes.html', {
        'boxes': existing_boxes,
        'color_swatches': [],
        'used_colors_map': {},
        'active_page': 'boxes',
    })

def box_delete(request, pk):
    box = get_object_or_404(StorageBox, pk=pk)
    name = box.name
    box.delete()
    messages.info(request, f"Box '{name}' deleted.")
    return redirect('box_manager')

@login_required(login_url='login')
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

# --- Dispatch, Scanner & Label Print ---
def scan_dispatch(request, sku):
    item = get_object_or_404(JewelrySKU.objects.select_related('storage_box'), sku=sku)
    item.sync_stock_from_batches()
    platforms = get_or_seed_platforms()
    price_map = {pp.platform_id: pp.price for pp in item.platform_prices.all()}

    if request.method == 'POST':
        platform_id = request.POST.get('platform_id')
        platform = get_object_or_404(Platform, pk=platform_id)

        if item.stock <= 0:
            messages.error(request, f"Out of stock: Cannot dispatch '{item.sku}'!")
            return redirect('scan_dispatch', sku=item.sku)

        with transaction.atomic():
            active_batch = item.batches.select_for_update().filter(
                status='active', quantity__gt=0
            ).order_by('created_at').first()
            if not active_batch:
                item.sync_stock_from_batches()
                messages.error(request, f"Out of stock: Cannot dispatch '{item.sku}'!")
                return redirect('scan_dispatch', sku=item.sku)

            active_batch.quantity -= 1
            if active_batch.quantity == 0:
                active_batch.status = 'disabled'
                active_batch.finished_at = timezone.now()
            active_batch.save()
            item.sync_stock_from_batches()

        sold_price = price_map.get(platform.id, item.selling_price)
        DispatchLog.objects.create(
            sku=item,
            platform=platform,
            platform_name=platform.name,
            quantity=1,
            sold_price=sold_price,
            stock_after=item.stock
        )
        messages.success(request, f"Dispatched 1 unit for {platform.name}! Stock left: {item.stock}")
        return redirect('scan_dispatch', sku=item.sku)

    platform_data = [{'platform': p, 'price': price_map.get(p.id, item.selling_price)} for p in platforms]
    recent_logs = item.dispatch_logs.all()[:5]

    return render(request, 'sku_manager/dispatch.html', {
        'item': item,
        'platforms': platform_data,
        'recent_logs': recent_logs,
    })

def sku_print_label(request, pk):
    item = get_object_or_404(JewelrySKU.objects.select_related('storage_box'), pk=pk)
    dispatch_url = request.build_absolute_uri(reverse('scan_dispatch', args=[item.sku]))
    settings_obj = AppSettings.get_settings()

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
        'settings': settings_obj,
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

@login_required(login_url='login')
def sku_scanner(request):
    return render(request, 'sku_manager/scanner.html', {'active_page': 'scanner'})

@login_required(login_url='login')
def dispatch_logs(request):
    logs = DispatchLog.objects.select_related('sku').all()
    return render(request, 'sku_manager/dispatch_logs.html', {
        'logs': logs,
        'total_dispatches': logs.count(),
        'active_page': 'dispatch_logs',
    })

@login_required(login_url='login')
def export_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="inventory_stock.csv"'
    writer = csv.writer(response)
    writer.writerow(['SKU', 'Name', 'Category', 'Style', 'Color', 'Size', 'Stock', 'Box', 'Compartment', 'Purchase Price', 'MRP'])

    for obj in JewelrySKU.objects.select_related('storage_box').all():
        box_name = obj.storage_box.name if obj.storage_box else 'Unassigned'
        writer.writerow([
            obj.sku, obj.name, obj.category, obj.style, obj.color, obj.size,
            obj.stock, box_name, obj.section_name, obj.purchase_price, obj.selling_price
        ])
    return response

@login_required(login_url='login')
def app_settings_view(request):
    settings_obj = AppSettings.get_settings()
    if request.method == 'POST':
        settings_obj.brand_name = request.POST.get('brand_name', '').strip() or 'TATKAL PICK'
        settings_obj.tagline = request.POST.get('tagline', '').strip()
        settings_obj.currency_symbol = request.POST.get('currency_symbol', '₹').strip()
        threshold = request.POST.get('low_stock_threshold', '5').strip()
        settings_obj.low_stock_threshold = int(threshold) if threshold.isdigit() else 5
        settings_obj.support_contact = request.POST.get('support_contact', '').strip()
        settings_obj.save()
        messages.success(request, "Settings updated successfully!")
        return redirect('app_settings')

    return render(request, 'sku_manager/settings.html', {
        'settings': settings_obj,
        'active_page': 'settings',
    })