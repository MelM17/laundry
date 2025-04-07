from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.urls import reverse
import csv
import io
import xlsxwriter
from datetime import datetime, timedelta
import logging
from customer.models import User, Launderer, ClothItem, ClothType, Order, OrderItem, CustomerSupport, Review
from .models import LaundererService, LaundererWorkingHour, LaundererPaymentMethod, LaundererOrderStatus, Notification
from .forms import (LaundererRegistrationForm, LaundererLoginForm, ClothItemForm, LaundererServiceForm,
                   LaundererWorkingHourForm, LaundererPaymentMethodForm, OrderStatusUpdateForm,
                   LaundererProfileForm, LaundererSupportForm)


# Set up logger
logger = logging.getLogger(__name__)

# Add this debugging function at the top of the file after imports
def debug_orders(launderer):
    """Debug function to check orders in the database"""
    logger = logging.getLogger(__name__)
    
    # Check all orders for this launderer
    all_orders = Order.objects.filter(launderer=launderer)
    logger.info(f"Total orders for launderer {launderer.business_name}: {all_orders.count()}")
    
    # Check orders by status
    for status, _ in Order.STATUS_CHOICES:
        count = Order.objects.filter(launderer=launderer, status=status).count()
        logger.info(f"Orders with status '{status}': {count}")
    
    # Check specifically for pending_acceptance orders
    pending_orders = Order.objects.filter(launderer=launderer, status='pending_acceptance')
    logger.info(f"Pending acceptance orders: {pending_orders.count()}")
    for order in pending_orders:
        logger.info(f"Order ID: {order.order_id}, Customer: {order.customer.username}, Created: {order.created_at}")
    
    return pending_orders

# Helper function to check if user is launderer
def is_launderer(user):
    return user.is_authenticated and user.user_type == 'launderer'

def launderer_register(request):
    if request.user.is_authenticated:
        if request.user.user_type == 'launderer':
            return redirect('launderer:dashboard')
        else:
            logout(request)
    
    if request.method == 'POST':
        form = LaundererRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Registration successful! Your account is pending verification by admin.")
            return redirect('launderer:login')
        else:
            messages.error(request, "Registration failed. Please correct the errors below.")
    else:
        form = LaundererRegistrationForm()
    
    return render(request, 'launderer/register.html', {'form': form})

def launderer_login(request):
    if request.user.is_authenticated:
        if request.user.user_type == 'customer':
            return redirect('customer:home')
        elif request.user.user_type == 'launderer':
            return redirect('launderer:dashboard')
        elif request.user.user_type == 'admin':
            return redirect('admin_portal:dashboard')
    
    if request.method == 'POST':
        form = LaundererLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None and user.user_type == 'launderer':
                login(request, user)
                
                # Check if launderer is verified
                if not user.launderer_profile.is_verified:
                    messages.warning(request, "Your account is pending verification by admin.")
                
                return redirect('launderer:dashboard')
            else:
                messages.error(request, 'Invalid username or password or insufficient permissions.')
        else:
            messages.error(request, 'Invalid username or password or insufficient permissions.')
    else:
        form = LaundererLoginForm()
    
    return render(request, 'launderer/login.html', {'form': form})

@login_required
@user_passes_test(is_launderer)
def launderer_logout(request):
    logout(request)
    return redirect('launderer:login')

@login_required
@user_passes_test(is_launderer)
def dashboard(request):
    if not request.user.is_authenticated:
        return redirect('launderer:login')
    
    # Get order counts for different statuses
    pending_acceptance_orders = Order.objects.filter(launderer=request.user.launderer_profile, status='pending_acceptance').count()
    confirmed_orders = Order.objects.filter(launderer=request.user.launderer_profile, status='confirmed').count()
    processing_orders = Order.objects.filter(launderer=request.user.launderer_profile, status__in=['picked_up', 'processing']).count()
    ready_orders = Order.objects.filter(launderer=request.user.launderer_profile, status='ready').count()
    completed_orders = Order.objects.filter(launderer=request.user.launderer_profile, status='delivered').count()
    rejected_orders = Order.objects.filter(launderer=request.user.launderer_profile, status='rejected').count()
    
    # Get recent orders
    recent_orders = Order.objects.filter(launderer=request.user.launderer_profile).order_by('-created_at')[:5]
    
    # Get recent reviews
    recent_reviews = Review.objects.filter(launderer=request.user.launderer_profile).order_by('-created_at')[:3]
    
    context = {
        'pending_acceptance_orders': pending_acceptance_orders,
        'confirmed_orders': confirmed_orders,
        'processing_orders': processing_orders,
        'ready_orders': ready_orders,
        'completed_orders': completed_orders,
        'rejected_orders': rejected_orders,
        'recent_orders': recent_orders,
        'recent_reviews': recent_reviews,
    }
    
    return render(request, 'launderer/dashboard.html', context)

@login_required
@user_passes_test(is_launderer)
def received_orders(request):
    launderer = request.user.launderer_profile
    logger = logging.getLogger(__name__)
    
    # Debug orders in the database
    logger.info("Debugging orders for received_orders view")
    pending_orders = debug_orders(launderer)
    
    # Get search parameters
    search_query = request.GET.get('search', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    # Filter orders - only show pending_acceptance orders
    orders = Order.objects.filter(launderer=launderer, status='pending_acceptance')
    logger.info(f"Found {orders.count()} pending acceptance orders after filter")
    
    if search_query:
        orders = orders.filter(
            Q(order_id__icontains=search_query) | 
            Q(customer__username__icontains=search_query) |
            Q(customer__email__icontains=search_query)
        )
    
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            orders = orders.filter(created_at__date__gte=start_date)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            orders = orders.filter(created_at__date__lte=end_date)
        except ValueError:
            pass
    
    orders = orders.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(orders, 10)  # Show 10 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    # Check if export requested
    if 'export' in request.GET:
        return export_orders(request, orders, 'received_orders')
    
    return render(request, 'launderer/received_orders.html', context)

@login_required
@user_passes_test(is_launderer)
def pending_orders(request):
    launderer = request.user.launderer_profile
    
    # Get search parameters
    search_query = request.GET.get('search', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    # Filter orders
    orders = Order.objects.filter(launderer=launderer, status__in=['confirmed', 'picked_up', 'processing', 'ready'])
    
    if search_query:
        orders = orders.filter(
            Q(order_id__icontains=search_query) | 
            Q(customer__username__icontains=search_query) |
            Q(customer__email__icontains=search_query)
        )
    
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            orders = orders.filter(created_at__date__gte=start_date)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            orders = orders.filter(created_at__date__lte=end_date)
        except ValueError:
            pass
    
    orders = orders.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(orders, 10)  # Show 10 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    # Check if export requested
    if 'export' in request.GET:
        return export_orders(request, orders, 'pending_orders')
    
    return render(request, 'launderer/pending_orders.html', context)

@login_required
@user_passes_test(is_launderer)
def completed_orders(request):
    launderer = request.user.launderer_profile
    
    # Get search parameters
    search_query = request.GET.get('search', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    # Filter orders
    orders = Order.objects.filter(launderer=launderer, status='delivered')
    
    if search_query:
        orders = orders.filter(
            Q(order_id__icontains=search_query) | 
            Q(customer__username__icontains=search_query) |
            Q(customer__email__icontains=search_query)
        )
    
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            orders = orders.filter(created_at__date__gte=start_date)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            orders = orders.filter(created_at__date__lte=end_date)
        except ValueError:
            pass
    
    orders = orders.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(orders, 10)  # Show 10 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    # Check if export requested
    if 'export' in request.GET:
        return export_orders(request, orders, 'completed_orders')
    
    return render(request, 'launderer/completed_orders.html', context)

@login_required
@user_passes_test(is_launderer)
def rejected_orders(request):
    launderer = request.user.launderer_profile
    
    # Get search parameters
    search_query = request.GET.get('search', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    # Filter orders
    orders = Order.objects.filter(launderer=launderer, status='rejected')
    
    if search_query:
        orders = orders.filter(
            Q(order_id__icontains=search_query) | 
            Q(customer__username__icontains=search_query) |
            Q(customer__email__icontains=search_query)
        )
    
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            orders = orders.filter(created_at__date__gte=start_date)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            orders = orders.filter(created_at__date__lte=end_date)
        except ValueError:
            pass
    
    orders = orders.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(orders, 10)  # Show 10 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    # Check if export requested
    if 'export' in request.GET:
        return export_orders(request, orders, 'rejected_orders')
    
    return render(request, 'launderer/rejected_orders.html', context)

@login_required
@user_passes_test(is_launderer)
def order_detail(request, order_id):
    launderer = request.user.launderer_profile
    order = get_object_or_404(Order, order_id=order_id, launderer=launderer)
    
    # Get order items
    order_items = order.items.all()
    
    # Get status updates
    status_updates = order.status_updates.all().order_by('-created_at')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'confirm':
            # Only confirm if order is pending acceptance
            if order.status != 'pending_acceptance':
                messages.error(request, "This order cannot be confirmed because it is not in pending acceptance status.")
                return redirect('launderer:order_detail', order_id=order.order_id)
                
            # Confirm the order
            order.status = 'confirmed'
            order.save()
            
            # Create status update
            LaundererOrderStatus.objects.create(
                order=order,
                status='confirmed',
                notes="Order confirmed by launderer",
                updated_by=request.user
            )
            
            # Create notification for customer
            from customer.models import Notification as CustomerNotification
            CustomerNotification.objects.create(
                user=order.customer,
                notification_type='order_status',
                title="Order Confirmed",
                message=f"Your order #{order.order_id} has been confirmed by {launderer.business_name}. It will be processed soon.",
                order=order
            )
            
            # Update dashboard statistics
            update_dashboard_statistics(launderer)
            
            messages.success(request, "Order confirmed successfully.")
            
        elif action == 'reject':
            # Only reject if order is pending acceptance
            if order.status != 'pending_acceptance':
                messages.error(request, "This order cannot be rejected because it is not in pending acceptance status.")
                return redirect('launderer:order_detail', order_id=order.order_id)
                
            # Reject the order
            rejection_reason = request.POST.get('rejection_reason')
            
            if not rejection_reason:
                messages.error(request, "Please provide a reason for rejection.")
                return redirect('launderer:order_detail', order_id=order.order_id)
            
            order.status = 'rejected'
            order.rejection_reason = rejection_reason
            order.save()
            
            # Create status update
            LaundererOrderStatus.objects.create(
                order=order,
                status='rejected',
                notes=f"Order rejected. Reason: {rejection_reason}",
                updated_by=request.user
            )
            
            # Create notification for customer
            from customer.models import Notification as CustomerNotification
            CustomerNotification.objects.create(
                user=order.customer,
                notification_type='order_status',
                title="Order Rejected",
                message=f"Your order #{order.order_id} has been rejected by {launderer.business_name}. Reason: {rejection_reason}",
                order=order
            )
            
            # Update dashboard statistics
            update_dashboard_statistics(launderer)
            
            messages.success(request, "Order rejected successfully.")
            
        elif action == 'update':
            # Update order status
            new_status = request.POST.get('status')
            notes = request.POST.get('notes')
            
            # Validate status transition
            valid_transitions = {
                'confirmed': ['picked_up'],
                'picked_up': ['processing'],
                'processing': ['ready'],
                'ready': ['delivered']
            }
            
            if new_status in valid_transitions.get(order.status, []):
                order.status = new_status
                
                # If delivered, set delivered date
                if new_status == 'delivered':
                    order.delivered_date = timezone.now()
                
                order.save()
                
                # Create status update
                LaundererOrderStatus.objects.create(
                    order=order,
                    status=new_status,
                    notes=notes,
                    updated_by=request.user
                )
                
                # Create notification for customer
                status_display = dict(Order.STATUS_CHOICES)[new_status]
                from customer.models import Notification as CustomerNotification
                CustomerNotification.objects.create(
                    user=order.customer,
                    notification_type='order_status',
                    title=f"Order {status_display}",
                    message=f"Your order #{order.order_id} is now {status_display.lower()}.",
                    order=order
                )
                
                # Update dashboard statistics
                update_dashboard_statistics(launderer)
                
                messages.success(request, f"Order status updated to {status_display}.")
            else:
                messages.error(request, "Invalid status transition.")
        
        return redirect('launderer:order_detail', order_id=order.order_id)
    
    context = {
        'order': order,
        'order_items': order_items,
        'status_updates': status_updates,
    }
    
    return render(request, 'launderer/order_detail.html', context)

# Helper function to update dashboard statistics
def update_dashboard_statistics(launderer):
    """Update the dashboard statistics for a launderer"""
    # This function will be called whenever an order status changes
    # The dashboard already queries the database for the latest counts,
    # so we don't need to do anything here, but this function can be
    # extended in the future if needed.
    pass

@login_required
@user_passes_test(is_launderer)
def confirm_order(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, launderer=request.user.launderer_profile)
    
    if order.status == 'pending_acceptance':
        order.status = 'confirmed'
        order.save()
        
        # Create status update
        LaundererOrderStatus.objects.create(
            order=order,
            status='confirmed',
            notes="Order confirmed by launderer",
            updated_by=request.user
        )
        
        # Create notification for customer
        from customer.models import Notification as CustomerNotification
        CustomerNotification.objects.create(
            user=order.customer,
            notification_type='order_status',
            title="Order Confirmed",
            message=f"Your order #{order.order_id} has been confirmed by {request.user.launderer_profile.business_name}. It will be processed soon.",
            order=order
        )
        
        messages.success(request, "Order confirmed successfully.")
    else:
        messages.error(request, "This order cannot be confirmed because it is not in pending acceptance status.")
    
    return redirect('launderer:order_detail', order_id=order.order_id)

@login_required
@user_passes_test(is_launderer)
def reject_order(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, launderer=request.user.launderer_profile)
    
    if request.method == 'POST':
        rejection_reason = request.POST.get('rejection_reason')
        
        if not rejection_reason:
            messages.error(request, "Please provide a reason for rejection.")
            return redirect('launderer:order_detail', order_id=order.order_id)
        
        if order.status == 'pending_acceptance':
            order.status = 'rejected'
            order.rejection_reason = rejection_reason
            order.save()
            
            # Create status update
            LaundererOrderStatus.objects.create(
                order=order,
                status='rejected',
                notes=f"Order rejected. Reason: {rejection_reason}",
                updated_by=request.user
            )
            
            # Create notification for customer
            from customer.models import Notification as CustomerNotification
            CustomerNotification.objects.create(
                user=order.customer,
                notification_type='order_status',
                title="Order Rejected",
                message=f"Your order #{order.order_id} has been rejected by {request.user.launderer_profile.business_name}. Reason: {rejection_reason}",
                order=order
            )
            
            messages.success(request, "Order rejected successfully.")
        else:
            messages.error(request, "This order cannot be rejected because it is not in pending acceptance status.")
    else:
        messages.error(request, "Invalid request method.")
    
    return redirect('launderer:order_detail', order_id=order.order_id)

@login_required
@user_passes_test(is_launderer)
def settings(request):
    launderer = request.user.launderer_profile
    
    if request.method == 'POST':
        form = LaundererProfileForm(request.POST, request.FILES, instance=launderer, user=request.user)
        if form.is_valid():
            form.save(user=request.user)
            messages.success(request, "Profile updated successfully")
            return redirect('launderer:settings')
    else:
        form = LaundererProfileForm(instance=launderer, user=request.user)
    
    # Get payment methods
    payment_methods = LaundererPaymentMethod.objects.filter(launderer=launderer)
    
    # Get working hours
    working_hours = LaundererWorkingHour.objects.filter(launderer=launderer).order_by('day')
    
    # Get services
    services = LaundererService.objects.filter(launderer=launderer)
    
    # Get cloth items
    cloth_items = ClothItem.objects.filter(launderer=launderer)
    
    context = {
        'form': form,
        'payment_methods': payment_methods,
        'working_hours': working_hours,
        'services': services,
        'cloth_items': cloth_items,
    }
    
    return render(request, 'launderer/settings.html', context)

@login_required
@user_passes_test(is_launderer)
def manage_payment_methods(request):
    launderer = request.user.launderer_profile
    
    if request.method == 'POST':
        form = LaundererPaymentMethodForm(request.POST)
        if form.is_valid():
            payment_method = form.save(commit=False)
            payment_method.launderer = launderer
            payment_method.save()
            messages.success(request, "Payment method added successfully")
            return redirect('launderer:manage_payment_methods')
    else:
        form = LaundererPaymentMethodForm()
    
    # Get payment methods
    payment_methods = LaundererPaymentMethod.objects.filter(launderer=launderer)
    
    context = {
        'form': form,
        'payment_methods': payment_methods,
    }
    
    return render(request, 'launderer/manage_payment_methods.html', context)

@login_required
@user_passes_test(is_launderer)
def delete_payment_method(request, payment_id):
    launderer = request.user.launderer_profile
    payment_method = get_object_or_404(LaundererPaymentMethod, id=payment_id, launderer=launderer)
    
    if request.method == 'POST':
        payment_method.delete()
        messages.success(request, "Payment method deleted successfully")
    
    return redirect('launderer:manage_payment_methods')

@login_required
@user_passes_test(is_launderer)
def manage_working_hours(request):
    launderer = request.user.launderer_profile
    
    # Get working hours
    working_hours = LaundererWorkingHour.objects.filter(launderer=launderer).order_by('day')
    
    if request.method == 'POST':
        # Update working hours
        for day in range(7):
            working_hour = working_hours.get(day=day)
            is_closed = request.POST.get(f'is_closed_{day}', '') == 'on'
            
            if not is_closed:
                open_time = request.POST.get(f'open_time_{day}', '')
                close_time = request.POST.get(f'close_time_{day}', '')
                
                if open_time and close_time:
                    working_hour.open_time = open_time
                    working_hour.close_time = close_time
                    working_hour.is_closed = False
                    working_hour.save()
            else:
                working_hour.is_closed = True
                working_hour.save()
        
        messages.success(request, "Working hours updated successfully")
        return redirect('launderer:manage_working_hours')
    
    context = {
        'working_hours': working_hours,
    }
    
    return render(request, 'launderer/manage_working_hours.html', context)

@login_required
@user_passes_test(is_launderer)
def manage_services(request):
    launderer = request.user.launderer_profile
    
    if request.method == 'POST':
        form = LaundererServiceForm(request.POST)
        if form.is_valid():
            service = form.save(commit=False)
            service.launderer = launderer
            service.save()
            messages.success(request, "Service added successfully")
            return redirect('launderer:manage_services')
    else:
        form = LaundererServiceForm()
    
    # Get services
    services = LaundererService.objects.filter(launderer=launderer)
    
    context = {
        'form': form,
        'services': services,
    }
    
    return render(request, 'launderer/manage_services.html', context)

@login_required
@user_passes_test(is_launderer)
def edit_service(request, service_id):
    launderer = request.user.launderer_profile
    service = get_object_or_404(LaundererService, id=service_id, launderer=launderer)
    
    if request.method == 'POST':
        form = LaundererServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, "Service updated successfully")
            return redirect('launderer:manage_services')
    else:
        form = LaundererServiceForm(instance=service)
    
    context = {
        'form': form,
        'service': service,
    }
    
    return render(request, 'launderer/edit_service.html', context)

@login_required
@user_passes_test(is_launderer)
def delete_service(request, service_id):
    launderer = request.user.launderer_profile
    service = get_object_or_404(LaundererService, id=service_id, launderer=launderer)
    
    if request.method == 'POST':
        service.delete()
        messages.success(request, "Service deleted successfully")
    
    return redirect('launderer:manage_services')

# Update the manage_cloth_items view to handle service_type
@login_required
@user_passes_test(is_launderer)
def manage_cloth_items(request):
    launderer = request.user.launderer_profile
    
    if request.method == 'POST':
        form = ClothItemForm(request.POST)
        if form.is_valid():
            # Get form data
            cloth_type_name = form.cleaned_data['cloth_type']
            cloth_name = form.cleaned_data['cloth_name']
            service_type = form.cleaned_data['service_type']
            price = form.cleaned_data['price']
            
            # Get or create cloth type
            cloth_type, created = ClothType.objects.get_or_create(name=cloth_type_name)
            
            # Create cloth item
            ClothItem.objects.create(
                launderer=launderer,
                cloth_type=cloth_type,
                cloth_name=cloth_name,
                service_type=service_type,
                price=price
            )
            
            messages.success(request, "Cloth item added successfully")
            return redirect('launderer:manage_cloth_items')
    else:
        form = ClothItemForm()
    
    # Get cloth items
    cloth_items = ClothItem.objects.filter(launderer=launderer)
    
    context = {
        'form': form,
        'cloth_items': cloth_items,
    }
    
    return render(request, 'launderer/manage_cloth_items.html', context)

# Update the edit_cloth_item view to handle service_type
@login_required
@user_passes_test(is_launderer)
def edit_cloth_item(request, item_id):
    launderer = request.user.launderer_profile
    cloth_item = get_object_or_404(ClothItem, id=item_id, launderer=launderer)
    
    if request.method == 'POST':
        form = ClothItemForm(request.POST)
        if form.is_valid():
            # Get form data
            cloth_type_name = form.cleaned_data['cloth_type']
            cloth_name = form.cleaned_data['cloth_name']
            service_type = form.cleaned_data['service_type']
            price = form.cleaned_data['price']
            
            # Get or create cloth type
            cloth_type, created = ClothType.objects.get_or_create(name=cloth_type_name)
            
            # Update cloth item
            cloth_item.cloth_type = cloth_type
            cloth_item.cloth_name = cloth_name
            cloth_item.service_type = service_type
            cloth_item.price = price
            cloth_item.save()
            
            messages.success(request, "Cloth item updated successfully")
            return redirect('launderer:manage_cloth_items')
    else:
        # Initialize form with existing data
        form = ClothItemForm(initial={
            'cloth_type': cloth_item.cloth_type.name,
            'cloth_name': cloth_item.cloth_name,
            'service_type': cloth_item.service_type or '',
            'price': cloth_item.price
        })
    
    context = {
        'form': form,
        'cloth_item': cloth_item,
    }
    
    return render(request, 'launderer/edit_cloth_item.html', context)

@login_required
@user_passes_test(is_launderer)
def delete_cloth_item(request, item_id):
    launderer = request.user.launderer_profile
    cloth_item = get_object_or_404(ClothItem, id=item_id, launderer=launderer)
    
    if request.method == 'POST':
        cloth_item.delete()
        messages.success(request, "Cloth item deleted successfully")
    
    return redirect('launderer:manage_cloth_items')

@login_required
@user_passes_test(is_launderer)
def help_support(request):
    if request.method == 'POST':
        form = LaundererSupportForm(request.POST)
        if form.is_valid():
            support = form.save(commit=False)
            support.user = request.user
            support.save()
            messages.success(request, "Your query has been submitted. We will get back to you soon.")
            return redirect('launderer:help_support')
    else:
        form = LaundererSupportForm()
    
    # Get previous support queries for this user
    support_queries = CustomerSupport.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'form': form,
        'support_queries': support_queries,
    }
    
    return render(request, 'launderer/help_support.html', context)

@login_required
@user_passes_test(is_launderer)
def export_orders(request, orders, export_type):
    # Create Excel file
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('Orders')
    
    # Add header
    bold = workbook.add_format({'bold': True})
    worksheet.write(0, 0, 'Order ID', bold)
    worksheet.write(0, 1, 'Customer Name', bold)
    worksheet.write(0, 2, 'Customer Email', bold)
    worksheet.write(0, 3, 'Order Date', bold)
    worksheet.write(0, 4, 'Service Type', bold)
    worksheet.write(0, 5, 'Pickup Date', bold)
    worksheet.write(0, 6, 'Pickup Slot', bold)
    worksheet.write(0, 7, 'Status', bold)
    worksheet.write(0, 8, 'Payment Method', bold)
    worksheet.write(0, 9, 'Total Amount', bold)
    
    # Add data
    for i, order in enumerate(orders):
        row = i + 1
        worksheet.write(row, 0, str(order.order_id))
        worksheet.write(row, 1, order.customer.get_full_name() or order.customer.username)
        worksheet.write(row, 2, order.customer.email)
        worksheet.write(row, 3, order.created_at.strftime('%Y-%m-%d %H:%M'))
        worksheet.write(row, 4, order.get_service_type_display())
        worksheet.write(row, 5, order.pickup_date.strftime('%Y-%m-%d'))
        worksheet.write(row, 6, order.get_pickup_slot_display())
        worksheet.write(row, 7, order.get_status_display())
        worksheet.write(row, 8, order.get_payment_method_display())
        worksheet.write(row, 9, float(order.total_amount))
    
    workbook.close()
    
    # Create response
    output.seek(0)
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"laundrygo_{export_type}_{timezone.now().strftime('%Y%m%d')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

@login_required
@user_passes_test(is_launderer)
def notifications(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Update notification count in session
    request.session['notification_count'] = Notification.objects.filter(user=request.user, is_read=False).count()
    
    return render(request, 'launderer/notifications.html', {
        'notifications': notifications
    })

@login_required
@user_passes_test(is_launderer)
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    
    if request.method == 'POST':
        notification.is_read = True
        notification.save()
        
        # Update notification count in session
        request.session['notification_count'] = Notification.objects.filter(user=request.user, is_read=False).count()
    
    return redirect('launderer:notifications')

@login_required
@user_passes_test(is_launderer)
def mark_all_read(request):
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        
        # Update notification count in session
        request.session['notification_count'] = 0
    
    return redirect('launderer:notifications')

