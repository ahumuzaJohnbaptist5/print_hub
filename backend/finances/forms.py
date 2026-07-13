from django import forms
from .models import CommissionRate, PaperInventory, FinancialRecord

# Reusable Tailwind classes for dark-themed inputs
DARK_INPUT_CLASSES = 'w-full px-4 py-3 bg-slate-700 border border-slate-600 text-white rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none placeholder-gray-400'

class CommissionRateForm(forms.ModelForm):
    class Meta:
        model = CommissionRate
        fields = ['rate_percentage', 'description']
        widgets = {
            'rate_percentage': forms.NumberInput(attrs={'class': DARK_INPUT_CLASSES, 'step': '0.01', 'placeholder': '10.00'}),
            'description': forms.TextInput(attrs={'class': DARK_INPUT_CLASSES, 'placeholder': 'e.g., Standard Agent Rate'}),
        }

class PaperInventoryForm(forms.ModelForm):
    class Meta:
        model = PaperInventory
        fields = ['paper_type', 'quantity', 'cost_per_sheet']
        widgets = {
            'paper_type': forms.TextInput(attrs={'class': DARK_INPUT_CLASSES, 'placeholder': 'e.g., A4 White'}),
            'quantity': forms.NumberInput(attrs={'class': DARK_INPUT_CLASSES}),
            'cost_per_sheet': forms.NumberInput(attrs={'class': DARK_INPUT_CLASSES, 'step': '0.01'}),
        }

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = FinancialRecord
        fields = ['amount', 'description']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': DARK_INPUT_CLASSES, 'step': '0.01'}),
            'description': forms.TextInput(attrs={'class': DARK_INPUT_CLASSES, 'placeholder': 'e.g., Bought ink, Paid rider'}),
        }
