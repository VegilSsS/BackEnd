from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class ActivityType(models.TextChoices):
    TAREA = "TAREA", "Tarea"
    EXAMEN = "EXAMEN", "Examen"
    PROYECTO = "PROYECTO", "Proyecto"
    LECTURA = "LECTURA", "Lectura"
    OTRO = "OTRO", "Otro"


class SubtaskStatus(models.TextChoices):
    PENDING = "PENDING", "Pendiente"
    DONE = "DONE", "Hecha"
    POSTPONED = "POSTPONED", "Pospuesta"


class Activity(models.Model):
    """US-01 / US-03: actividad evaluativa creada por el estudiante."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activities",
        null=True,
        blank=True,
        help_text="Nulo mientras no haya autenticación real (Sprint 0-1, US-11).",
    )
    title = models.CharField(max_length=200)
    course = models.CharField(max_length=120, blank=True, default="")
    type = models.CharField(max_length=20, choices=ActivityType.choices, default=ActivityType.TAREA)
    due_date = models.DateField()
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date", "title"]

    def __str__(self):
        return self.title

    @property
    def subtasks_total(self):
        return self.subtasks.count()

    @property
    def subtasks_done(self):
        return self.subtasks.filter(status=SubtaskStatus.DONE).count()

    @property
    def progress_percent(self):
        total = self.subtasks_total
        if total == 0:
            return 0
        return round((self.subtasks_done / total) * 100)


class Subtask(models.Model):
    """US-02 / US-03 / US-06 / US-09: unidad de trabajo planificable de una actividad."""

    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="subtasks")
    title = models.CharField(max_length=200)
    target_date = models.DateField()
    estimated_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0.25)],
        help_text="Debe ser mayor a 0 (US-02, Escenario 2).",
    )
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=SubtaskStatus.choices, default=SubtaskStatus.PENDING)
    postpone_note = models.TextField(blank=True, default="")
    done_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["target_date", "estimated_hours"]

    def __str__(self):
        return f"{self.title} ({self.activity.title})"


class DailyCapacity(models.Model):
    """US-12: límite diario de horas configurable por usuario (o demo)."""

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_capacity",
        null=True,
        blank=True,
    )
    daily_limit_hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=6,
        validators=[MinValueValidator(1), MaxValueValidator(16)],
    )

    def __str__(self):
        return f"Límite {self.daily_limit_hours}h — {self.owner or 'demo'}"
