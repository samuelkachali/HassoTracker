from django import forms
from django.forms import formset_factory

from .models import Batch, Order, PreparationCost, Product, SellingUnit

FIELD = 'field-input'
SELECT = 'field-input field-select'
TEXTAREA = 'field-input field-textarea'

UNIT_TYPE_CHOICES = [
    ('', 'Choose a quantity...'),
    ('litre:5', '5 Litre bucket'),
    ('litre:8', '8 Litre bucket'),
    ('litre:10', '10 Litre bucket'),
    ('litre:20', '20 Litre bucket'),
    ('kg:50', '50 kg bag'),
    ('other', 'Other (describe it)'),
]


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ('name',)
        widgets = {
            'name': forms.TextInput(
                attrs={'class': FIELD, 'placeholder': 'e.g. Irish Potatoes'}
            ),
        }


class SellingUnitForm(forms.Form):
    """A selling quantity (size) plus its current price."""

    unit_type = forms.ChoiceField(
        choices=UNIT_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': SELECT, 'data-unit-type': ''}),
    )
    label = forms.CharField(
        required=False,
        max_length=60,
        widget=forms.TextInput(
            attrs={'class': FIELD, 'placeholder': 'e.g. large bowl', 'data-unit-label': ''}
        ),
    )
    price = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={'class': FIELD, 'type': 'number', 'step': '0.01', 'min': '0', 'placeholder': 'e.g. 3000'}
        ),
    )

    def clean(self):
        cleaned = super().clean()
        unit_type = cleaned.get('unit_type')
        if not unit_type:
            cleaned['is_empty'] = True
            return cleaned
        cleaned['is_empty'] = False
        price = cleaned.get('price')
        if price is None:
            self.add_error('price', 'Enter the price for this quantity.')
        if unit_type == 'other':
            if not cleaned.get('label'):
                self.add_error('label', 'Describe this quantity.')
            cleaned['measure'] = SellingUnit.Measure.OTHER
            cleaned['size'] = None
        else:
            measure, size = unit_type.split(':')
            cleaned['measure'] = measure
            cleaned['size'] = size
        return cleaned

    def to_selling_unit(self, product):
        return SellingUnit(
            product=product,
            measure=self.cleaned_data['measure'],
            size=self.cleaned_data['size'] or None,
            label=self.cleaned_data.get('label', ''),
            current_price=self.cleaned_data['price'],
        )


SellingUnitFormSet = formset_factory(SellingUnitForm, extra=3)


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = (
            'product',
            'order_date',
            'quantity_kg',
            'order_price',
            'transport_to_market',
            'transport_from_market',
            'food_amount',
            'other_amount',
            'other_description',
            'opening_balance',
            'notes',
        )
        widgets = {
            'product': forms.Select(attrs={'class': SELECT}),
            'order_date': forms.DateInput(
                attrs={'class': FIELD, 'type': 'date'}, format='%Y-%m-%d'
            ),
            'quantity_kg': forms.NumberInput(
                attrs={'class': FIELD, 'type': 'number', 'step': '0.01', 'min': '0', 'placeholder': 'e.g. 200'}
            ),
            'order_price': forms.NumberInput(
                attrs={'class': FIELD, 'type': 'number', 'step': '0.01', 'min': '0', 'placeholder': 'e.g. 180000'}
            ),
            'transport_to_market': forms.NumberInput(
                attrs={'class': FIELD, 'type': 'number', 'step': '0.01', 'min': '0', 'placeholder': 'e.g. 8000'}
            ),
            'transport_from_market': forms.NumberInput(
                attrs={'class': FIELD, 'type': 'number', 'step': '0.01', 'min': '0', 'placeholder': 'e.g. 8000'}
            ),
            'food_amount': forms.NumberInput(
                attrs={'class': FIELD, 'type': 'number', 'step': '0.01', 'min': '0', 'placeholder': '0'}
            ),
            'other_amount': forms.NumberInput(
                attrs={'class': FIELD, 'type': 'number', 'step': '0.01', 'min': '0', 'placeholder': '0'}
            ),
            'other_description': forms.TextInput(
                attrs={'class': FIELD, 'placeholder': 'e.g. loading fees'}
            ),
            'opening_balance': forms.NumberInput(
                attrs={'class': FIELD, 'type': 'number', 'step': '0.01', 'min': '0', 'placeholder': 'money you had'}
            ),
            'notes': forms.Textarea(
                attrs={'class': TEXTAREA, 'rows': 2, 'placeholder': 'optional notes'}
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['product'].queryset = Product.objects.filter(owner=user)
        self.fields['quantity_kg'].label = 'KGs ordered'
        self.fields['order_price'].label = 'Price for total order'


class BatchForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ('received_date', 'notes')
        widgets = {
            'received_date': forms.DateInput(
                attrs={'class': FIELD, 'type': 'date'}, format='%Y-%m-%d'
            ),
            'notes': forms.Textarea(
                attrs={'class': TEXTAREA, 'rows': 2, 'placeholder': 'e.g. 2 bags were lighter'}
            ),
        }


class PreparationCostForm(forms.ModelForm):
    class Meta:
        model = PreparationCost
        fields = ('description', 'amount', 'spent_at')
        widgets = {
            'description': forms.TextInput(
                attrs={'class': FIELD, 'placeholder': 'e.g. Washing and sorting'}
            ),
            'amount': forms.NumberInput(
                attrs={'class': FIELD, 'type': 'number', 'step': '0.01', 'min': '0'}
            ),
            'spent_at': forms.DateInput(
                attrs={'class': FIELD, 'type': 'date'}, format='%Y-%m-%d'
            ),
        }
