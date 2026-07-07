from django import forms
from .models import CommissionRate, PaperInventory

class CommissionRateForm(forms.ModelForm):
    class Meta:
        model = CommissionRate
        fields = ['rate_percentage', 'description', 'is_active']
        widgets = {
            'rate_percentage': forms.NumberInput(attrs={'class': 'w-full bg-white/10 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500', 'step': '0.01'}),
            'description': forms.TextInput(attrs={'class': 'w-full bg-white/10 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class PaperInventoryForm(forms.ModelForm):
    class Meta:
        model = PaperInventory
        fields = ['paper_type', 'quantity', 'cost_per_sheet']
        widgets = {
            'paper_type': forms.TextInput(attrs={'class': 'w-full bg-white/10 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'quantity': forms.NumberInput(attrs={'class': 'w-full bg-white/10 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'cost_per_sheet': forms.NumberInput(attrs={'class': 'w-full bg-white/10 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500', 'step': '0.01'}),
        }
