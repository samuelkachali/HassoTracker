from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from unfold.admin import ModelAdmin

from .models import Profile


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    fk_name = 'user'


class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]
    list_display = ('username', 'email', 'is_staff', 'is_active')


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Profile)
class ProfileAdmin(ModelAdmin):
    list_display = ('user', 'business_name', 'phone', 'currency', 'onboarded', 'created_at')
    search_fields = ('user__username', 'business_name', 'phone')
    list_filter = ('onboarded',)
    ordering = ('user__username',)
