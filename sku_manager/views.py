# sku_manager/views.py
import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import JewelrySKU

def get_next_serial():
    latest = JewelrySKU.objects.order_by('-id').first()
    if not latest:
        return '001'
    try:
        return str(int(latest.number) + 1).zfill(3)
    except (ValueError, TypeError):
        return '001'

# Page 1: SKU Generator Form
def sku_generate(request):
    if request.method == 'POST':
        category = request.POST.get('category', '').strip()
        style = request.POST.get('style', '').strip()
        name = request.POST.get('name', '').strip()
        color = request.POST.get('color', '').strip()
        size = request.POST.get('size', '').strip()
        number = request.POST.get('number', '').strip()
        stock = request.POST.get('stock', '0').strip()
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
                image=image
            )
            item.save()
            messages.success(request, f"SKU '{item.sku}' generated and saved!")
            return redirect('sku_inventory')
        except Exception as e:
            messages.error(request, f"Error saving SKU: {str(e)}")

    existing_skus = list(JewelrySKU.objects.values_list('sku', flat=True))
    return render(request, 'sku_manager/generator.html', {
        'is_edit': False,
        'next_serial': get_next_serial(),
        'existing_skus': existing_skus,
        'active_page': 'generator',
    })

# Page 2: Dedicated Inventory & Data View (with Pagination)
def sku_inventory(request):
    search_query = request.GET.get('q', '').strip()
    filter_status = request.GET.get('status', '').strip()
    
    sku_list = JewelrySKU.objects.all()

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

    # 10 items per page
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
        'search_query': search_query,
        'filter_status': filter_status,
        'total_count': sku_list.count(),
        'active_page': 'inventory',
    })

# Edit Record
def sku_edit(request, pk):
    item = get_object_or_404(JewelrySKU, pk=pk)

    if request.method == 'POST':
        item.category = request.POST.get('category', '').strip()
        item.style = request.POST.get('style', '').strip()
        item.name = request.POST.get('name', '').strip()
        item.color = request.POST.get('color', '').strip()
        item.size = request.POST.get('size', '').strip()
        item.number = request.POST.get('number', '').strip()
        
        stock_val = request.POST.get('stock', '0').strip()
        item.stock = int(stock_val) if stock_val.isdigit() else 0

        if 'image' in request.FILES:
            item.image = request.FILES['image']

        try:
            item.save()
            messages.success(request, f"SKU updated to '{item.sku}'!")
            return redirect('sku_inventory')
        except Exception as e:
            messages.error(request, f"Error updating SKU: {str(e)}")

    existing_skus = list(JewelrySKU.objects.exclude(pk=pk).values_list('sku', flat=True))
    return render(request, 'sku_manager/generator.html', {
        'is_edit': True,
        'edit_item': item,
        'existing_skus': existing_skus,
        'active_page': 'generator',
    })

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

# sku_manager/views.py

def adjust_stock(request, pk, action):
    item = get_object_or_404(JewelrySKU, pk=pk)
    if action == 'dec':
        item.stock = max(0, item.stock - 1)
    elif action == 'inc':
        item.stock += 1
        
    item.save(update_fields=['stock', 'updated_at'])
    return redirect(request.META.get('HTTP_REFERER', 'sku_inventory'))

def export_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="jewelry_inventory.csv"'

    writer = csv.writer(response)
    writer.writerow(['SKU', 'Category', 'Style', 'Name', 'Color', 'Size', 'Stock', 'Listed Status', 'Created At'])

    for obj in JewelrySKU.objects.all():
        writer.writerow([
            obj.sku, obj.category, obj.style, obj.name,
            obj.color, obj.size, obj.stock,
            'Listed' if obj.is_listed else 'Unlisted',
            obj.created_at.strftime("%Y-%m-%d %H:%M")
        ])

    return response