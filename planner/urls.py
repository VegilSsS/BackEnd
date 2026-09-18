from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("activities", views.ActivityViewSet, basename="activity")

urlpatterns = router.urls + [
    path(
        "activities/<int:activity_id>/subtasks/",
        views.ActivitySubtaskListView.as_view(),
        name="activity-subtasks",
    ),
    path(
        "activities/<int:activity_id>/progress/",
        views.ActivityProgressView.as_view(),
        name="activity-progress",
    ),
    path("subtasks/<int:pk>/", views.SubtaskDetailView.as_view(), name="subtask-detail"),
    path("today/", views.TodayView.as_view(), name="today"),
    path("conflicts/overload/", views.OverloadCheckView.as_view(), name="overload-check"),
    path("capacity/", views.DailyCapacityView.as_view(), name="capacity"),
]
