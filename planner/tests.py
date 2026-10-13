from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Activity, ActivityType, Subtask, SubtaskStatus, DailyCapacity

User = get_user_model()


class Sprint4BackendTests(APITestCase):
    """
    Pruebas unitarias e integrales para los criterios del Sprint 4:
    - C1: Registrar tareas ejecutadas (Hecha/Pospuesta) + nota explicativa persistente.
    - C2: Cálculo consistente de progreso (% y conteo de gestiones por evento).
    - C3: Reducción de carga diaria de horas al ejecutar o posponer una tarea.
    - C5: Manejo estándar de errores y respuestas HTTP en API.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="sergio@correounivalle.edu.co",
            email="sergio@correounivalle.edu.co",
            password="testpassword123",
            first_name="Sergio",
        )
        self.client.force_authenticate(user=self.user)

        self.today = date.today()
        self.activity = Activity.objects.create(
            owner=self.user,
            title="Conferencia Internacional de IA",
            course="Inteligencia Artificial",
            type=ActivityType.PROYECTO,
            due_date=self.today + timedelta(days=10),
            description="Organización de logística de conferencia",
        )

        self.subtask1 = Subtask.objects.create(
            activity=self.activity,
            title="Reservar auditorio principal",
            target_date=self.today,
            estimated_hours=3.0,
            status=SubtaskStatus.PENDING,
        )
        self.subtask2 = Subtask.objects.create(
            activity=self.activity,
            title="Contratar servicio de catering",
            target_date=self.today,
            estimated_hours=2.0,
            status=SubtaskStatus.PENDING,
        )

    def test_c1_marcar_subtarea_hecha_persiste_y_asigna_done_at(self):
        """C1: Marcar como Hecha (DONE) persiste en BD y actualiza done_at."""
        url = reverse("subtask-detail", kwargs={"pk": self.subtask1.pk})
        response = self.client.patch(url, {"status": SubtaskStatus.DONE}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.subtask1.refresh_from_db()
        self.assertEqual(self.subtask1.status, SubtaskStatus.DONE)
        self.assertIsNotNone(self.subtask1.done_at)

    def test_c1_marcar_subtarea_pospuesta_con_nota_explicativa_persiste(self):
        """C1: Marcar como Pospuesta (POSTPONED) con nota opcional explicativa."""
        url = reverse("subtask-detail", kwargs={"pk": self.subtask2.pk})
        payload = {
            "status": SubtaskStatus.POSTPONED,
            "postpone_note": "Esperando confirmación del proveedor de catering para cotización final",
        }
        response = self.client.patch(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.subtask2.refresh_from_db()
        self.assertEqual(self.subtask2.status, SubtaskStatus.POSTPONED)
        self.assertEqual(
            self.subtask2.postpone_note,
            "Esperando confirmación del proveedor de catering para cotización final",
        )

    def test_completar_subtarea_pospuesta_limpia_nota_explicativa(self):
        """Al marcar una tarea pospuesta como Hecha (DONE), la nota explicativa se limpia automáticamente."""
        # Primero posponemos con nota
        self.subtask2.status = SubtaskStatus.POSTPONED
        self.subtask2.postpone_note = "Pendiente cotización"
        self.subtask2.save()

        # Completamos la tarea
        url = reverse("subtask-detail", kwargs={"pk": self.subtask2.pk})
        response = self.client.patch(url, {"status": SubtaskStatus.DONE}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.subtask2.refresh_from_db()
        self.assertEqual(self.subtask2.status, SubtaskStatus.DONE)
        self.assertEqual(self.subtask2.postpone_note, "")
        self.assertIsNotNone(self.subtask2.done_at)

    def test_c2_barra_progreso_calculo_consistente(self):
        """C2: Consulta de progreso por evento calcula porcentaje exacto y conteo."""
        # 1 de 2 tareas hecha -> 50%
        self.subtask1.status = SubtaskStatus.DONE
        self.subtask1.save()

        url = reverse("activity-progress", kwargs={"activity_id": self.activity.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(data["activity_id"], self.activity.id)
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["done"], 1)
        self.assertEqual(data["progress_percent"], 50)

    def test_c3_reduccion_carga_urgente_al_ejecutar_o_posponer(self):
        """C3: Al marcar Hecha o Pospuesta, la carga de horas del día se reduce."""
        from .logic import planned_hours_for_day

        # Inicialmente 2 tareas de 3h y 2h = 5h
        self.assertEqual(planned_hours_for_day(self.user, self.today), 5.0)

        # Al completar subtask1 (3h), solo queda 2h
        self.subtask1.status = SubtaskStatus.DONE
        self.subtask1.save()
        self.assertEqual(planned_hours_for_day(self.user, self.today), 2.0)

        # Al posponer subtask2 (2h), la carga urgente pasa a 0h
        self.subtask2.status = SubtaskStatus.POSTPONED
        self.subtask2.save()
        self.assertEqual(planned_hours_for_day(self.user, self.today), 0.0)

    def test_c5_manejo_estandar_de_errores(self):
        """C5: Validación estándar rechaza horas menores o iguales a cero con 400 Bad Request."""
        url = reverse("subtask-detail", kwargs={"pk": self.subtask1.pk})
        response = self.client.patch(url, {"estimated_hours": -1}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
