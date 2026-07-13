from django import forms
from .models import CommissionRate, PaperInventory, FinancialRecord

class CommissionRateForm(forms.ModelForm):
    class Meta:
        model = CommissionRate
        fields = ['rate_percentage', 'description']
        widgets = {
            'rate_percentage': forms.NumberInput(attrs={'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none', 'step': '0.01', 'placeholder': '10.00'}),
            'description': forms.TextInput(attrs={'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none', 'placeholder': 'e.g., Standard Agent Rate'}),
        }

class PaperInventoryForm(forms.ModelForm):
    class Meta:
        model = PaperInventory
        fields = ['paper_type', 'quantity', 'cost_per_sheet']
        widgets = {
            'paper_type': forms.TextInput(attrs={'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none', 'placeholder': 'e.g., A4 White'}),
            'quantity': forms.NumberInput(attrs={'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none'}),
            'cost_per_sheet': forms.NumberInput(attrs={'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none', 'step': '0.01'}),
        }

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = FinancialRecord
        fields = ['amount', 'description']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none', 'step': '0.01'}),
            'description': forms.TextInput(attrs={'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none', 'placeholder': 'e.g., Bought ink, Paid rider'}),
        }
