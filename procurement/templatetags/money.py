from decimal import Decimal, InvalidOperation

from django import template
from django.utils.safestring import mark_safe


register = template.Library()


@register.filter
def money(value):
    """Render a ruble amount with grouped thousands and non-breaking spaces."""
    if value is None or value == "":
        return "-"
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return value
    decimals = "" if amount == amount.quantize(Decimal("1")) else f",{amount:.2f}".split(".", 1)[1]
    if decimals:
        decimals = f",{decimals}"
    whole = f"{int(amount):,}".replace(",", "\u00a0")
    return mark_safe(f'<span class="money-value">{whole}{decimals}\u00a0₽</span>')
