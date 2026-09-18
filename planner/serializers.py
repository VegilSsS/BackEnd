from rest_framework import serializers

from .models import Activity, DailyCapacity, Subtask


class SubtaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtask
        fields = [
            "id",
            "activity",
            "title",
            "target_date",
            "estimated_hours",
            "description",
            "status",
            "postpone_note",
            "done_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "done_at", "created_at", "updated_at"]

    def validate_estimated_hours(self, value):
        # US-02, Escenario 2: "horas estimadas en 0" debe rechazarse con
        # mensaje claro. El validador del modelo ya exige > 0.25, esto solo
        # da un mensaje más amable que el genérico de DecimalField.
        if value <= 0:
            raise serializers.ValidationError("Las horas deben ser mayores a 0.")
        return value

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError("El título es requerido.")
        return value


class SubtaskNestedSerializer(serializers.ModelSerializer):
    """Igual que SubtaskSerializer pero sin pedir 'activity' (va en la URL)."""

    class Meta:
        model = Subtask
        fields = [
            "id",
            "title",
            "target_date",
            "estimated_hours",
            "description",
            "status",
            "postpone_note",
            "done_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "done_at", "created_at", "updated_at"]

    def validate_estimated_hours(self, value):
        if value <= 0:
            raise serializers.ValidationError("Las horas deben ser mayores a 0.")
        return value


class TodaySubtaskSerializer(serializers.ModelSerializer):
    """Subtarea + datos de su actividad, para la vista /today (US-04)."""

    activity_id = serializers.IntegerField(source="activity.id", read_only=True)
    activity_title = serializers.CharField(source="activity.title", read_only=True)
    course = serializers.CharField(source="activity.course", read_only=True)

    class Meta:
        model = Subtask
        fields = [
            "id",
            "title",
            "activity_id",
            "activity_title",
            "course",
            "target_date",
            "estimated_hours",
            "description",
            "status",
        ]


class ActivitySerializer(serializers.ModelSerializer):
    subtasks_total = serializers.ReadOnlyField()
    subtasks_done = serializers.ReadOnlyField()
    progress_percent = serializers.ReadOnlyField()

    class Meta:
        model = Activity
        fields = [
            "id",
            "title",
            "course",
            "type",
            "due_date",
            "description",
            "subtasks_total",
            "subtasks_done",
            "progress_percent",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError("El título es requerido.")
        return value


class ActivityDetailSerializer(ActivitySerializer):
    subtasks = SubtaskNestedSerializer(many=True, read_only=True)

    class Meta(ActivitySerializer.Meta):
        fields = ActivitySerializer.Meta.fields + ["subtasks"]


class DailyCapacitySerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyCapacity
        fields = ["daily_limit_hours"]

    def validate_daily_limit_hours(self, value):
        # US-12, Escenario 3: rango permitido 1..16.
        if value < 1 or value > 16:
            raise serializers.ValidationError(
                "El límite diario debe estar entre 1 y 16 horas."
            )
        return value


class OverloadCheckSerializer(serializers.Serializer):
    """Entrada para POST /api/conflicts/overload/ (US-07)."""

    target_date = serializers.DateField()
    estimated_hours = serializers.DecimalField(max_digits=5, decimal_places=2)
    subtask_id = serializers.IntegerField(required=False, allow_null=True)
