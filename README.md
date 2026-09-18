# Backend — Organizador de Actividades (MiniProyecto 1)

API REST en **Django + Django REST Framework**, implementando la
arquitectura mínima de la sección 6 del Backlog Refinado:

- **Front-end:** React (SPA) — no vive en este repo.
- **Back-end:** este proyecto (Django REST Framework).
- **Persistencia:** Postgres administrado por **Supabase** en producción
  (vía `DATABASE_URL`); SQLite local automático si esa variable no está
  configurada, para poder levantar el proyecto sin credenciales.

Probado de punta a punta (16/16 escenarios del backlog) antes de entregarlo.

## Puesta en marcha local

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # déjalo con DATABASE_URL vacío para usar SQLite

python manage.py migrate
python manage.py createsuperuser   # opcional, para entrar a /admin/
python manage.py runserver
```

La API queda en `http://127.0.0.1:8000/api/`.

## Conectar con Supabase (persistencia real)

1. En tu proyecto de Supabase: **Project Settings → Database → Connection
   string → URI**. Copia la cadena (modo *Session pooler* si vas a
   desplegar en Render u otro entorno serverless).
2. Pégala en `.env` como `DATABASE_URL=postgresql://...`.
3. Corre `python manage.py migrate` de nuevo — esta vez creará las tablas
   en Supabase en lugar de SQLite.

No hace falta tocar nada más: `config/settings.py` detecta `DATABASE_URL`
automáticamente (`dj_database_url`) y activa SSL.

## Endpoints

| Método | Ruta | User Story | Qué hace |
|---|---|---|---|
| GET/POST | `/api/activities/` | US-01 | Listar / crear actividades |
| GET/PATCH/DELETE | `/api/activities/<id>/` | US-01, US-03 | Detalle, editar, eliminar (cascada a subtareas) |
| GET/POST | `/api/activities/<id>/subtasks/` | US-02 | Listar / crear subtareas de una actividad |
| GET/PATCH/DELETE | `/api/subtasks/<id>/` | US-03, US-06, US-09 | Editar cualquier campo, reprogramar (`target_date`), marcar `DONE`/`POSTPONED` (+ `postpone_note`), eliminar |
| GET | `/api/today/?course=&status=` | US-04, US-05 | Subtareas agrupadas en `vencidas` / `para_hoy` / `proximas`, ordenadas por fecha y desempatadas por horas; filtros opcionales |
| POST | `/api/conflicts/overload/` | US-07 | Previsualiza sobrecarga antes de confirmar un cambio: `{target_date, estimated_hours, subtask_id?}` → `{planned_hours, limit_hours, exceeds_by, conflict}` |
| GET | `/api/activities/<id>/progress/` | US-10 | `{total, done, progress_percent}` |
| GET/PUT | `/api/capacity/` | US-12 | Límite diario de horas (por defecto 6, rango 1–16) |

**US-08 (resolver conflicto)** no tiene un endpoint propio: "mover" es un
`PATCH /subtasks/<id>/` cambiando `target_date`, "reducir horas" es el
mismo `PATCH` cambiando `estimated_hours`, y "posponer" ya está en US-09.
El `PATCH` responde con `day_load` (mismo payload que `/conflicts/overload/`)
recalculado, para confirmar si el conflicto quedó resuelto.

**US-11 (autenticación)** queda marcada como Sprint 2+ en el backlog. Por
ahora (`planner/logic.get_actor`) todo se asocia a un usuario `demo` fijo,
así el resto de los endpoints funcionan sin bloquear el desarrollo. Cuando
se implemente login real, basta con que el front-end mande la sesión — el
resto del código ya filtra todo por "actor" y no necesita cambios.

## Estructura

```
config/          settings, urls raíz, wsgi/asgi
planner/
  models.py      Activity, Subtask, DailyCapacity
  logic.py       reglas de negocio (sobrecarga, agrupación de Hoy, actor demo)
  serializers.py validaciones (título requerido, horas > 0, rango 1-16h)
  views.py       endpoints REST
  urls.py        rutas /api/...
  admin.py       registrado en /admin/ para inspeccionar datos rápido
```

## Desplegar en Render (backend)

1. Sube este código a un repo de tu organización de GitHub (el mismo tipo
   de repo que ya usan para el resto del proyecto).
2. En Render: **New → Web Service** → conecta el repo.
3. Configura:
   - **Build Command:** `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
   - **Start Command:** `gunicorn config.wsgi:application`
4. En **Environment**, agrega las variables (mismos nombres que `.env.example`):
   - `DJANGO_SECRET_KEY` — genera una nueva, no reuses la de desarrollo.
   - `DJANGO_DEBUG=False`
   - `DATABASE_URL` — la connection string de Supabase (ver arriba).
   - `CORS_ALLOWED_ORIGINS` — la URL de tu front-end en Vercel, ej. `https://tu-app.vercel.app`
   - `CSRF_TRUSTED_ORIGINS` — la URL que Render te va a dar para este servicio, ej. `https://tu-backend.onrender.com` (la sabrás después del primer deploy; redepliega una vez la tengas).
   - `DJANGO_ALLOWED_HOSTS` — opcional, puedes dejar `*` o poner el dominio de Render.
5. Deploy. Render corre el *build command* (instala, junta estáticos y
   migra la base en Supabase) y luego levanta gunicorn.

Cada vez que hagas push a la rama conectada, Render vuelve a desplegar solo.

## Usar la API

### Desde el front-end (React)

```js
const API = import.meta.env.VITE_API_URL; // ej. https://tu-backend.onrender.com/api

// Crear una actividad
await fetch(`${API}/activities/`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ title: "Parcial de Cálculo", course: "Cálculo III", type: "EXAMEN", due_date: "2026-09-30" }),
});

// Traer la vista Hoy
const res = await fetch(`${API}/today/`);
const { vencidas, para_hoy, proximas, rule } = await res.json();
```

Define `VITE_API_URL` en el `.env` del proyecto de React (local apuntando
a `http://127.0.0.1:8000/api`, en Vercel apuntando a tu URL de Render).

### Sin front-end, para probar o generar evidencia

- **Django admin:** entra a `/admin/` con el superusuario
  (`python manage.py createsuperuser`) y ve/edita todo desde ahí —
  sirve como evidencia visual rápida sin tocar la API directamente.
- **curl / Postman / Thunder Client:** cualquier cliente HTTP sirve;
  usa la tabla de endpoints de arriba. Ejemplo:
  `curl -X POST http://127.0.0.1:8000/api/activities/ -H "Content-Type: application/json" -d '{"title":"x","due_date":"2026-09-30"}'`

## Notas para las evidencias del sprint

- `python manage.py check` y `makemigrations`/`migrate` corren limpio.
- Los 16 escenarios probados cubren: creación + validaciones (US-01,
  US-02), agrupación/orden de Hoy (US-04), sobrecarga (US-07), marcar
  hecha/posponer con nota (US-09), capacidad diaria con rango (US-12),
  progreso (US-10), editar/eliminar con cascada (US-03).
- Formato de errores: el de DRF por defecto (`{"campo": ["mensaje"]}`).
  Si el equipo ya tiene un estándar de respuesta (TS-03) distinto, es un
  cambio acotado a un exception handler en `config/settings.py`.
