from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from customer.models import User, Launderer, ClothItem, ClothType, Order, CustomerSupport
from .models import LaundererService, LaundererWorkingHour, LaundererPaymentMethod

class LaundererRegistrationForm(UserCreationForm):
  name = forms.CharField(max_length=100, required=True)
  phone = forms.CharField(max_length=15, required=True)
  business_name = forms.CharField(max_length=100, required=True)
  address = forms.CharField(widget=forms.Textarea, required=True)
  gstin = forms.CharField(max_length=15, required=False)
  pincode = forms.CharField(max_length=10, required=True)
  profile_pic = forms.ImageField(required=False)
  upi_id = forms.CharField(max_length=50, required=False, help_text="Enter your UPI ID for payments")
  
  # Delivery information
  provides_delivery = forms.BooleanField(
      initial=True, 
      required=False,
      help_text="Check if you provide delivery services",
      widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
  )
  delivery_radius = forms.IntegerField(
      min_value=1, 
      max_value=50, 
      initial=5, 
      help_text="Maximum delivery radius in kilometers",
      widget=forms.NumberInput(attrs={'class': 'form-control'})
  )
  base_delivery_charge = forms.DecimalField(
      max_digits=6, 
      decimal_places=2, 
      initial=30.00,
      widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
  )
  per_km_charge = forms.DecimalField(
      max_digits=6, 
      decimal_places=2, 
      initial=10.00,
      widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
  )
  min_order_free_delivery = forms.DecimalField(
      max_digits=8, 
      decimal_places=2, 
      initial=500.00,
      help_text="Minimum order amount for free delivery",
      widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
  )
  
  class Meta:
      model = User
      fields = ['name', 'phone', 'business_name', 'address', 'gstin', 'pincode', 
                'username', 'email', 'password1', 'password2', 'profile_pic', 'upi_id',
                'provides_delivery', 'delivery_radius', 'base_delivery_charge', 
                'per_km_charge', 'min_order_free_delivery']
  
  def clean_email(self):
      email = self.cleaned_data.get('email')
      if User.objects.filter(email=email).exists():
          raise ValidationError("Email already in use")
      return email
  
  def save(self, commit=True):
      user = super().save(commit=False)
      user.user_type = 'launderer'
      user.phone = self.cleaned_data.get('phone')
      user.address = self.cleaned_data.get('address')
      user.pincode = self.cleaned_data.get('pincode')
      
      if self.cleaned_data.get('profile_pic'):
          user.profile_pic = self.cleaned_data.get('profile_pic')
      
      if commit:
          user.save()
          
          # Create launderer profile
          launderer = Launderer.objects.create(
              user=user,
              business_name=self.cleaned_data.get('business_name'),
              gstin=self.cleaned_data.get('gstin'),
              is_verified=False,  # Requires admin approval
              provides_delivery=self.cleaned_data.get('provides_delivery'),
              delivery_radius=self.cleaned_data.get('delivery_radius'),
              base_delivery_charge=self.cleaned_data.get('base_delivery_charge'),
              per_km_charge=self.cleaned_data.get('per_km_charge'),
              min_order_free_delivery=self.cleaned_data.get('min_order_free_delivery')
          )
          
          # Create payment method if UPI ID provided
          upi_id = self.cleaned_data.get('upi_id')
          if upi_id:
              LaundererPaymentMethod.objects.create(
                  launderer=launderer,
                  payment_type='upi',
                  upi_id=upi_id,
                  is_primary=True
              )
          
          # Create default working hours
          for day in range(7):
              is_closed = day in [5, 6]  # Closed on weekends by default
              LaundererWorkingHour.objects.create(
                  launderer=launderer,
                  day=day,
                  open_time='09:00:00',
                  close_time='18:00:00',
                  is_closed=is_closed
              )
          
          # Create verification record in admin portal
          from admin_portal.models import LaundererVerification
          LaundererVerification.objects.create(launderer=launderer, status='pending')
          
      return user

class LaundererLoginForm(AuthenticationForm):
  username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}))
  password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))
  
  def confirm_login_allowed(self, user):
      if user.user_type != 'launderer':
          raise forms.ValidationError("This account is not a launderer account.", code='invalid_login')
      super().confirm_login_allowed(user)

# Update the ClothItemForm to include service_type field
class ClothItemForm(forms.Form):
    cloth_type = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-control'}))
    cloth_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    service_type = forms.ChoiceField(
        choices=[
            ('', 'All Services'),
            ('washing', 'Washing'),
            ('dry_cleaning', 'Dry Cleaning'),
            ('ironing', 'Ironing'),
            ('full_service', 'Full Service')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    price = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        widget=forms.NumberInput(attrs={'min': '0', 'step': '0.01', 'class': 'form-control'})
    )

class LaundererServiceForm(forms.ModelForm):
  class Meta:
      model = LaundererService
      fields = ['service_name', 'description', 'price', 'is_active']
      widgets = {
          'service_name': forms.TextInput(attrs={'class': 'form-control'}),
          'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
          'price': forms.NumberInput(attrs={'min': '0', 'step': '0.01', 'class': 'form-control'}),
          'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
      }

class LaundererWorkingHourForm(forms.ModelForm):
  class Meta:
      model = LaundererWorkingHour
      fields = ['day', 'open_time', 'close_time', 'is_closed']
      widgets = {
          'day': forms.Select(attrs={'class': 'form-control'}),
          'open_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
          'close_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
          'is_closed': forms.CheckboxInput(attrs={'class': 'form-check-input'})
      }

class LaundererPaymentMethodForm(forms.ModelForm):
  class Meta:
      model = LaundererPaymentMethod
      fields = ['payment_type', 'upi_id', 'is_primary']
      widgets = {
          'payment_type': forms.Select(attrs={'class': 'form-control', 'onchange': 'toggleUpiField(this.value)'}),
          'upi_id': forms.TextInput(attrs={'class': 'form-control'}),
          'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'})
      }

class OrderStatusUpdateForm(forms.Form):
  STATUS_CHOICES = (
      ('confirmed', 'Confirm Order'),
      ('picked_up', 'Mark as Picked Up'),
      ('processing', 'Mark as Processing'),
      ('ready', 'Mark as Ready'),
      ('delivered', 'Mark as Delivered'),
      ('rejected', 'Reject Order'),
  )
  
  status = forms.ChoiceField(choices=STATUS_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
  notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}), required=False)
  rejection_reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}), required=False)
  
  def clean(self):
      cleaned_data = super().clean()
      status = cleaned_data.get('status')
      rejection_reason = cleaned_data.get('rejection_reason')
      
      if status == 'rejected' and not rejection_reason:
          raise forms.ValidationError("Please provide a reason for rejection.")
      
      return cleaned_data

class LaundererProfileForm(forms.ModelForm):
  name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
  phone = forms.CharField(max_length=15, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
  address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}), required=True)
  pincode = forms.CharField(max_length=10, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
  profile_pic = forms.ImageField(required=False, widget=forms.FileInput(attrs={'class': 'form-control'}))
  
  # Delivery information
  provides_delivery = forms.BooleanField(
      required=False,
      help_text="Check if you provide delivery services",
      widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'provides_delivery'})
  )
  delivery_radius = forms.IntegerField(
      min_value=1, 
      max_value=50, 
      help_text="Maximum delivery radius in kilometers",
      widget=forms.NumberInput(attrs={'class': 'form-control'})
  )
  base_delivery_charge = forms.DecimalField(
      max_digits=6, 
      decimal_places=2,
      widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
  )
  per_km_charge = forms.DecimalField(
      max_digits=6, 
      decimal_places=2,
      widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
  )
  min_order_free_delivery = forms.DecimalField(
      max_digits=8, 
      decimal_places=2,
      help_text="Minimum order amount for free delivery",
      widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
  )
  
  class Meta:
      model = Launderer
      fields = [
          'business_name', 'gstin', 'description', 'years_of_experience', 'is_available',
          'provides_delivery', 'delivery_radius', 'base_delivery_charge', 'per_km_charge', 'min_order_free_delivery'
      ]
      widgets = {
          'business_name': forms.TextInput(attrs={'class': 'form-control'}),
          'gstin': forms.TextInput(attrs={'class': 'form-control'}),
          'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
          'years_of_experience': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
          'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input'})
      }
  
  def __init__(self, *args, **kwargs):
      user = kwargs.pop('user', None)
      super().__init__(*args, **kwargs)
      
      if user:
          self.fields['name'].initial = user.get_full_name() or user.username
          self.fields['phone'].initial = user.phone
          self.fields['address'].initial = user.address
          self.fields['pincode'].initial = user.pincode
  
  def save(self, user=None, commit=True):
      launderer = super().save(commit=False)
      
      if user:
          user.first_name = self.cleaned_data.get('name').split()[0]
          user.last_name = ' '.join(self.cleaned_data.get('name').split()[1:]) if len(self.cleaned_data.get('name').split()) > 1 else ''
          user.phone = self.cleaned_data.get('phone')
          user.address = self.cleaned_data.get('address')
          user.pincode = self.cleaned_data.get('pincode')
          
          if self.cleaned_data.get('profile_pic'):
              user.profile_pic = self.cleaned_data.get('profile_pic')
          
          if commit:
              user.save()
      
      if commit:
          launderer.save()
      
      return launderer

class LaundererSupportForm(forms.ModelForm):
  class Meta:
      model = CustomerSupport
      fields = ['query']
      widgets = {
          'query': forms.Textarea(attrs={'rows': 5, 'class': 'form-control', 'placeholder': 'Enter your query here...'})
      }
      labels = {
          'query': 'Your Query'
      }

