from django.db import models
from django.utils import timezone
from customer.models import User, Launderer, Order

class LaundererVerification(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    launderer = models.OneToOneField(Launderer, on_delete=models.CASCADE, related_name='verification')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    verification_date = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verifications')
    rejection_reason = models.TextField(null=True, blank=True)
    
    # Document verification
    id_proof = models.FileField(upload_to='verification/id_proofs/', null=True, blank=True)
    business_license = models.FileField(upload_to='verification/business_licenses/', null=True, blank=True)
    address_proof = models.FileField(upload_to='verification/address_proofs/', null=True, blank=True)
    
    def __str__(self):
        return f"{self.launderer.business_name} - {self.get_status_display()}"
    
    def approve(self, admin_user):
        self.status = 'approved'
        self.verification_date = timezone.now()
        self.verified_by = admin_user
        self.save()
        
        # Update launderer status
        self.launderer.is_verified = True
        self.launderer.save()
    
    def reject(self, admin_user, reason=None):
        self.status = 'rejected'
        self.verification_date = timezone.now()
        self.verified_by = admin_user
        self.rejection_reason = reason
        self.save()

class AdminSupportResponse(models.Model):
    support_query = models.ForeignKey('customer.CustomerSupport', on_delete=models.CASCADE, related_name='admin_responses')
    response_text = models.TextField()
    responded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='support_responses')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Response to {self.support_query.user.username}'s query"
    
    def save(self, *args, **kwargs):
        # Mark the support query as resolved when a response is added
        if not self.id:  # Only on creation
            self.support_query.is_resolved = True
            self.support_query.resolved_at = timezone.now()
            self.support_query.response = self.response_text
            self.support_query.save()
        
        super().save(*args, **kwargs)

class AnalyticsData(models.Model):
    date = models.DateField(unique=True)
    customers_registered = models.IntegerField(default=0)
    laundromats_registered = models.IntegerField(default=0)
    laundromats_verified = models.IntegerField(default=0)
    laundromats_rejected = models.IntegerField(default=0)
    orders_placed = models.IntegerField(default=0)
    orders_completed = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    def __str__(self):
        return f"Analytics for {self.date}"
    
    @classmethod
    def update_daily_analytics(cls):
        """Update analytics data for today"""
        today = timezone.now().date()
        analytics, created = cls.objects.get_or_create(date=today)
        
        # Get today's data
        today_start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
        today_end = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.max.time()))
        
        # Update analytics
        analytics.customers_registered = User.objects.filter(
            user_type='customer', 
            date_joined__range=(today_start, today_end)
        ).count()
        
        analytics.laundromats_registered = Launderer.objects.filter(
            user__date_joined__range=(today_start, today_end)
        ).count()
        
        analytics.laundromats_verified = LaundererVerification.objects.filter(
            status='approved',
            verification_date__range=(today_start, today_end)
        ).count()
        
        analytics.laundromats_rejected = LaundererVerification.objects.filter(
            status='rejected',
            verification_date__range=(today_start, today_end)
        ).count()
        
        analytics.orders_placed = Order.objects.filter(
            created_at__range=(today_start, today_end)
        ).count()
        
        analytics.orders_completed = Order.objects.filter(
            status='delivered',
            delivered_date__range=(today_start, today_end)
        ).count()
        
        # Calculate revenue from completed orders
        completed_orders = Order.objects.filter(
            status='delivered',
            delivered_date__range=(today_start, today_end)
        )
        analytics.total_revenue = sum(order.total_amount for order in completed_orders)
        
        analytics.save()
        return analytics

