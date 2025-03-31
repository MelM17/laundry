from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid

class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('customer', 'Customer'),
        ('launderer', 'Launderer'),
        ('admin', 'Admin'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)
    phone = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    
    # Delivery information
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    delivery_instructions = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.username} ({self.user_type})"

class Launderer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='launderer_profile')
    business_name = models.CharField(max_length=100)
    is_available = models.BooleanField(default=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    is_verified = models.BooleanField(default=False)
    gstin = models.CharField(max_length=15, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    years_of_experience = models.PositiveIntegerField(default=0)
    is_open = models.BooleanField(default=True)
    
    # Delivery information
    provides_delivery = models.BooleanField(default=True, help_text="Whether this launderer provides delivery services")
    delivery_radius = models.PositiveIntegerField(default=5, help_text="Maximum delivery radius in kilometers")
    base_delivery_charge = models.DecimalField(max_digits=6, decimal_places=2, default=30.00)
    per_km_charge = models.DecimalField(max_digits=6, decimal_places=2, default=10.00)
    min_order_free_delivery = models.DecimalField(max_digits=8, decimal_places=2, default=500.00, help_text="Minimum order amount for free delivery")
    
    # Service capacity
    max_orders_per_day = models.PositiveIntegerField(default=20, help_text="Maximum number of orders this launderer can handle per day")
    
    def __str__(self):
        return self.business_name

class ClothType(models.Model):
    name = models.CharField(max_length=50)
    
    def __str__(self):
        return self.name

class ClothItem(models.Model):
    launderer = models.ForeignKey(Launderer, on_delete=models.CASCADE, related_name='cloth_items')
    cloth_type = models.ForeignKey(ClothType, on_delete=models.CASCADE)
    cloth_name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    service_type = models.CharField(max_length=20, blank=True, null=True, help_text="Specific service type this item is available for")
    
    def __str__(self):
        return f"{self.cloth_name} - {self.launderer.business_name}"

class CustomerAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=50, default="Additional Address")
    address = models.TextField()
    pincode = models.CharField(max_length=10)
    instructions = models.TextField(blank=True, null=True)
    is_default = models.BooleanField(default=False)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.label} - {self.user.username}"
    
    def save(self, *args, **kwargs):
        if self.is_default:
            # Set all other addresses of this user to not default
            CustomerAddress.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending_acceptance', 'Pending Acceptance'),
        ('confirmed', 'Confirmed'),
        ('picked_up', 'Picked Up'),
        ('processing', 'Processing'),
        ('ready', 'Ready for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
    ]

    PAYMENT_CHOICES = (
        ('upi', 'UPI'),
        ('cash', 'Cash on Delivery'),
    )

    SERVICE_CHOICES = (
        ('washing', 'Washing'),
        ('dry_cleaning', 'Dry Cleaning'),
        ('ironing', 'Ironing'),
        ('full_service', 'Full Service'),
    )

    PICKUP_DELIVERY_CHOICES = (
        ('pickup', 'Pickup'),
        ('drop_off', 'Drop Off'),
        ('both', 'Both'),
    )

    TIME_SLOT_CHOICES = (
        ('morning', 'Morning (8 AM - 12 PM)'),
        ('afternoon', 'Afternoon (12 PM - 4 PM)'),
        ('evening', 'Evening (4 PM - 8 PM)'),
    )

    order_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    launderer = models.ForeignKey(Launderer, on_delete=models.CASCADE, related_name='orders')
    service_type = models.CharField(max_length=20, choices=SERVICE_CHOICES)
    pickup_delivery = models.CharField(max_length=10, choices=PICKUP_DELIVERY_CHOICES)
    pickup_date = models.DateField()
    pickup_slot = models.CharField(max_length=10, choices=TIME_SLOT_CHOICES)
    delivery_date = models.DateField(null=True, blank=True)
    delivery_slot = models.CharField(max_length=10, choices=TIME_SLOT_CHOICES, null=True, blank=True)
    special_instructions = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_acceptance')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_charge = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    distance = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, help_text="Distance in kilometers")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    delivered_date = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    estimated_completion_time = models.DateTimeField(null=True, blank=True, help_text="Estimated time when the order will be completed")
    
    # New fields
    laundry_image = models.ImageField(upload_to='laundry_images/', null=True, blank=True)
    delivery_address = models.TextField(blank=True, null=True)
    delivery_pincode = models.CharField(max_length=10, blank=True, null=True)
    delivery_instructions = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Order {self.order_id} - {self.customer.username}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    cloth_item = models.ForeignKey(ClothItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"{self.quantity} x {self.cloth_item.cloth_name}"

class Review(models.Model):
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    launderer = models.ForeignKey(Launderer, on_delete=models.CASCADE, related_name='reviews')
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='review', null=True, blank=True)
    rating = models.PositiveSmallIntegerField()  # 1-5 stars
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Review by {self.customer.username} for {self.launderer.business_name}"

class CustomerSupport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_queries')
    query = models.TextField()
    response = models.TextField(null=True, blank=True)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Query by {self.user.username} - {self.is_resolved}"

# Add a new model for contact messages from unregistered users
class ContactMessage(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('replied', 'Replied'),
        ('closed', 'Closed'),
    )
    
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_registered_user = models.BooleanField(default=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='contact_messages')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    admin_response = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Contact from {self.name} - {self.subject}"

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('order_status', 'Order Status Change'),
        ('new_order', 'New Order'),
        ('message', 'Message'),
        ('system', 'System Notification'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=100)
    message = models.TextField()
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.notification_type} for {self.user.username}: {self.title}"

