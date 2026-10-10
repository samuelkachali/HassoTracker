from decimal import Decimal, InvalidOperation

from django import template
from django.conf import settings

register = template.Library()


@register.filter
def money(value):
    """Format an amount as MWK 45,000 (decimals only when they exist)."""
    if value in (None, ''):
        value = 0
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        return value
    if amount == amount.to_integral():
        formatted = f'{amount:,.0f}'
    else:
        formatted = f'{amount:,.2f}'
    return f'{settings.CURRENCY} {formatted}'


@register.filter
def bucket_size(value):
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        return value
    return f'{amount.normalize()}L'


@register.filter(name='abs')
def absolute(value):
    try:
        return abs(Decimal(value))
    except (InvalidOperation, ValueError, TypeError):
        return value

