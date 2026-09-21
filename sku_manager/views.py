import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.db.models import Q
from .models import JewelrySKU

def get_next_serial():
    latest = JewelrySKU.objects.order_by('-id').first()
    if not latest:
        return '001'
    try:
        return str(int(latest.number) + 1).zfill(3)
    except (ValueError, TypeError):
        return '001'

def sku_dashboard(request):
    search_query = request.GET.get('q', '').strip()
    skus = JewelrySKU.objects.all()

    if search_query:
        skus = skus.filter(
            Q(sku__icontains=search_query) |
            Q(name__icontains=search_query) |
            Q(style__icontains=search_query) |
            Q(category__icontains=search_query)
        )

    if request.method == 'POST':
        category = request.POST.get('category', '').strip()
        style = request.POST.get('style', '').strip()
        name = request.POST.get('name', '').strip()
        color = request.POST.get('color', '').strip()
        size = request.POST.get('size', '').strip()
        number = request.POST.get('number', '').strip()
        stock = request.POST.get('stock', 1)
        image = request.FILES.get('image')

        try:
            item = JewelrySKU(
                category=category,
                style=style,
                name=name,
                color=color,
                size=size,
                number=number,
                stock=int(stock) if str(stock).isdigit() else 0,
                image=image
            )
            item.save()
            messages.success(request, f"SKU '{item.sku}' successfully added with stock {item.stock}!")
            return redirect('sku_dashboard')
        except Exception as e:
            messages.error(request, f"Error saving SKU: {e}")

    return render(request, 'sku_manager/index.html', {
        'skus': skus,
        'search_query': search_query,
        'is_edit': False,
        'next_serial': get_next_serial(),
    })

def sku_edit(request, pk):
    item = get_object_or_404(JewelrySKU, pk=pk)
    
    if request.method == 'POST':
        item.category = request.POST.get('category', '').strip()
        item.style = request.POST.get('style', '').strip()
        item.name = request.POST.get('name', '').strip()
        item.color = request.POST.get('color', '').strip()
        item.size = request.POST.get('size', '').strip()
        item.number = request.POST.get('number', '').strip()
        
        stock_val = request.POST.get('stock', item.stock)
        item.stock = int(stock_val) if str(stock_val).isdigit() else item.stock

        if request.FILES.get('image'):
            item.image = request.FILES.get('image')

        try:
            item.save()
            messages.success(request, f"SKU updated to '{item.sku}'!")
            return redirect('sku_dashboard')
        except Exception as e:
            messages.error(request, f"Error updating SKU: {e}")

    skus = JewelrySKU.objects.all()
    return render(request, 'sku_manager/index.html', {
        'skus': skus,
        'is_edit': True,
        'edit_item': item,
    })

def toggle_listed(request, pk):
    item = get_object_or_404(JewelrySKU, pk=pk)
    item.is_listed = not item.is_listed
    item.save(update_fields=['is_listed', 'updated_at'])
    status = "Listed" if item.is_listed else "Unlisted"
    messages.success(request, f"SKU '{item.sku}' marked as {status}.")
    return redirect(request.META.get('HTTP_REFERER', 'sku_dashboard'))

def stock_adjust(request, pk, action):
    item = get_object_or_404(JewelrySKU, pk=pk)
    if action == 'inc':
        item.stock += 1
    elif action == 'dec' and item.stock > 0:
        item.stock -= 1
    item.save(update_fields=['stock', 'updated_at'])
    return redirect(request.META.get('HTTP_REFERER', 'sku_dashboard'))

def sku_delete(request, pk):
    item = get_object_or_404(JewelrySKU, pk=pk)
    sku_val = item.sku
    item.delete()
    messages.info(request, f"SKU '{sku_val}' deleted.")
    return redirect('sku_dashboard')

def export_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="jewelry_skus.csv"'

    writer = csv.writer(response)
    writer.writerow(['SKU', 'Category', 'Style', 'Name', 'Color', 'Size', 'Stock', 'Listed', 'Created At'])

    for obj in JewelrySKU.objects.all():
        writer.writerow([
            obj.sku, obj.category, obj.style, obj.name,
            obj.color, obj.size, obj.stock,
            'Yes' if obj.is_listed else 'No',
            obj.created_at.strftime("%Y-%m-%d %H:%M")
        ])

    return response