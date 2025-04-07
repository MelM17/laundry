from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordResetForm, SetPasswordForm
from .models import User, Order, Review, CustomerSupport
from django.utils import timezone

class CustomerRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=15, required=True)
    address = forms.CharField(widget=forms.Textarea, required=True)
    pincode = forms.CharField(max_length=10, required=True)
    # latitude = forms.FloatField(required=False, widget=forms.HiddenInput())
    # longitude = forms.FloatField(required=False, widget=forms.HiddenInput())
    # delivery_instructions = forms.CharField(
    #     widget=forms.Textarea(attrs={'rows': 3}), 
    #     required=False,
    #     help_text="Any special instructions for delivery (e.g., landmark, gate code, etc.)"
    # )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'phone', 'address', 'pincode', 'password1', 'password2', 
                #  'latitude', 'longitude', 'delivery_instructions'
                 ]
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'customer'
        if commit:
            user.save()
        return user

class CustomerProfileUpdateForm(forms.ModelForm):
    # delivery_instructions = forms.CharField(
    #     widget=forms.Textarea(attrs={'rows': 3}), 
    #     required=False,
    #     help_text="Any special instructions for delivery (e.g., landmark, gate code, etc.)"
    # )
    # latitude = forms.FloatField(required=False, widget=forms.HiddenInput())
    # longitude = forms.FloatField(required=False, widget=forms.HiddenInput())
    
    class Meta:
        model = User
        fields = ['username', 'email', 'phone', 'address', 'pincode', 'profile_pic', 
                #  'latitude', 'longitude', 'delivery_instructions'
                 ]
class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['service_type', 'pickup_delivery', 'pickup_date', 'pickup_slot', 
                  'delivery_date', 'special_instructions', 'payment_method', 'launderer']
        widgets = {
            'pickup_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'delivery_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'special_instructions': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'pickup_slot': forms.Select(attrs={'class': 'form-control'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'service_type': forms.Select(attrs={'class': 'form-control'}),
            'pickup_delivery': forms.Select(attrs={'class': 'form-control'}),
            'launderer': forms.HiddenInput(),  # Hide this field as it will be set programmatically
        }
    
    def clean(self):
        cleaned_data = super().clean()
        pickup_date = cleaned_data.get('pickup_date')
        delivery_date = cleaned_data.get('delivery_date')
        
        # Validate that pickup date is not in the past
        if pickup_date and pickup_date < timezone.now().date():
            self.add_error('pickup_date', 'Pickup date cannot be in the past')
        
        # Validate that delivery date is after pickup date
        if pickup_date and delivery_date and delivery_date < pickup_date:
            self.add_error('delivery_date', 'Delivery date must be after pickup date')
        
        return cleaned_data



class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 4}),
        }

class CustomerSupportForm(forms.ModelForm):
    class Meta:
        model = CustomerSupport
        fields = ['query']
        widgets = {
            'query': forms.Textarea(attrs={'rows': 4}),
        }

class CustomPasswordResetForm(PasswordResetForm):
    user_type = forms.ChoiceField(choices=User.USER_TYPE_CHOICES)
    
class CustomSetPasswordForm(SetPasswordForm):
    pass

