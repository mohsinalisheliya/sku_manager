# sku_manager/views.py
import csv
import io
import base64
import re
import qrcode
from datetime import datetime
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse
from .models import JewelrySKU, Platform, PlatformPrice, DispatchLog, StorageBox, StockBatch, AppSettings


# sku_manager/views.py ke top imports me add karein:
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

# --- Authentication Views ---

def user_login(request):
    """Clean dark-themed login without forms.py"""
    if request.user.is_authenticated:
        return redirect('sku_generate')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            next_url = request.POST.get('next') or request.GET.get('next') or 'sku_generate'
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password. Please try again.")

    return render(request, 'sku_manager/login.html')

def user_logout(request):
    """Logout action"""
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('login')


DEFAULT_PLATFORMS = ['Flipkart', 'Amazon', 'Meesho', 'Website']
PRESET_COLORS = [
    # Reds & Crimsons
    '#EF4444', '#DC2626', '#B91C1C', '#991B1B',
    # Rose & Pink
    '#F43F5E', '#E11D48', '#BE123C', '#EC4899', '#DB2777', '#BE185D',
    # Corals & Oranges
    '#FB923C', '#F97316', '#EA580C', '#C2410C',
    # Ambers & Gold
    '#FBBF24', '#F59E0B', '#D97706', '#B45309',
    # Yellows & Brass
    '#FDE047', '#EAB308', '#CA8A04', '#A16207',
    # Limes & Olive
    '#A3E635', '#84CC16', '#65A30D', '#4D7C0F',
    # Greens & Emerald
    '#4ADE80', '#22C55E', '#16A34A', '#15803D', '#10B981', '#059669', '#047857',
    # Teals & Aquas
    '#2DD4BF', '#14B8A6', '#0D9488', '#0F766E', '#06B6D4', '#0891B2', '#0E7490',
    # Blues & Cobalt
    '#38BDF8', '#0EA5E9', '#0284C7', '#3B82F6', '#2563EB', '#1D4ED8',
    # Indigos & Violets
    '#818CF8', '#6366F1', '#4F46E5', '#8B5CF6', '#7C3AED', '#6D28D9',
    # Purples & Magentas
    '#C084FC', '#A855F7', '#9333EA', '#E879F9', '#D946EF', '#C026D3',
]

def get_or_seed_platforms():
    if not Platform.objects.exists():
        for name in DEFAULT_PLATFORMS:
            Platform.objects.get_or_create(name=name)
    return Platform.objects.all().order_by('id')

def get_all_boxes():
    """Fetch only user-created storage boxes without auto-seeding defaults."""
    return StorageBox.objects.all().order_by('name')

def get_next_serial():
    latest = JewelrySKU.objects.order_by('-id').first()
    if not latest:
        return '001'
    try:
        return str(int(latest.number) + 1).zfill(3)
    except (ValueError, TypeError):
        return '001'


# Separate product registration from stock inwarding.
@login_required(login_url='login')
def product_create(request):
    if request.method == 'POST':
        try:
            item = JewelrySKU(
                category=request.POST.get('category', '').strip() or 'GEN',
                style=request.POST.get('style', '').strip() or 'STD',
                name=request.POST.get('name', '').strip() or 'ITEM',
                color=request.POST.get('color', '').strip() or 'BLK',
                size=request.POST.get('size', '').strip() or 'FREE',
                number=request.POST.get('number', '').strip() or '001',
                image=request.FILES.get('image'),
                stock=0,
            )
            item.save()
            messages.success(request, f"Product registered with SKU '{item.sku}'. Now inward stock below.")
            return redirect(f"{reverse('stock_inward')}?sku_id={item.pk}")
        except Exception as exc:
            messages.error(request, f"Error saving product: {exc}")

    return render(request, 'sku_manager/product_create.html', {
        'existing_skus': list(JewelrySKU.objects.values_list('sku', flat=True)),
        'next_serial': get_next_serial(),
        'active_page': 'product_create',
    })


@login_required(login_url='login')
def stock_inward(request):
    platforms = get_or_seed_platforms()
    boxes = get_all_boxes()
    products = JewelrySKU.objects.all().order_by('-created_at')
    preselected_sku_id = request.GET.get('sku_id', '')

    if request.method == 'POST':
        item = get_object_or_404(JewelrySKU, pk=request.POST.get('sku_id'))
        batch_no = request.POST.get('batch_no', '').strip() or f"BAT-{datetime.now().strftime('%y%m%d-%H%M')}"
        quantity_raw = request.POST.get('quantity', '1').strip()

        try:
            quantity = int(quantity_raw)
            if quantity < 1:
                raise ValueError
            purchase_price = Decimal(request.POST.get('purchase_price', '0').strip() or '0')
            selling_price = Decimal(request.POST.get('selling_price', '0').strip() or '0')
            if purchase_price < 0 or selling_price < 0:
                raise ValueError
            platform_prices = {}
            for platform in platforms:
                price_raw = request.POST.get(f'platform_price_{platform.id}', '').strip()
                if price_raw:
                    price = Decimal(price_raw)
                    if price < 0:
                        raise ValueError
                    platform_prices[platform] = price
        except (ValueError, InvalidOperation):
            messages.error(request, 'Enter a whole quantity of at least 1 and valid, non-negative prices.')
            return redirect(f"{reverse('stock_inward')}?sku_id={item.pk}")

        section_name = request.POST.get('section_name', '').strip() or 'Main Section'
        storage_box = None
        if request.POST.get('box_choice_type', 'previous') == 'new':
            new_box_name = request.POST.get('new_box_name', '').strip()
            new_box_color = request.POST.get('new_box_color', '#F59E0B').strip().upper()
            if new_box_name:
                storage_box, _ = StorageBox.objects.get_or_create(
                    name=new_box_name,
                    defaults={'color_tag': new_box_color},
                )
        else:
            previous_box_id = request.POST.get('existing_box_id')
            if previous_box_id:
                storage_box = StorageBox.objects.filter(pk=previous_box_id).first()

        with transaction.atomic():
            item.stock += quantity
            item.batch_no = batch_no
            item.purchase_price = purchase_price
            item.selling_price = selling_price
            if storage_box:
                item.storage_box = storage_box
            item.section_name = section_name
            item.save()

            StockBatch.objects.create(
                sku=item,
                batch_no=batch_no,
                quantity=quantity,
                purchase_price=purchase_price,
                selling_price=selling_price,
                storage_box=storage_box,
                section_name=section_name,
            )

            for platform, price in platform_prices.items():
                PlatformPrice.objects.update_or_create(
                    sku=item,
                    platform=platform,
                    defaults={'price': price},
                )

        box_name = storage_box.name if storage_box else 'No Box'
        messages.success(request, f"Added {quantity} units to '{item.sku}' (Batch: {batch_no}). Location: {box_name} -> {section_name}")
        return redirect('sku_inventory')

    return render(request, 'sku_manager/stock_inward.html', {
        'products': products,
        'platforms': platforms,
        'boxes': boxes,
        'preselected_sku_id': preselected_sku_id,
        'suggested_batch': f"BAT-{datetime.now().strftime('%y%m%d-%H%M')}",
        'active_page': 'stock_inward',
    })

# 1. Box Management Page
@login_required(login_url='login')
def box_manager(request):
    """Manage custom storage boxes with unique names and colors."""
    existing_boxes = StorageBox.objects.annotate(total_skus=Count('skus')).order_by('name')
    used_colors_map = {b.color_tag.upper(): b.name for b in existing_boxes if b.color_tag}

    if request.method == 'POST':
        name = request.POST.get('box_name', '').strip()
        color_tag = request.POST.get('color_tag', '').strip().upper()
        description = request.POST.get('description', '').strip()

        if color_tag and not color_tag.startswith('#'):
            color_tag = f"#{color_tag}"

        if not name:
            messages.error(request, "Box name cannot be empty.")
            return redirect('box_manager')

        if StorageBox.objects.filter(name__iexact=name).exists():
            messages.error(request, f"Error: A storage box named '{name}' already exists! Box names must be unique.")
            return redirect('box_manager')

        if color_tag in used_colors_map:
            messages.error(request, f"Error: Color {color_tag} is already assigned to '{used_colors_map[color_tag]}'! Please pick another color.")
            return redirect('box_manager')

        StorageBox.objects.create(
            name=name,
            color_tag=color_tag or '#F59E0B',
            description=description,
        )
        messages.success(request, f"Storage box '{name}' successfully created!")
        return redirect('box_manager')

    color_swatches = []
    for color in PRESET_COLORS:
        c_upper = color.upper()
        color_swatches.append({
            'hex': c_upper,
            'is_taken': c_upper in used_colors_map,
            'used_by': used_colors_map.get(c_upper, ''),
        })

    return render(request, 'sku_manager/boxes.html', {
        'boxes': existing_boxes,
        'color_swatches': color_swatches,
        'used_colors_map': used_colors_map,
        'active_page': 'boxes',
    })

def box_delete(request, pk):
    box = get_object_or_404(StorageBox, pk=pk)
    name = box.name
    box.delete()
    messages.info(request, f"Storage box '{name}' deleted. Associated products are now unassigned.")
    return redirect('box_manager')

# 2. SKU Generator
@login_required(login_url='login')
def sku_generate(request):
    platforms = get_or_seed_platforms()
    boxes = get_all_boxes()

    if request.method == 'POST':
        category = request.POST.get('category', '').strip()
        style = request.POST.get('style', '').strip()
        name = request.POST.get('name', '').strip()
        color = request.POST.get('color', '').strip()
        size = request.POST.get('size', '').strip()
        number = request.POST.get('number', '').strip()
        stock = request.POST.get('stock', '').strip()
        purchase_price = request.POST.get('purchase_price', '').strip()
        selling_price = request.POST.get('selling_price', '').strip()
        box_id = request.POST.get('storage_box', '').strip()
        section_name = request.POST.get('section_name', '').strip()
        image = request.FILES.get('image')

        storage_box = StorageBox.objects.filter(pk=box_id).first() if box_id else None

        try:
            item = JewelrySKU(
                category=category or 'UNC',
                style=style or 'STD',
                name=name or 'ITEM',
                color=color or 'GLD',
                size=size or 'FREE',
                number=number or '001',
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
@login_required(login_url='login')
def sku_inventory(request):
    search_query = request.GET.get('q', '').strip()
    filter_status = request.GET.get('status', '').strip()
    filter_box = request.GET.get('box', '').strip()
    platforms = get_or_seed_platforms()
    boxes = get_all_boxes()
    
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
@login_required(login_url='login')
def sku_edit(request, pk):
    item = get_object_or_404(JewelrySKU, pk=pk)
    platforms = get_or_seed_platforms()
    boxes = get_all_boxes()

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

# Standard actions
@login_required(login_url='login')
def sku_scanner(request):
    return render(request, 'sku_manager/scanner.html', {'active_page': 'scanner'})

@login_required(login_url='login')
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

@login_required(login_url='login')
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

@login_required(login_url='login')
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

@login_required(login_url='login')
def app_settings_view(request):
    """Database-driven System Settings View"""
    settings_obj = AppSettings.get_settings()

    if request.method == 'POST':
        brand_name = request.POST.get('brand_name', '').strip()
        tagline = request.POST.get('tagline', '').strip()
        currency_symbol = request.POST.get('currency_symbol', '₹').strip()
        low_stock = request.POST.get('low_stock_threshold', '5').strip()
        support_contact = request.POST.get('support_contact', '').strip()

        settings_obj.brand_name = brand_name or 'TATKAL PICK'
        settings_obj.tagline = tagline
        settings_obj.currency_symbol = currency_symbol or '₹'
        settings_obj.low_stock_threshold = int(low_stock) if low_stock.isdigit() else 5
        settings_obj.support_contact = support_contact
        settings_obj.save()

        messages.success(request, "Settings updated successfully!")
        return redirect('app_settings')

    return render(request, 'sku_manager/settings.html', {
        'settings': settings_obj,
        'active_page': 'settings',
    })