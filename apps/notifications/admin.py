from django.contrib import admin
from .models import NotificationPreference, PushSubscription

@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'channel', 'is_active')
    list_filter = ('channel', 'is_active')
    search_fields = ('user__email',)


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'endpoint_preview', 'created_at')
    search_fields = ('user__email', 'endpoint')
    readonly_fields = ('created_at',)

    def endpoint_preview(self, obj):
        return obj.endpoint[:60] + "..." if len(obj.endpoint) > 60 else obj.endpoint
    endpoint_preview.short_description = "Endpoint"
