from django.conf import settings
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    business_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    currency = models.CharField(max_length=8, default='MWK')
    onboarded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['user__username']

    def __str__(self):
        return self.business_name or self.user.get_username()

    @property
    def display_name(self):
        return self.business_name or self.user.get_username()
