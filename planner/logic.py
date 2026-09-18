"""
Lógica de negocio compartida entre vistas.

Mantiene fuera de views.py las reglas que tienen criterios de aceptación
explícitos en el backlog, para que sean fáciles de ubicar y testear:

- get_actor            -> US-11 (demo en Sprint 0-1, usuario real desde Sprint 2)
- get_or_create_capacity -> US-12
- planned_hours_for_day -> US-07 (cálculo de horas planificadas por día)
- overload_payload      -> US-07 (payload conflict/planned/limit/exceeds_by)
- group_for_today       -> US-04 / US-05 (agrupación, orden y filtros)
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.db.models import Sum

from .models import DailyCapacity, Subtask, SubtaskStatus

User = get_user_model()

ORDER_RULE_TEXT = (
    "Ordenadas por fecha objetivo y prioridad temporal: vencidas → para hoy → "
    "próximas. Dentro de cada grupo, primero la fecha más urgente y, en caso de "
    "empate, la subtarea con menos horas estimadas."
)


def get_actor(request):
    """
    US-11: mientras no haya login real, todas las operaciones se asocian a un
    usuario 'demo' fijo, para no bloquear el resto del backlog (Sprint 0-1).
    Cuando el front-end mande un usuario autenticado, se usa ese.
    """
    if request.user and request.user.is_authenticated:
        return request.user
    demo_user, _ = User.objects.get_or_create(
        username="demo",
        defaults={"first_name": "Usuario", "last_name": "Demo"},
    )
    return demo_user


def get_or_create_capacity(actor):
    capacity, _ = DailyCapacity.objects.get_or_create(
        owner=actor, defaults={"daily_limit_hours": 6}
    )
    return capacity


def planned_hours_for_day(actor, target_date, exclude_subtask_id=None):
    """
    US-07: suma de estimated_hours para subtareas NO 'DONE' de ese usuario en
    ese día, excluyendo opcionalmente la subtarea que se está reprogramando
    (para poder recalcular su nueva posición sin contarla dos veces).
    """
    qs = Subtask.objects.filter(
        activity__owner=actor,
        target_date=target_date,
    ).exclude(status=SubtaskStatus.DONE)
    if exclude_subtask_id is not None:
        qs = qs.exclude(pk=exclude_subtask_id)
    total = qs.aggregate(total=Sum("estimated_hours"))["total"] or 0
    return total


def overload_payload(actor, target_date, extra_hours=0, exclude_subtask_id=None):
    """
    US-07: arma el payload {planned_hours, limit_hours, exceeds_by, conflict}
    para un día hipotético, sumando extra_hours (la subtarea que se quiere
    mover/crear ahí) a lo ya planificado.
    """
    capacity = get_or_create_capacity(actor)
    limit_hours = capacity.daily_limit_hours
    already_planned = planned_hours_for_day(actor, target_date, exclude_subtask_id)
    planned_hours = already_planned + extra_hours
    exceeds_by = max(planned_hours - limit_hours, 0)
    return {
        "target_date": target_date,
        "planned_hours": planned_hours,
        "limit_hours": limit_hours,
        "exceeds_by": exceeds_by,
        "conflict": planned_hours > limit_hours,
    }


def group_for_today(actor, course=None, status=None, today=None):
    """
    US-04: agrupa en Vencidas / Para hoy / Próximas, ordenadas por
    target_date y desempatadas por estimated_hours (ambos ascendentes).

    US-05: filtros opcionales por curso (Activity.course) y por estado
    (Subtask.status). Sin filtro de estado, se excluyen las 'DONE' por
    defecto (US-04, Escenario 1); pasar status explícito lo anula, para
    poder ver hechas o pospuestas a propósito.
    """
    today = today or date.today()
    qs = Subtask.objects.filter(activity__owner=actor).select_related("activity")

    if course:
        qs = qs.filter(activity__course__iexact=course)

    if status:
        qs = qs.filter(status=status.upper())
    else:
        qs = qs.exclude(status=SubtaskStatus.DONE)

    qs = qs.order_by("target_date", "estimated_hours")

    vencidas, para_hoy, proximas = [], [], []
    for subtask in qs:
        if subtask.target_date < today:
            vencidas.append(subtask)
        elif subtask.target_date == today:
            para_hoy.append(subtask)
        else:
            proximas.append(subtask)

    return {
        "rule": ORDER_RULE_TEXT,
        "today": today,
        "vencidas": vencidas,
        "para_hoy": para_hoy,
        "proximas": proximas,
    }
