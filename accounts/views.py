from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from tracker.forms import SellingUnitFormSet
from tracker.models import Product

from .forms import OnboardingForm, ProfileForm, RegisterForm
from .models import Profile


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Account created. Let us set up your business.')
        return redirect('onboarding')

    return render(request, 'accounts/register.html', {'form': form})


@login_required
def onboarding(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if profile.onboarded:
        return redirect('dashboard')

    form = OnboardingForm(request.POST or None)
    formset = SellingUnitFormSet(request.POST or None)
    unit_error = ''

    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        units = [
            f for f in formset.forms
            if f.cleaned_data and not f.cleaned_data.get('is_empty')
        ]
        if not units:
            unit_error = 'Add at least one quantity you sell (e.g. a 5 Litre bucket).'
        else:
            profile.business_name = form.cleaned_data['business_name']
            profile.phone = form.cleaned_data['phone']
            profile.onboarded = True
            profile.save(update_fields=['business_name', 'phone', 'onboarded'])

            product, _ = Product.objects.get_or_create(
                owner=request.user,
                name=form.cleaned_data['product_name'].strip(),
            )
            for unit_form in units:
                unit_form.to_selling_unit(product).save()

            messages.success(request, 'Business set up. You can record your first order now.')
            return redirect('order_create')

    return render(
        request,
        'accounts/onboarding.html',
        {'form': form, 'formset': formset, 'unit_error': unit_error},
    )


@login_required
def profile(request):
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, instance=profile_obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Business details updated.')
        return redirect('profile')

    return render(request, 'accounts/profile.html', {'form': form})
