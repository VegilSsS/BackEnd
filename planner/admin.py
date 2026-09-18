from django.contrib import admin

from .models import Activity, DailyCapacity, Subtask


class SubtaskInline(admin.TabularInline):
    model = Subtask
    extra = 0


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ["title", "course", "type", "due_date", "owner", "progress_percent"]
    list_filter = ["type", "course"]
    search_fields = ["title", "course"]
    inlines = [SubtaskInline]


@admin.register(Subtask)
class SubtaskAdmin(admin.ModelAdmin):
    list_display = ["title", "activity", "target_date", "estimated_hours", "status"]
    list_filter = ["status"]
    search_fields = ["title"]


@admin.register(DailyCapacity)
class DailyCapacityAdmin(admin.ModelAdmin):
    list_display = ["owner", "daily_limit_hours"]
