from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("activities", views.ActivityViewSet, basename="activity")

from rest_framework_simplejwt.views import TokenObtainPairView

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
    path("auth/google/", views.GoogleLoginView.as_view(), name="google-auth"),
    path("auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/register/", views.RegisterView.as_view(), name="register"),
]
