from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from . import logic
from .models import Activity, Subtask, SubtaskStatus
from .serializers import (
    ActivityDetailSerializer,
    ActivitySerializer,
    DailyCapacitySerializer,
    OverloadCheckSerializer,
    SubtaskNestedSerializer,
    SubtaskSerializer,
    TodaySubtaskSerializer,
)


class ActivityViewSet(viewsets.ModelViewSet):
    """
    US-01 (crear), US-03 (editar/eliminar con confirmación la maneja el
    front-end antes de llamar a DELETE).

    GET    /api/activities/        listar (solo del actor actual)
    POST   /api/activities/        crear
    GET    /api/activities/<id>/   detalle (incluye subtareas)
    PATCH  /api/activities/<id>/   editar
    DELETE /api/activities/<id>/   eliminar (cascada a subtareas)
    """

    serializer_class = ActivitySerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        actor = logic.get_actor(self.request)
        return Activity.objects.filter(owner=actor)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ActivityDetailSerializer
        return ActivitySerializer

    def perform_create(self, serializer):
        serializer.save(owner=logic.get_actor(self.request))


class ActivitySubtaskListView(APIView):
    """
    US-02: agregar una subtarea a una actividad existente.

    GET  /api/activities/<activity_id>/subtasks/   listar subtareas
    POST /api/activities/<activity_id>/subtasks/   crear subtarea
    """

    def get(self, request, activity_id):
        activity = get_object_or_404(
            Activity, pk=activity_id, owner=logic.get_actor(request)
        )
        subtasks = activity.subtasks.all()
        return Response(SubtaskNestedSerializer(subtasks, many=True).data)

    def post(self, request, activity_id):
        activity = get_object_or_404(
            Activity, pk=activity_id, owner=logic.get_actor(request)
        )
        serializer = SubtaskNestedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(activity=activity)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SubtaskDetailView(APIView):
    """
    US-03 (editar/eliminar), US-06 (reprogramar target_date), US-09
    (marcar Hecha / Pospuesta con nota).

    GET    /api/subtasks/<id>/   detalle
    PATCH  /api/subtasks/<id>/   editar cualquier campo (parcial)
    DELETE /api/subtasks/<id>/   eliminar
    """

    def get_object(self, request, pk):
        return get_object_or_404(
            Subtask, pk=pk, activity__owner=logic.get_actor(request)
        )

    def get(self, request, pk):
        subtask = self.get_object(request, pk)
        return Response(SubtaskSerializer(subtask).data)

    def patch(self, request, pk):
        subtask = self.get_object(request, pk)
        serializer = SubtaskSerializer(subtask, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        new_status = request.data.get("status")
        if new_status == SubtaskStatus.DONE and subtask.status != SubtaskStatus.DONE:
            serializer.save(done_at=timezone.now())
        else:
            serializer.save()

        subtask.refresh_from_db()
        payload = SubtaskSerializer(subtask).data

        # Si se tocó target_date o estimated_hours, informamos si el día
        # quedó o no en conflicto (US-06 / US-08: "recalcula y confirma").
        if "target_date" in request.data or "estimated_hours" in request.data:
            conflict = logic.overload_payload(
                actor=logic.get_actor(request),
                target_date=subtask.target_date,
                extra_hours=0,  # ya está contada: la subtarea sigue existiendo
                exclude_subtask_id=None,
            )
            payload["day_load"] = conflict

        return Response(payload)

    def delete(self, request, pk):
        subtask = self.get_object(request, pk)
        subtask.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TodayView(APIView):
    """
    US-04: GET /api/today/  — agrupado en vencidas / para_hoy / proximas.
    US-05: filtros ?course=&status=
    """

    def get(self, request):
        actor = logic.get_actor(request)
        course = request.query_params.get("course")
        status_filter = request.query_params.get("status")

        grouped = logic.group_for_today(actor, course=course, status=status_filter)

        def serialize(items):
            return TodaySubtaskSerializer(items, many=True).data

        return Response(
            {
                "today": grouped["today"],
                "rule": grouped["rule"],
                "vencidas": serialize(grouped["vencidas"]),
                "para_hoy": serialize(grouped["para_hoy"]),
                "proximas": serialize(grouped["proximas"]),
            }
        )


class OverloadCheckView(APIView):
    """
    US-07: POST /api/conflicts/overload/
    Previsualiza si mover/crear una subtarea con estimated_hours en
    target_date generaría sobrecarga, ANTES de confirmar el cambio.

    Body: {"target_date": "2026-09-20", "estimated_hours": 2,
           "subtask_id": 14 (opcional, si es una subtarea existente que
           se está reprogramando, para no contarla dos veces)}
    """

    def post(self, request):
        serializer = OverloadCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        payload = logic.overload_payload(
            actor=logic.get_actor(request),
            target_date=data["target_date"],
            extra_hours=data["estimated_hours"],
            exclude_subtask_id=data.get("subtask_id"),
        )
        return Response(payload)


class ActivityProgressView(APIView):
    """US-10: GET /api/activities/<id>/progress/"""

    def get(self, request, activity_id):
        activity = get_object_or_404(
            Activity, pk=activity_id, owner=logic.get_actor(request)
        )
        return Response(
            {
                "activity_id": activity.id,
                "total": activity.subtasks_total,
                "done": activity.subtasks_done,
                "progress_percent": activity.progress_percent,
            }
        )


class DailyCapacityView(APIView):
    """
    US-12: GET/PUT /api/capacity/
    Límite diario de horas del actor actual (por defecto 6h, rango 1-16).
    """

    def get(self, request):
        capacity = logic.get_or_create_capacity(logic.get_actor(request))
        return Response(DailyCapacitySerializer(capacity).data)

    def put(self, request):
        capacity = logic.get_or_create_capacity(logic.get_actor(request))
        serializer = DailyCapacitySerializer(capacity, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
