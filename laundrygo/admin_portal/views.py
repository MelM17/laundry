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

from customer.models import User, Launderer, CustomerSupport, Order, Review
from .models import LaundererVerification, AdminSupportResponse, AnalyticsData
from .forms import AdminLoginForm, LaundererVerificationForm, AdminSupportResponseForm, AnalyticsFilterForm

# Helper function to check if user is admin
def is_admin(user):
    return user.is_authenticated and user.user_type == 'admin'

def admin_login(request):
    if request.user.is_authenticated:
        if request.user.user_type == 'admin':
            return redirect('admin_portal:dashboard')
        elif request.user.user_type == 'customer':
            return redirect('customer:home')
        elif request.user.user_type == 'launderer':
            return redirect('launderer:dashboard')
    
    if request.method == 'POST':
        form = AdminLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None and user.user_type == 'admin':
                login(request, user)
                return redirect('admin_portal:dashboard')
            else:
                messages.error(request, 'Invalid username or password or insufficient permissions.')
        else:
            messages.error(request, 'Invalid username or password or insufficient permissions.')
    else:
        form = AdminLoginForm()
    
    return render(request, 'admin_portal/login.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def admin_logout(request):
    logout(request)
    return redirect('admin_portal:login')

@login_required
@user_passes_test(is_admin)
def dashboard(request):
    # Get counts for dashboard
    pending_verifications = LaundererVerification.objects.filter(status='pending').count()
    unresolved_customer_support = CustomerSupport.objects.filter(is_resolved=False, user__user_type='customer').count()
    unresolved_launderer_support = CustomerSupport.objects.filter(is_resolved=False, user__user_type='launderer').count()
    
    # Add contact messages count
    from customer.models import ContactMessage
    pending_contact_messages = ContactMessage.objects.filter(status='pending').count()
    
    # Get recent registrations
    recent_customers = User.objects.filter(user_type='customer').order_by('-date_joined')[:5]
    recent_launderers = Launderer.objects.order_by('-user__date_joined')[:5]
    
    context = {
        'pending_verifications': pending_verifications,
        'unresolved_customer_support': unresolved_customer_support,
        'unresolved_launderer_support': unresolved_launderer_support,
        'pending_contact_messages': pending_contact_messages,
        'recent_customers': recent_customers,
        'recent_launderers': recent_launderers,
    }
    
    return render(request, 'admin_portal/dashboard.html', context)

@login_required
@user_passes_test(is_admin)
def new_registrations(request):
    pending_verifications = LaundererVerification.objects.filter(status='pending').select_related('launderer', 'launderer__user')
    
    paginator = Paginator(pending_verifications, 10)  # Show 10 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'admin_portal/new_registrations.html', {'page_obj': page_obj})

@login_required
@user_passes_test(is_admin)
def verify_launderer(request, verification_id):
    verification = get_object_or_404(LaundererVerification, id=verification_id, status='pending')
    
    if request.method == 'POST':
        form = LaundererVerificationForm(request.POST, instance=verification)
        if form.is_valid():
            action = request.POST.get('action')
            
            if action == 'approve':
                verification.approve(request.user)
                messages.success(request, f"Launderer '{verification.launderer.business_name}' has been approved.")
            elif action == 'reject':
                rejection_reason = form.cleaned_data.get('rejection_reason')
                if not rejection_reason:
                    messages.error(request, "Please provide a reason for rejection.")
                    return redirect('admin_portal:verify_launderer', verification_id=verification_id)
                
                verification.reject(request.user, rejection_reason)
                messages.success(request, f"Launderer '{verification.launderer.business_name}' has been rejected.")
            
            return redirect('admin_portal:new_registrations')
    else:
        form = LaundererVerificationForm(instance=verification)
    
    return render(request, 'admin_portal/verify_launderer.html', {
        'form': form,
        'verification': verification
    })

@login_required
@user_passes_test(is_admin)
def manage_customers(request):
    # Get customer support queries
    query = request.GET.get('query', '')
    status = request.GET.get('status', 'unresolved')
    
    support_queries = CustomerSupport.objects.filter(user__user_type='customer').select_related('user')
    
    if query:
        support_queries = support_queries.filter(
            Q(user__username__icontains=query) | 
            Q(user__email__icontains=query) |
            Q(query__icontains=query)
        )
    
    if status == 'unresolved':
        support_queries = support_queries.filter(is_resolved=False)
    elif status == 'resolved':
        support_queries = support_queries.filter(is_resolved=True)
    
    support_queries = support_queries.order_by('-created_at')
    
    paginator = Paginator(support_queries, 10)  # Show 10 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'admin_portal/manage_customers.html', {
        'page_obj': page_obj,
        'query': query,
        'status': status
    })

@login_required
@user_passes_test(is_admin)
def respond_to_customer(request, query_id):
    support_query = get_object_or_404(CustomerSupport, id=query_id, user__user_type='customer')
    
    if request.method == 'POST':
        form = AdminSupportResponseForm(request.POST)
        if form.is_valid():
            response = form.save(commit=False)
            response.support_query = support_query
            response.responded_by = request.user
            response.save()
            
            messages.success(request, "Response sent successfully.")
            return redirect('admin_portal:manage_customers')
    else:
        form = AdminSupportResponseForm()
    
    return render(request, 'admin_portal/respond_to_support.html', {
        'form': form,
        'support_query': support_query,
        'user_type': 'customer'
    })

@login_required
@user_passes_test(is_admin)
def manage_laundromats(request):
    # Get launderer support queries
    query = request.GET.get('query', '')
    status = request.GET.get('status', 'unresolved')
    
    support_queries = CustomerSupport.objects.filter(user__user_type='launderer').select_related('user')
    
    if query:
        support_queries = support_queries.filter(
            Q(user__username__icontains=query) | 
            Q(user__email__icontains=query) |
            Q(query__icontains=query)
        )
    
    if status == 'unresolved':
        support_queries = support_queries.filter(is_resolved=False)
    elif status == 'resolved':
        support_queries = support_queries.filter(is_resolved=True)
    
    support_queries = support_queries.order_by('-created_at')
    
    paginator = Paginator(support_queries, 10)  # Show 10 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'admin_portal/manage_laundromats.html', {
        'page_obj': page_obj,
        'query': query,
        'status': status
    })

@login_required
@user_passes_test(is_admin)
def respond_to_launderer(request, query_id):
    support_query = get_object_or_404(CustomerSupport, id=query_id, user__user_type='launderer')
    
    if request.method == 'POST':
        form = AdminSupportResponseForm(request.POST)
        if form.is_valid():
            response = form.save(commit=False)
            response.support_query = support_query
            response.responded_by = request.user
            response.save()
            
            messages.success(request, "Response sent successfully.")
            return redirect('admin_portal:manage_laundromats')
    else:
        form = AdminSupportResponseForm()
    
    return render(request, 'admin_portal/respond_to_support.html', {
        'form': form,
        'support_query': support_query,
        'user_type': 'launderer'
    })

@login_required
@user_passes_test(is_admin)
def analytics(request):
    # Default to last 30 days if no dates provided
    today = timezone.now().date()
    default_start_date = today - timedelta(days=30)
    default_end_date = today
    
    if request.method == 'POST':
        form = AnalyticsFilterForm(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            report_type = form.cleaned_data['report_type']
        else:
            start_date = default_start_date
            end_date = default_end_date
            report_type = 'all'
    else:
        form = AnalyticsFilterForm(initial={
            'start_date': default_start_date,
            'end_date': default_end_date,
            'report_type': 'all'
        })
        start_date = default_start_date
        end_date = default_end_date
        report_type = 'all'
    
    # Get analytics data
    analytics_data = AnalyticsData.objects.filter(date__range=[start_date, end_date]).order_by('date')
    
    # Calculate totals
    total_customers = sum(data.customers_registered for data in analytics_data)
    total_laundromats = sum(data.laundromats_registered for data in analytics_data)
    total_verified = sum(data.laundromats_verified for data in analytics_data)
    total_rejected = sum(data.laundromats_rejected for data in analytics_data)
    total_orders = sum(data.orders_placed for data in analytics_data)
    total_completed = sum(data.orders_completed for data in analytics_data)
    total_revenue = sum(data.total_revenue for data in analytics_data)
    
    # Get additional data
    laundromats_by_rating = Launderer.objects.annotate(
        avg_rating=Sum('reviews__rating') / Count('reviews')
    ).order_by('-avg_rating')[:10]
    
    # Check if export requested
    if 'export' in request.POST:
        return export_analytics(request, analytics_data, start_date, end_date, report_type)
    
    context = {
        'form': form,
        'analytics_data': analytics_data,
        'total_customers': total_customers,
        'total_laundromats': total_laundromats,
        'total_verified': total_verified,
        'total_rejected': total_rejected,
        'total_orders': total_orders,
        'total_completed': total_completed,
        'total_revenue': total_revenue,
        'laundromats_by_rating': laundromats_by_rating,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'admin_portal/analytics.html', context)

@login_required
@user_passes_test(is_admin)
def export_analytics(request, analytics_data, start_date, end_date, report_type):
    # Create Excel file
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('Analytics')
    
    # Add header
    bold = workbook.add_format({'bold': True})
    worksheet.write(0, 0, 'Date', bold)
    
    if report_type in ['customers_registered', 'all']:
        worksheet.write(0, 1, 'Customers Registered', bold)
    
    if report_type in ['laundromats_registered', 'all']:
        worksheet.write(0, 2, 'Laundromats Registered', bold)
        worksheet.write(0, 3, 'Laundromats Verified', bold)
        worksheet.write(0, 4, 'Laundromats Rejected', bold)
    
    if report_type in ['orders_placed', 'all']:
        worksheet.write(0, 5, 'Orders Placed', bold)
        worksheet.write(0, 6, 'Orders Completed', bold)
    
    if report_type in ['revenue', 'all']:
        worksheet.write(0, 7, 'Total Revenue', bold)
    
    # Add data
    for i, data in enumerate(analytics_data):
        row = i + 1
        worksheet.write(row, 0, data.date.strftime('%Y-%m-%d'))
        
        if report_type in ['customers_registered', 'all']:
            worksheet.write(row, 1, data.customers_registered)
        
        if report_type in ['laundromats_registered', 'all']:
            worksheet.write(row, 2, data.laundromats_registered)
            worksheet.write(row, 3, data.laundromats_verified)
            worksheet.write(row, 4, data.laundromats_rejected)
        
        if report_type in ['orders_placed', 'all']:
            worksheet.write(row, 5, data.orders_placed)
            worksheet.write(row, 6, data.orders_completed)
        
        if report_type in ['revenue', 'all']:
            worksheet.write(row, 7, float(data.total_revenue))
    
    # Add totals row
    total_row = len(analytics_data) + 1
    worksheet.write(total_row, 0, 'Total', bold)
    
    if report_type in ['customers_registered', 'all']:
        worksheet.write(total_row, 1, sum(data.customers_registered for data in analytics_data))
    
    if report_type in ['laundromats_registered', 'all']:
        worksheet.write(total_row, 2, sum(data.laundromats_registered for data in analytics_data))
        worksheet.write(total_row, 3, sum(data.laundromats_verified for data in analytics_data))
        worksheet.write(total_row, 4, sum(data.laundromats_rejected for data in analytics_data))
    
    if report_type in ['orders_placed', 'all']:
        worksheet.write(total_row, 5, sum(data.orders_placed for data in analytics_data))
        worksheet.write(total_row, 6, sum(data.orders_completed for data in analytics_data))
    
    if report_type in ['revenue', 'all']:
        worksheet.write(total_row, 7, float(sum(data.total_revenue for data in analytics_data)))
    
    workbook.close()
    
    # Create response
    output.seek(0)
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"laundrygo_analytics_{start_date}_to_{end_date}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

@login_required
@user_passes_test(is_admin)
def manage_contact_messages(request):
    # Get contact messages
    query = request.GET.get('query', '')
    status = request.GET.get('status', 'pending')
    
    from customer.models import ContactMessage
    contact_messages = ContactMessage.objects.all()
    
    if query:
        contact_messages = contact_messages.filter(
            Q(name__icontains=query) | 
            Q(email__icontains=query) |
            Q(subject__icontains=query) |
            Q(message__icontains=query)
        )
    
    if status != 'all':
        contact_messages = contact_messages.filter(status=status)
    
    contact_messages = contact_messages.order_by('-created_at')
    
    paginator = Paginator(contact_messages, 10)  # Show 10 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'admin_portal/manage_contact_messages.html', {
        'page_obj': page_obj,
        'query': query,
        'status': status
    })

# Update the respond_to_contact view to send email
@login_required
@user_passes_test(is_admin)
def respond_to_contact(request, message_id):
    from customer.models import ContactMessage
    contact_message = get_object_or_404(ContactMessage, id=message_id)
    
    if request.method == 'POST':
        response = request.POST.get('response')
        
        if response:
            # Update the contact message
            contact_message.admin_response = response
            contact_message.status = 'replied'
            contact_message.save()
            
            # Send email (uncomment in production)
            from django.core.mail import send_mail
            try:
                send_mail(
                    f'Re: {contact_message.subject}',
                    response,
                    'admin@laundrygo.com',
                    [contact_message.email],
                    fail_silently=False,
                )
                messages.success(request, "Response sent successfully to customer's email.")
            except Exception as e:
                messages.warning(request, f"Response saved but email could not be sent: {str(e)}")
            
            return redirect('admin_portal:manage_contact_messages')
        else:
            messages.error(request, "Response cannot be empty.")
    
    return render(request, 'admin_portal/respond_to_contact.html', {
        'contact_message': contact_message
    })

