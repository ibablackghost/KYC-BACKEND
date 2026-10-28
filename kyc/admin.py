from django.contrib import admin

from .models import Account


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("email", "first_name", "last_name", "status", "created_at")
    search_fields = ("email", "first_name", "last_name", "session_id")
    readonly_fields = ("id", "created_at", "updated_at")
