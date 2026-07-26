# backend/orders/templatetags/order_filters.py
from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiply value by arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def intcomma(value):
    """Format number with commas"""
    try:
        return f"{int(float(value)):,}"
    except (ValueError, TypeError):
        return value
