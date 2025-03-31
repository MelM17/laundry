from django.db import models
from django.utils import timezone
from customer.models import User, Launderer, Order, Notification

class LaundererService(models.Model):
    launderer = models.ForeignKey(Launderer, on_delete=models.CASCADE, related_name='services')
    service_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.service_name} - {self.launderer.business_name}"

class LaundererWorkingHour(models.Model):
    DAY_CHOICES = (
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    )
    
    launderer = models.ForeignKey(Launderer, on_delete=models.CASCADE, related_name='working_hours')
    day = models.PositiveSmallIntegerField(choices=DAY_CHOICES)
    open_time = models.TimeField()
    close_time = models.TimeField()
    is_closed = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('launderer', 'day')
    
    def __str__(self):
        return f"{self.get_day_display()} - {self.launderer.business_name}"

class LaundererPaymentMethod(models.Model):
    PAYMENT_TYPE_CHOICES = (
        ('upi', 'UPI'),
        ('cash', 'Cash on Delivery'),
        ('card', 'Credit/Debit Card'),
        ('netbanking', 'Net Banking'),
    )
    
    launderer = models.ForeignKey(Launderer, on_delete=models.CASCADE, related_name='payment_methods')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    upi_id = models.CharField(max_length=50, blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    
    # Card payment details (if payment_type is 'card')
    card_name = models.CharField(max_length=100, blank=True, null=True, help_text="Name on the card")
    card_number_last4 = models.CharField(max_length=4, blank=True, null=True, help_text="Last 4 digits of card")
    card_expiry = models.CharField(max_length=7, blank=True, null=True, help_text="MM/YYYY format")
    
    # Bank details (if payment_type is 'netbanking')
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    account_number_last4 = models.CharField(max_length=4, blank=True, null=True, help_text="Last 4 digits of account")
    
    class Meta:
        unique_together = ('launderer', 'payment_type')
    
    def save(self, *args, **kwargs):
        if self.is_primary:
            # Set all other payment methods of this launderer to not primary
            LaundererPaymentMethod.objects.filter(launderer=self.launderer, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.get_payment_type_display()} - {self.launderer.business_name}"

class LaundererOrderStatus(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_updates')
    status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES)
    notes = models.TextField(blank=True, null=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='status_updates')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Status update for Order {self.order.order_id}: {self.status}"


