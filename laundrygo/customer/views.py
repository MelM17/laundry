from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Q
from django.http import HttpResponse
from django.utils import timezone
from django.core.paginator import Paginator
from .models import User, Launderer, Order, OrderItem, ClothItem, Review, CustomerSupport, ContactMessage
from .forms import (CustomerRegistrationForm, CustomerProfileUpdateForm, OrderForm, 
                   ReviewForm, CustomerSupportForm, CustomPasswordResetForm, CustomSetPasswordForm)
import uuid
import json
import math
from xhtml2pdf import pisa
from django.template.loader import get_template

def home(request):
    if request.user.is_authenticated and request.user.user_type == 'customer':
        return redirect('customer:dashboard')
    return render(request, 'customer/login.html')

def register_customer(request):
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('customer:dashboard')
    else:
        form = CustomerRegistrationForm()
    return render(request, 'customer/register.html', {'form': form})

def login_customer(request):
    if request.user.is_authenticated:
        if request.user.user_type == 'customer':
            return redirect('customer:home')
        elif request.user.user_type == 'launderer':
            return redirect('launderer:dashboard')
        elif request.user.user_type == 'admin':
            return redirect('admin_portal:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None and user.user_type == 'customer':
            login(request, user)
            return redirect('customer:dashboard')
        else:
            messages.error(request, 'Invalid username or password')
    
    return render(request, 'customer/login.html')

@login_required
def logout_customer(request):
    logout(request)
    return redirect('customer:login')

@login_required
def dashboard(request):
    if request.user.user_type != 'customer':
        return redirect('customer:login')
    
    query = request.GET.get('query', '')
    pincode = request.GET.get('pincode', '')
    available_only = request.GET.get('available', '') == 'on'
    
    # Only show verified launderers to customers
    launderers = Launderer.objects.filter(is_verified=True)
    
    if query:
        launderers = launderers.filter(
            Q(business_name__icontains=query) | 
            Q(user__address__icontains=query)
        )
    
    if pincode:
        launderers = launderers.filter(user__pincode=pincode)
    
    if available_only:
        launderers = launderers.filter(is_available=True)
    
    # Sort by availability first, then by rating
    launderers = launderers.annotate(avg_rating=Avg('reviews__rating')).order_by('-is_available', '-avg_rating')
    
    paginator = Paginator(launderers, 10)  # Show 10 launderers per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'customer/home.html', {
        'page_obj': page_obj,
        'query': query,
        'pincode': pincode,
        'available_only': available_only
    })

# Update the launderer_detail view to include working hours
@login_required
def launderer_detail(request, launderer_id):
    launderer = get_object_or_404(Launderer, id=launderer_id)
    cloth_items = ClothItem.objects.filter(launderer=launderer)
    reviews = Review.objects.filter(launderer=launderer).order_by('-created_at')
    
    # Get available services for this launderer
    available_services = set()
    
    for item in cloth_items:
        if item.service_type:
            available_services.add(item.service_type)
        else:
            # If no specific service type is set, assume it's available for all services
            available_services.update([choice[0] for choice in Order.SERVICE_CHOICES])
    
    # Get working hours
    from launderer.models import LaundererWorkingHour
    working_hours = LaundererWorkingHour.objects.filter(launderer=launderer).order_by('day')
    
    return render(request, 'customer/launderer_detail.html', {
        'launderer': launderer,
        'cloth_items': cloth_items,
        'reviews': reviews,
        'available_services': available_services,
        'working_hours': working_hours
    })

# Update the scheduling view to filter cloth items by service type

@login_required
def scheduling(request, launderer_id=None):
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create the order with initial status "Pending Acceptance"
                    order = form.save(commit=False)
                    order.customer = request.user.customer
                    
                    if launderer_id:
                        try:
                            launderer = Launderer.objects.get(id=launderer_id)
                            order.launderer = launderer
                        except Launderer.DoesNotExist:
                            messages.error(request, "Selected launderer does not exist.")
                            return redirect('customer:scheduling')
                    
                    order.status = 'pending_acceptance'  # Set initial status to pending_acceptance
                    order.save()
                    logger.info(f"Order created successfully: {order.id}")
                    
                    # Create notification for the launderer
                    if order.launderer:
                        Notification.objects.create(
                            user=order.launderer.user,
                            message=f"New order received from {order.customer.user.username}",
                            order_id=order.id,
                            notification_type="new_order"
                        )
                    
                    # Create items from the form data
                    items_data = []
                    for i in range(1, 11):  # Assuming maximum 10 items
                        item_type = request.POST.get(f'item_type_{i}')
                        quantity = request.POST.get(f'quantity_{i}')
                        
                        if item_type and quantity and int(quantity) > 0:
                            items_data.append({
                                'item_type': item_type,
                                'quantity': int(quantity)
                            })
                    
                    # Save each item
                    for item_data in items_data:
                        OrderItem.objects.create(
                            order=order,
                            item_type=item_data['item_type'],
                            quantity=item_data['quantity']
                        )
                    
                    messages.success(request, "Your order has been placed successfully! It will be confirmed once the launderer accepts it.")
                    return redirect('customer:order_details', order_id=order.id)
            except Exception as e:
                logger.error(f"Error creating order: {str(e)}")
                messages.error(request, f"An error occurred while placing your order: {str(e)}")
        else:
            logger.error(f"Form validation errors: {form.errors}")
            messages.error(request, "Please correct the errors in the form.")
    else:
        form = OrderForm()
        if launderer_id:
            try:
                launderer = Launderer.objects.get(id=launderer_id)
                form.fields['launderer'].initial = launderer.id
            except Launderer.DoesNotExist:
                messages.error(request, "Selected launderer does not exist.")
                return redirect('customer:scheduling')
    
    launderers = Launderer.objects.filter(is_verified=True)
    return render(request, 'customer/scheduling.html', {
        'form': form,
        'launderers': launderers
    })

@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user.customer)
    
    # Only allow cancellation if order is pending acceptance
    if order.status != 'pending_acceptance':
        messages.error(request, "You can only cancel orders that are pending acceptance.")
        return redirect('customer:order_details', order_id=order.id)
    
    if request.method == 'POST':
        with transaction.atomic():
            order.status = 'cancelled'
            order.save()
            
            # Create status update
            from launderer.models import LaundererOrderStatus, Notification
            LaundererOrderStatus.objects.create(
                order=order,
                status='cancelled',
                notes="Cancelled by customer",
                updated_by=request.user
            )
            
            # Create notification for launderer
            if order.launderer:
                Notification.objects.create(
                    user=order.launderer.user,
                    notification_type='order_status',
                    title="Order Cancelled",
                    message=f"Order #{order.id} has been cancelled by the customer.",
                    order=order
                )
            
            messages.success(request, "Your order has been cancelled successfully.")
            return redirect('customer:orders')
    
    return redirect('customer:order_details', order_id=order.id)


@login_required
def orders(request):
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    return render(request, 'customer/orders.html', {'orders': orders})

@login_required
def order_details(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, customer=request.user)
    items = OrderItem.objects.filter(order=order)
    
    return render(request, 'customer/order_details.html', {
        'order': order,
        'items': items
    })

@login_required
def download_order_pdf(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, customer=request.user)
    items = OrderItem.objects.filter(order=order)
    
    template = get_template('customer/order_pdf.html')
    context = {
        'order': order,
        'items': items,
    }
    html = template.render(context)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="order_{order.order_id}.pdf"'
    
    # Create PDF
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('PDF generation error')
    return response

@login_required
def submit_review(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, customer=request.user)
    
    # Check if order is delivered
    if order.status != 'delivered':
        messages.error(request, 'You can only review completed orders')
        return redirect('customer:order_details', order_id=order.order_id)
    
    # Check if review already exists
    existing_review = Review.objects.filter(order=order).first()
    if existing_review:
        messages.error(request, 'You have already submitted a review for this order')
        return redirect('customer:order_details', order_id=order.order_id)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.customer = request.user
            review.launderer = order.launderer
            review.order = order
            review.save()
            
            # Update launderer rating
            launderer_reviews = Review.objects.filter(launderer=order.launderer)
            avg_rating = launderer_reviews.aggregate(Avg('rating'))['rating__avg']
            order.launderer.rating = avg_rating
            order.launderer.save()
            
            messages.success(request, 'Review submitted successfully!')
            return redirect('customer:order_details', order_id=order.order_id)
    else:
        form = ReviewForm()
    
    return render(request, 'customer/feedback.html', {
        'form': form,
        'order': order
    })

@login_required
def settings(request):
    if request.method == 'POST':
        form = CustomerProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('customer:settings')
    else:
        form = CustomerProfileUpdateForm(instance=request.user)
    
    return render(request, 'customer/settings.html', {'form': form})

@login_required
def help(request):
    if request.method == 'POST':
        form = CustomerSupportForm(request.POST)
        if form.is_valid():
            support = form.save(commit=False)
            support.user = request.user
            support.save()
            messages.success(request, 'Your query has been submitted. We will get back to you soon.')
            return redirect('customer:dashboard')
    else:
        form = CustomerSupportForm()
    
    # Get previous support queries for this user
    previous_queries = CustomerSupport.objects.filter(user=request.user).order_by('-created_at')
    
    return render(request, 'customer/help.html', {
        'form': form,
        'previous_queries': previous_queries
    })

def forgot_password(request):
    if request.method == 'POST':
        form = CustomPasswordResetForm(request.POST)
        if form.is_valid():
            # Process the form
            email = form.cleaned_data['email']
            user_type = form.cleaned_data['user_type']
            
            # Check if user exists
            user = User.objects.filter(email=email, user_type=user_type).first()
            if user:
                # In a real application, send a password reset email
                # For this example, we'll just redirect to a reset page
                return redirect('customer:reset_password', user_id=user.id)
            else:
                messages.error(request, 'No user found with this email and user type')
    else:
        form = CustomPasswordResetForm()
    
    return render(request, 'customer/forgot_password.html', {'form': form})

def reset_password(request, user_id):
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        form = CustomSetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Password has been reset successfully. You can now login.')
            return redirect('customer:login')
    else:
        form = CustomSetPasswordForm(user)
    
    return render(request, 'customer/reset_password.html', {'form': form})

# Add a contact view function at the end of the file
def contact(request):
    confirmation_message = None
    
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        # Check if the user is registered
        is_registered = request.user.is_authenticated
        user = request.user if is_registered else None
        
        # Create contact message
        contact_msg = ContactMessage.objects.create(
            name=name,
            email=email,
            subject=subject,
            message=message,
            is_registered_user=is_registered,
            user=user
        )
        
        confirmation_message = "Your message has been sent successfully. We'll get back to you soon!"
    
    # Get previous messages for this user if logged in
    previous_messages = []
    if request.user.is_authenticated:
        previous_messages = ContactMessage.objects.filter(user=request.user).order_by('-created_at')
    
    return render(request, 'customer/contact.html', {
        'confirmation_message': confirmation_message,
        'previous_messages': previous_messages
    })

@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, customer=request.user)
    
    # Only allow cancellation if order is pending acceptance or pending
    if order.status not in ['pending_acceptance', 'pending']:
        messages.error(request, "You can only cancel orders that are pending acceptance or confirmation.")
        return redirect('customer:order_details', order_id=order.order_id)
    
    if request.method == 'POST':
        order.status = 'cancelled'
        order.save()
        
        # Create status update
        from launderer.models import LaundererOrderStatus, Notification
        LaundererOrderStatus.objects.create(
            order=order,
            status='cancelled',
            notes="Cancelled by customer",
            updated_by=request.user
        )
        
        # Create notification for launderer
        Notification.objects.create(
            user=order.launderer.user,
            notification_type='order_status',
            title="Order Cancelled",
            message=f"Order #{order.order_id} has been cancelled by the customer.",
            order=order
        )
        
        messages.success(request, "Your order has been cancelled successfully.")
        return redirect('customer:orders')
    
    return redirect('customer:order_details', order_id=order.order_id)

@login_required
def notifications(request):
    from launderer.models import Notification
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Update notification count in session
    request.session['notification_count'] = Notification.objects.filter(user=request.user, is_read=False).count()
    
    return render(request, 'customer/notifications.html', {
        'notifications': notifications
    })

@login_required
def mark_notification_read(request, notification_id):
    from launderer.models import Notification
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    
    if request.method == 'POST':
        notification.is_read = True
        notification.save()
        
        # Update notification count in session
        request.session['notification_count'] = Notification.objects.filter(user=request.user, is_read=False).count()
    
    return redirect('customer:notifications')

@login_required
def mark_all_read(request):
    from launderer.models import Notification
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        
        # Update notification count in session
        request.session['notification_count'] = 0
    
    return redirect('customer:notifications')

