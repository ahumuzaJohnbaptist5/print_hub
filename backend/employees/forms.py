# backend/employees/forms.py
from django import forms
from django.core.validators import MinValueValidator, MaxValueValidator
from .models import Application


class ApplicationForm(forms.ModelForm):
    """Form for submitting a job application."""
    
    class Meta:
        model = Application
        fields = [
            'first_name', 'last_name', 'email', 'phone', 'location',
            'applied_stage', 'experience_years', 'availability',
            'why_work', 'experience', 'skills',
            'attention_to_detail', 'software_proficiency',
            'printer_experience', 'quality_standards', 'customer_service',
            'resume',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none',
                'placeholder': 'First name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none',
                'placeholder': 'Last name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none',
                'placeholder': 'email@example.com'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none',
                'placeholder': '+2567XXXXXXXX'
            }),
            'location': forms.TextInput(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none',
                'placeholder': 'e.g., Kabale'
            }),
            'applied_stage': forms.Select(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none'
            }),
            'experience_years': forms.NumberInput(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none',
                'placeholder': '0',
                'min': '0'
            }),
            'availability': forms.TextInput(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none',
                'placeholder': 'e.g., Immediately, 2 weeks notice'
            }),
            'why_work': forms.Textarea(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none',
                'rows': '4',
                'placeholder': 'Why do you want to work at PrintHub?'
            }),
            'experience': forms.Textarea(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none',
                'rows': '4',
                'placeholder': 'Describe your relevant experience...'
            }),
            'skills': forms.Textarea(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none',
                'rows': '3',
                'placeholder': 'List your skills...'
            }),
            'attention_to_detail': forms.NumberInput(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none',
                'min': '1', 'max': '10',
                'placeholder': '1-10'
            }),
            'software_proficiency': forms.TextInput(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none',
                'placeholder': 'e.g., Adobe, MS Office, Google Docs'
            }),
            'printer_experience': forms.Textarea(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none',
                'rows': '3',
                'placeholder': 'Describe your printer experience...'
            }),
            'quality_standards': forms.Textarea(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none',
                'rows': '3',
                'placeholder': 'Describe your quality control knowledge...'
            }),
            'customer_service': forms.Textarea(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none',
                'rows': '3',
                'placeholder': 'Describe your customer service experience...'
            }),
            'resume': forms.FileInput(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-blue-600 file:text-white hover:file:bg-blue-700'
            }),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Application.objects.filter(email=email).exists():
            raise forms.ValidationError("An application with this email already exists.")
        return email


class ApplicationReviewForm(forms.ModelForm):
    """Form for reviewing applications (admin only)."""
    
    class Meta:
        model = Application
        fields = ['status', 'reviewer_notes']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none'
            }),
            'reviewer_notes': forms.Textarea(attrs={
                'class': 'w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none',
                'rows': '5',
                'placeholder': 'Notes about this applicant...'
            }),
        }
