from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'phone_number', 'updated_at')
    search_fields = ('user__username', 'user__email', 'phone_number', 'full_name')
    list_filter = ('created_at', 'updated_at')
