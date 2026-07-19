from django import forms
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
from .models import (
    CommissionRate, PaperInventory, FinancialRecord, 
    AgentEarning, DiscountCode, MerchantSettings, Expense
)

# Reusable Tailwind classes for dark-themed inputs
DARK_INPUT_CLASSES = 'w-full px-4 py-3 bg-slate-700 border border-slate-600 text-white rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none placeholder-gray-400'
DARK_SELECT_CLASSES = 'w-full px-4 py-3 bg-slate-700 border border-slate-600 text-white rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none'
DARK_TEXTAREA_CLASSES = 'w-full px-4 py-3 bg-slate-700 border border-slate-600 text-white rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none placeholder-gray-400'
DARK_CHECKBOX_CLASSES = 'w-4 h-4 text-indigo-600 bg-slate-700 border-slate-600 rounded focus:ring-indigo-500'
DARK_FILE_CLASSES = 'w-full px-4 py-3 bg-slate-700 border border-slate-600 text-white rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-indigo-600 file:text-white hover:file:bg-indigo-700'


class CommissionRateForm(forms.ModelForm):
    """Form for creating new commission rates."""
    
    class Meta:
        model = CommissionRate
        fields = ['rate_percentage', 'description', 'is_active']
        widgets = {
            'rate_percentage': forms.NumberInput(attrs={
                'class': DARK_INPUT_CLASSES, 
                'step': '0.01', 
                'min': '0', 
                'max': '100',
                'placeholder': 'e.g., 10.00'
            }),
            'description': forms.TextInput(attrs={
                'class': DARK_INPUT_CLASSES, 
                'placeholder': 'e.g., Standard Agent Commission Rate'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': DARK_CHECKBOX_CLASSES
            }),
        }
        labels = {
            'rate_percentage': 'Commission Rate (%)',
            'description': 'Rate Description',
            'is_active': 'Activate Immediately',
        }
        help_texts = {
            'rate_percentage': 'Enter percentage between 0 and 100',
            'is_active': 'This will deactivate all other rates',
        }
    
    def clean_rate_percentage(self):
        rate = self.cleaned_data.get('rate_percentage')
        if rate and (rate < 0 or rate > 100):
            raise forms.ValidationError('Rate must be between 0 and 100%.')
        return rate


class PaperInventoryForm(forms.ModelForm):
    """Form for adding new paper inventory types."""
    
    class Meta:
        model = PaperInventory
        fields = ['paper_type', 'quantity', 'cost_per_sheet', 'low_stock_threshold']
        widgets = {
            'paper_type': forms.Select(attrs={
                'class': DARK_SELECT_CLASSES
            }),
            'quantity': forms.NumberInput(attrs={
                'class': DARK_INPUT_CLASSES,
                'min': '0',
                'placeholder': 'Initial stock quantity'
            }),
            'cost_per_sheet': forms.NumberInput(attrs={
                'class': DARK_INPUT_CLASSES, 
                'step': '0.01',
                'min': '0.01',
                'placeholder': 'Cost per sheet in UGX'
            }),
            'low_stock_threshold': forms.NumberInput(attrs={
                'class': DARK_INPUT_CLASSES,
                'min': '0',
                'placeholder': 'e.g., 500'
            }),
        }
        labels = {
            'paper_type': 'Paper Type',
            'quantity': 'Initial Quantity',
            'cost_per_sheet': 'Cost Per Sheet (UGX)',
            'low_stock_threshold': 'Low Stock Alert Threshold',
        }
        help_texts = {
            'low_stock_threshold': 'Alert when stock falls below this number',
        }


class PaperRestockForm(forms.Form):
    """Form for restocking existing paper inventory."""
    
    inventory_id = forms.IntegerField(widget=forms.HiddenInput())
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': DARK_INPUT_CLASSES,
            'min': '1',
            'placeholder': 'Quantity to add'
        }),
        label='Restock Quantity'
    )
    cost_per_sheet = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': DARK_INPUT_CLASSES,
            'step': '0.01',
            'placeholder': 'New cost per sheet (optional)'
        }),
        label='New Cost Per Sheet (Optional)'
    )


class ExpenseForm(forms.ModelForm):
    """Form for adding business expenses."""
    
    class Meta:
        model = Expense
        fields = ['category', 'amount', 'description', 'receipt']
        widgets = {
            'category': forms.Select(attrs={
                'class': DARK_SELECT_CLASSES
            }),
            'amount': forms.NumberInput(attrs={
                'class': DARK_INPUT_CLASSES, 
                'step': '0.01',
                'min': '0.01',
                'placeholder': 'Expense amount in UGX'
            }),
            'description': forms.Textarea(attrs={
                'class': DARK_TEXTAREA_CLASSES, 
                'rows': 3,
                'placeholder': 'Describe the expense (e.g., Bought 5 reams of paper, Paid rider for delivery)'
            }),
            'receipt': forms.FileInput(attrs={
                'class': DARK_FILE_CLASSES
            }),
        }
        labels = {
            'category': 'Expense Category',
            'amount': 'Amount (UGX)',
            'description': 'Description',
            'receipt': 'Receipt (Optional)',
        }
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount <= 0:
            raise forms.ValidationError('Amount must be greater than 0.')
        return amount


class DiscountCodeForm(forms.ModelForm):
    """Form for creating discount codes."""
    
    class Meta:
        model = DiscountCode
        fields = [
            'code', 'discount_type', 'discount_value', 
            'minimum_order', 'max_uses', 'valid_from', 
            'valid_until', 'description', 'is_active'
        ]
        widgets = {
            'code': forms.TextInput(attrs={
                'class': DARK_INPUT_CLASSES,
                'placeholder': 'e.g., WELCOME10',
                'style': 'text-transform: uppercase;'
            }),
            'discount_type': forms.Select(attrs={
                'class': DARK_SELECT_CLASSES
            }),
            'discount_value': forms.NumberInput(attrs={
                'class': DARK_INPUT_CLASSES,
                'step': '0.01',
                'min': '0',
                'placeholder': 'Discount value'
            }),
            'minimum_order': forms.NumberInput(attrs={
                'class': DARK_INPUT_CLASSES,
                'step': '0.01',
                'min': '0',
                'placeholder': 'Minimum order total (0 for none)'
            }),
            'max_uses': forms.NumberInput(attrs={
                'class': DARK_INPUT_CLASSES,
                'min': '0',
                'placeholder': '0 for unlimited'
            }),
            'valid_from': forms.DateTimeInput(attrs={
                'class': DARK_INPUT_CLASSES,
                'type': 'datetime-local'
            }),
            'valid_until': forms.DateTimeInput(attrs={
                'class': DARK_INPUT_CLASSES,
                'type': 'datetime-local'
            }),
            'description': forms.TextInput(attrs={
                'class': DARK_INPUT_CLASSES,
                'placeholder': 'e.g., New customer welcome discount'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': DARK_CHECKBOX_CLASSES
            }),
        }
        labels = {
            'code': 'Discount Code',
            'discount_type': 'Discount Type',
            'discount_value': 'Discount Value',
            'minimum_order': 'Minimum Order Amount (UGX)',
            'max_uses': 'Maximum Uses (0 = unlimited)',
            'valid_from': 'Valid From',
            'valid_until': 'Valid Until',
            'description': 'Description',
            'is_active': 'Active',
        }
        help_texts = {
            'code': 'Code will be automatically converted to uppercase',
            'discount_value': 'Percentage (e.g., 10) or fixed amount (e.g., 5000)',
            'max_uses': 'Set to 0 for unlimited usage',
        }
    
    def clean_code(self):
        code = self.cleaned_data.get('code')
        return code.upper() if code else code
    
    def clean(self):
        cleaned_data = super().clean()
        discount_type = cleaned_data.get('discount_type')
        discount_value = cleaned_data.get('discount_value')
        minimum_order = cleaned_data.get('minimum_order')
        valid_from = cleaned_data.get('valid_from')
        valid_until = cleaned_data.get('valid_until')
        
        if discount_type == 'percentage' and discount_value and discount_value > 100:
            self.add_error('discount_value', 'Percentage discount cannot exceed 100%.')
        
        if minimum_order and discount_value and discount_type == 'fixed' and discount_value > minimum_order:
            self.add_error('discount_value', 'Fixed discount cannot exceed minimum order amount.')
        
        if valid_from and valid_until and valid_from >= valid_until:
            self.add_error('valid_until', 'End date must be after start date.')
        
        return cleaned_data


class MerchantSettingsForm(forms.ModelForm):
    """Form for managing payment merchant settings."""
    
    class Meta:
        model = MerchantSettings
        fields = ['payment_method', 'merchant_name', 'merchant_phone', 'is_active']
        widgets = {
            'payment_method': forms.Select(attrs={
                'class': DARK_SELECT_CLASSES
            }),
            'merchant_name': forms.TextInput(attrs={
                'class': DARK_INPUT_CLASSES,
                'placeholder': 'e.g., Matovu Evaristo'
            }),
            'merchant_phone': forms.TextInput(attrs={
                'class': DARK_INPUT_CLASSES,
                'placeholder': 'e.g., 0765511075'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': DARK_CHECKBOX_CLASSES
            }),
        }
        labels = {
            'payment_method': 'Payment Method',
            'merchant_name': 'Merchant Name',
            'merchant_phone': 'Merchant Phone Number',
            'is_active': 'Active',
        }
        help_texts = {
            'merchant_phone': 'Phone number that customers will send payment to',
        }
    
    def clean_merchant_phone(self):
        phone = self.cleaned_data.get('merchant_phone')
        # Remove spaces and special characters
        phone = ''.join(c for c in phone if c.isdigit() or c == '+')
        if len(phone) < 10:
            raise forms.ValidationError('Please enter a valid phone number.')
        return phone


class AgentEarningPaymentForm(forms.Form):
    """Form for bulk paying agent earnings."""
    
    earning_ids = forms.CharField(
        widget=forms.HiddenInput(),
        required=True
    )
    payment_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': DARK_TEXTAREA_CLASSES,
            'rows': 2,
            'placeholder': 'Payment notes (optional)'
        }),
        label='Payment Notes'
    )
    
    def clean_earning_ids(self):
        ids_str = self.cleaned_data.get('earning_ids')
        try:
            ids = [int(id.strip()) for id in ids_str.split(',') if id.strip()]
            if not ids:
                raise forms.ValidationError('No earnings selected.')
            return ids
        except ValueError:
            raise forms.ValidationError('Invalid earning IDs.')


class FinancialReportForm(forms.Form):
    """Form for generating financial reports."""
    
    REPORT_TYPES = [
        ('daily', 'Daily Report'),
        ('weekly', 'Weekly Report'),
        ('monthly', 'Monthly Report'),
        ('custom', 'Custom Range'),
    ]
    
    report_type = forms.ChoiceField(
        choices=REPORT_TYPES,
        widget=forms.Select(attrs={'class': DARK_SELECT_CLASSES}),
        label='Report Type'
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': DARK_INPUT_CLASSES,
            'type': 'date'
        }),
        label='Start Date'
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': DARK_INPUT_CLASSES,
            'type': 'date'
        }),
        label='End Date'
    )
    include_expenses = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': DARK_CHECKBOX_CLASSES}),
        label='Include Expenses'
    )
    include_commissions = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': DARK_CHECKBOX_CLASSES}),
        label='Include Commissions'
    )
    group_by_station = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': DARK_CHECKBOX_CLASSES}),
        label='Group by Station'
    )


class DateFilterForm(forms.Form):
    """Reusable form for date filtering."""
    
    DATE_CHOICES = [
        ('today', 'Today'),
        ('week', 'This Week'),
        ('month', 'This Month'),
        ('year', 'This Year'),
        ('custom', 'Custom Range'),
    ]
    
    date_filter = forms.ChoiceField(
        choices=DATE_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': DARK_SELECT_CLASSES,
            'onchange': 'this.form.submit()'
        })
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': DARK_INPUT_CLASSES,
            'type': 'date'
        })
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': DARK_INPUT_CLASSES,
            'type': 'date'
        })
    )


class ExpenseFilterForm(forms.Form):
    """Form for filtering expenses."""
    
    category = forms.ChoiceField(
        required=False,
        choices=[('', 'All Categories')] + Expense.EXPENSE_CATEGORIES,
        widget=forms.Select(attrs={
            'class': DARK_SELECT_CLASSES,
            'onchange': 'this.form.submit()'
        })
    )
    date_filter = forms.ChoiceField(
        required=False,
        choices=DateFilterForm.DATE_CHOICES,
        widget=forms.Select(attrs={
            'class': DARK_SELECT_CLASSES,
            'onchange': 'this.form.submit()'
        })
    )


class AgentEarningFilterForm(forms.Form):
    """Form for filtering agent earnings."""
    
    STATUS_CHOICES = [
        ('', 'All Status'),
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]
    
    agent = forms.IntegerField(
        required=False,
        widget=forms.Select(attrs={
            'class': DARK_SELECT_CLASSES,
            'onchange': 'this.form.submit()'
        })
    )
    status = forms.ChoiceField(
        required=False,
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': DARK_SELECT_CLASSES,
            'onchange': 'this.form.submit()'
        })
    )
    date_filter = forms.ChoiceField(
        required=False,
        choices=DateFilterForm.DATE_CHOICES,
        widget=forms.Select(attrs={
            'class': DARK_SELECT_CLASSES,
            'onchange': 'this.form.submit()'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically load agents
        from django.contrib.auth import get_user_model
        User = get_user_model()
        agents = User.objects.filter(role='agent').values_list('id', 'username')
        self.fields['agent'].widget.choices = [('', 'All Agents')] + list(agents)
