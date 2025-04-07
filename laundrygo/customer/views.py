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
from django.db import transaction
import logging

# Set up logger
logger = logging.getLogger(__name__)

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
@login_required
def scheduling(request, launderer_id):
    logger.info(f"Scheduling view called for launderer_id: {launderer_id}")
    
    launderer = get_object_or_404(Launderer, id=launderer_id)
    logger.info(f"Launderer found: {launderer.business_name}")
    
    # Get all cloth items for this launderer
    all_cloth_items = ClothItem.objects.filter(launderer=launderer)
    
    # Prepare cloth items JSON for JavaScript
    cloth_items_json = []
    for item in all_cloth_items:
        cloth_items_json.append({
            'id': item.id,
            'cloth_name': item.cloth_name,
            'cloth_type_name': item.cloth_type.name,
            'price': float(item.price),
            'service_type': item.service_type
        })
    
    import json
    cloth_items_json = json.dumps(cloth_items_json)
    
    # Get available services for this launderer
    from launderer.models import LaundererService
    launderer_services = LaundererService.objects.filter(launderer=launderer, is_active=True)
    
    # If the launderer has specific services defined, use those
    available_services = set()
    if launderer_services.exists():
        for service in launderer_services:
            if hasattr(service, 'service_type') and service.service_type:
                available_services.add(service.service_type)
            else:
                # Map service names to service codes
                if "wash" in service.service_name.lower():
                    available_services.add('washing')
                elif "dry" in service.service_name.lower() or "clean" in service.service_name.lower():
                    available_services.add('dry_cleaning')
                elif "iron" in service.service_name.lower() or "press" in service.service_name.lower():
                    available_services.add('ironing')
                elif "full" in service.service_name.lower() or "complete" in service.service_name.lower():
                    available_services.add('full_service')
    else:
        # Otherwise, infer from cloth items
        for item in all_cloth_items:
            if item.service_type:
                available_services.add(item.service_type)
            else:
                # If no specific service type is set, assume it's available for all services
                available_services.update([choice[0] for choice in Order.SERVICE_CHOICES])
    
    # Convert set to list for JSON serialization
    available_services_list = list(available_services)
    logger.info(f"Available services for {launderer.business_name}: {available_services_list}")
    
    # Get saved addresses for this user
    from .models import CustomerAddress
    saved_addresses = CustomerAddress.objects.filter(user=request.user)
    
    # Calculate distance and delivery charges
    customer = request.user
    delivery_charge = 0
    distance = 0
    
    # Calculate distance if both customer and launderer have coordinates
    if (customer.latitude and customer.longitude and 
        launderer.user.latitude and launderer.user.longitude):
        # Calculate distance using Haversine formula
        lat1, lon1 = customer.latitude, customer.longitude
        lat2, lon2 = launderer.user.latitude, launderer.user.longitude
        
        # Convert latitude and longitude from degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371  # Radius of earth in kilometers
        distance = round(c * r, 2)
        
        # Check if distance is within delivery radius
        if distance > launderer.delivery_radius:
            messages.warning(request, f"You are {distance} km away from this launderer, which is outside their delivery radius of {launderer.delivery_radius} km.")
    
    if request.method == 'POST':
        logger.info("POST request received for scheduling")
        
        # Log all POST data for debugging
        for key, value in request.POST.items():
            logger.info(f"POST data: {key} = {value}")
        
        # Get selected services from POST data
        try:
            selected_services = json.loads(request.POST.get('selected_services', '[]'))
            logger.info(f"Selected services: {selected_services}")
        except json.JSONDecodeError:
            logger.error("Failed to parse selected_services JSON")
            selected_services = []
        
        if not selected_services:
            messages.error(request, 'Please select at least one service')
            form = OrderForm()
            return render(request, 'customer/scheduling.html', {
                'form': form,
                'launderer': launderer,
                'available_services': json.dumps(available_services_list),
                'distance': distance,
                'delivery_charge': delivery_charge,
                'cloth_items_json': cloth_items_json,
                'saved_addresses': saved_addresses
            })
        
        # Get items data
        try:
            items_data = json.loads(request.POST.get('items_data', '[]'))
            logger.info(f"Items data: {items_data}")
        except json.JSONDecodeError:
            logger.error("Failed to parse items_data JSON")
            items_data = []
        
        if not items_data:
            messages.error(request, 'Please select at least one item')
            form = OrderForm()
            return render(request, 'customer/scheduling.html', {
                'form': form,
                'launderer': launderer,
                'available_services': json.dumps(available_services_list),
                'distance': distance,
                'delivery_charge': delivery_charge,
                'cloth_items_json': cloth_items_json,
                'saved_addresses': saved_addresses
            })
        
        # Create a modified POST data dictionary that includes the required fields
        post_data = request.POST.copy()
        
        # Add the launderer ID to the POST data
        post_data['launderer'] = launderer.id
        
        # Add the first selected service as the service_type
        post_data['service_type'] = selected_services[0]
        
        # Now create the form with the modified POST data
        form = OrderForm(post_data, request.FILES)
        
        if form.is_valid():
            logger.info("Form is valid")
            try:
                # Use transaction to ensure all related objects are created together
                with transaction.atomic():
                    # Create order object but don't save yet
                    order = form.save(commit=False)
                    order.customer = request.user
                    order.launderer = launderer
                    order.status = 'pending_acceptance'  # Set initial status to pending_acceptance
                    logger.info(f"Setting order status to: {order.status}")
                    
                    # Calculate total amount
                    total_amount = 0
                    
                    # Calculate item subtotals
                    for item_data in items_data:
                        cloth_item_id = item_data.get('id')
                        if not cloth_item_id:
                            logger.error(f"Missing cloth item ID in item data: {item_data}")
                            continue
                            
                        try:
                            cloth_item = ClothItem.objects.get(id=cloth_item_id)
                            quantity = int(item_data.get('quantity', 1))
                            subtotal = cloth_item.price * quantity
                            total_amount += subtotal
                        except ClothItem.DoesNotExist:
                            logger.error(f"Cloth item with ID {cloth_item_id} not found")
                            continue
                        except ValueError as e:
                            logger.error(f"Error calculating subtotal: {str(e)}")
                            continue
                    
                    # Calculate delivery charge if pickup or both is selected
                    pickup_delivery = form.cleaned_data['pickup_delivery']
                    if pickup_delivery in ['pickup', 'both'] and distance > 0:
                        # Free delivery if order amount exceeds minimum
                        if total_amount >= launderer.min_order_free_delivery:
                            delivery_charge = 0
                        else:
                            # Base charge plus per km charge
                            delivery_charge = launderer.base_delivery_charge + (distance * launderer.per_km_charge)

                    # Add delivery charge to total
                    order.delivery_charge = delivery_charge
                    order.distance = distance
                    order.total_amount = total_amount + delivery_charge

                    # Handle image upload
                    if 'laundry_image' in request.FILES:
                        order.laundry_image = request.FILES['laundry_image']

                    # Get selected address
                    selected_address_id = request.POST.get('selected_address_id')
                    if selected_address_id and selected_address_id != str(request.user.id):
                        try:
                            address = CustomerAddress.objects.get(id=selected_address_id, user=request.user)
                            order.delivery_address = address.address
                            order.delivery_pincode = address.pincode
                            order.delivery_instructions = address.instructions
                        except CustomerAddress.DoesNotExist:
                            # Use customer's default address if selected address doesn't exist
                            order.delivery_address = request.user.address
                            order.delivery_pincode = request.user.pincode
                            order.delivery_instructions = request.user.delivery_instructions
                    else:
                        # Use customer's default address
                        order.delivery_address = request.user.address
                        order.delivery_pincode = request.user.pincode
                        order.delivery_instructions = request.user.delivery_instructions

                    # Log order details before saving
                    logger.info(f"Order details before save: {order.__dict__}")
                    
                    # Save the order to the database
                    order.save()
                    logger.info(f"Order saved successfully with ID: {order.order_id}")
                    
                    # Verify the order was saved correctly
                    saved_order = Order.objects.filter(order_id=order.order_id).first()
                    if saved_order:
                        logger.info(f"Order verification: Found order with ID {saved_order.order_id}, status: {saved_order.status}")
                    else:
                        logger.error(f"Order verification failed: Could not find order with ID {order.order_id}")
                    
                    # Save order items
                    for item_data in items_data:
                        cloth_item_id = item_data.get('id')
                        if not cloth_item_id:
                            continue
                            
                        try:
                            cloth_item = ClothItem.objects.get(id=cloth_item_id)
                            quantity = int(item_data.get('quantity', 1))
                            subtotal = cloth_item.price * quantity
                            
                            order_item = OrderItem.objects.create(
                                order=order,
                                cloth_item=cloth_item,
                                quantity=quantity,
                                subtotal=subtotal
                            )
                            logger.info(f"Order item created: {order_item.id}")
                        except Exception as e:
                            logger.error(f"Error creating order item: {str(e)}")
                            continue
                    
                    # Create notification for launderer about new order
                    try:
                        from launderer.models import Notification as LaundererNotification
                        notification = LaundererNotification.objects.create(
                            user=launderer.user,
                            notification_type='new_order',
                            title="New Order Received",
                            message=f"You have received a new order from {request.user.username}.",
                            order=order
                        )
                        logger.info(f"Launderer notification created: {notification.id}")
                    except Exception as e:
                        logger.error(f"Error creating launderer notification: {str(e)}")
                    
                    # Create a status update for the order
                    try:
                        from launderer.models import LaundererOrderStatus
                        status_update = LaundererOrderStatus.objects.create(
                            order=order,
                            status='pending_acceptance',
                            notes="Order placed by customer",
                            updated_by=None  # Make updated_by nullable
                        )
                        logger.info(f"Status update created: {status_update.id}")
                    except Exception as e:
                        logger.error(f"Error creating status update: {str(e)}")
                    
                    # Create notification for customer about order placement
                    try:
                        from customer.models import Notification as CustomerNotification
                        customer_notification = CustomerNotification.objects.create(
                            user=request.user,
                            notification_type='order_status',
                            title="Order Placed Successfully",
                            message=f"Your order #{order.order_id} has been placed successfully. It will be confirmed once the launderer accepts it.",
                            order=order
                        )
                        logger.info(f"Customer notification created: {customer_notification.id}")
                    except Exception as e:
                        logger.error(f"Error creating customer notification: {str(e)}")
                
                # Check if the order was successfully saved
                try:
                    order_check = Order.objects.get(order_id=order.order_id)
                    logger.info(f"Order successfully saved and retrieved: {order_check.order_id}, status: {order_check.status}")
                    messages.success(request, 'Order placed successfully! Your order will be confirmed once the launderer accepts it.')
                    return redirect('customer:order_details', order_id=order.order_id)
                except Order.DoesNotExist:
                    logger.error(f"Order was not saved to the database: {order.order_id}")
                    messages.error(request, 'Error: Order was not saved to the database. Please try again.')
                    
            except Exception as e:
                # Print detailed error information
                logger.error(f"Error saving order: {str(e)}")
                logger.error(traceback.format_exc())
                messages.error(request, f'Error saving order: {str(e)}')
        else:
            logger.error(f"Form is invalid. Errors: {form.errors}")
            messages.error(request, f"Form validation failed: {form.errors}")
    else:
        form = OrderForm()
    
    return render(request, 'customer/scheduling.html', {
        'form': form,
        'launderer': launderer,
        'available_services': json.dumps(available_services_list),  # Pass as JSON string
        'distance': distance,
        'delivery_charge': delivery_charge,
        'cloth_items_json': cloth_items_json,
        'saved_addresses': saved_addresses
    })


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
        from launderer.models import LaundererOrderStatus
        LaundererOrderStatus.objects.create(
            order=order,
            status='cancelled',
            notes="Cancelled by customer",
            updated_by=request.user
        )
        
        # Create notification for launderer
        from launderer.models import Notification as LaundererNotification
        LaundererNotification.objects.create(
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
    from customer.models import Notification
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Update notification count in session
    request.session['notification_count'] = Notification.objects.filter(user=request.user, is_read=False).count()
    
    return render(request, 'customer/notifications.html', {
        'notifications': notifications
    })

@login_required
def mark_notification_read(request, notification_id):
    from customer.models import Notification
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    
    if request.method == 'POST':
        notification.is_read = True
        notification.save()
        
        # Update notification count in session
        request.session['notification_count'] = Notification.objects.filter(user=request.user, is_read=False).count()
    
    return redirect('customer:notifications')

@login_required
def mark_all_read(request):
    from customer.models import Notification
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        
        # Update notification count in session
        request.session['notification_count'] = 0
    
    return redirect('customer:notifications')

@login_required
def order_tracking(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, customer=request.user)
    
    return render(request, 'customer/order_tracking.html', {
        'order': order
    })

