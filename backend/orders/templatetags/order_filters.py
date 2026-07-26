# orders/templatetags/order_filters.py
from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiply value by arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
