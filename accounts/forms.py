from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Profile

INPUT_CLASS = 'field-input'


class RegisterForm(UserCreationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'e.g. chikondi'}),
        help_text='',
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': INPUT_CLASS, 'placeholder': 'optional@email.com'}),
    )

    class Meta:
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].help_text = ''
        self.fields['password1'].widget.attrs.update({
            'class': INPUT_CLASS,
            'placeholder': 'At least 8 characters',
        })
        self.fields['password2'].help_text = ''
        self.fields['password2'].widget.attrs.update({
            'class': INPUT_CLASS,
            'placeholder': 'Repeat the password',
        })


class OnboardingForm(forms.Form):
    business_name = forms.CharField(
        max_length=150,
        label='Business name',
        widget=forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'e.g. Chimwemwe Produce'}),
    )
    phone = forms.CharField(
        max_length=30,
        required=False,
        label='Phone (optional)',
        widget=forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'e.g. 099 123 4567'}),
    )
    product_name = forms.CharField(
        max_length=150,
        label='What do you sell?',
        initial='Irish Potatoes',
        widget=forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'e.g. Irish Potatoes'}),
    )


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ('business_name', 'phone')
        widgets = {
            'business_name': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'phone': forms.TextInput(attrs={'class': INPUT_CLASS}),
        }
