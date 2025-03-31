from django import forms
from django.contrib.auth.forms import AuthenticationForm
from customer.models import User, Launderer, CustomerSupport
from .models import LaundererVerification, AdminSupportResponse

class AdminLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))
    
    def confirm_login_allowed(self, user):
        if user.user_type != 'admin':
            raise forms.ValidationError("You don't have permission to access the admin portal.", code='no_admin_access')
        super().confirm_login_allowed(user)

class LaundererVerificationForm(forms.ModelForm):
    rejection_reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        help_text="Required only if rejecting the application"
    )
    
    class Meta:
        model = LaundererVerification
        fields = ['rejection_reason']

class AdminSupportResponseForm(forms.ModelForm):
    class Meta:
        model = AdminSupportResponse
        fields = ['response_text']
        widgets = {
            'response_text': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Type your reply here...'}),
        }

class AnalyticsFilterForm(forms.Form):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True
    )
    report_type = forms.ChoiceField(
        choices=[
            ('laundromats_registered', 'Laundromats Registered'),
            ('customers_registered', 'Customers Registered'),
            ('orders_placed', 'Orders Placed'),
            ('revenue', 'Revenue'),
            ('all', 'All Data')
        ],
        required=True
    )

