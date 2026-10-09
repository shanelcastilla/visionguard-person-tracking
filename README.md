# VisionGuard

**Monitoreo de video y registro de detecciones de personas en tiempo real.**

VisionGuard combina una API en FastAPI, un panel web en Next.js y un detector
basado en YOLO. La aplicación presenta la transmisión de una cámara conectada
al equipo que ejecuta el backend y registra eventos de entrada y salida en
PostgreSQL.

> **Alcance:** el sistema detecta y sigue personas frente a una cámara. No
> reconoce rostros, no identifica personas y no infiere emociones ni identidad.

## Funcionalidades

- Transmisión MJPEG en vivo con las detecciones superpuestas.
- Inicio y detención de la cámara desde el panel.
- Resumen de entradas del día, personas con detecciones activas y duración
  promedio.
- Historial de eventos con filtros por fecha, seguimiento y confianza mínima.
- Evidencias fotográficas vinculadas a los eventos.
- Indicadores del estado de la cámara y los FPS observados.

## Arquitectura

| Componente | Tecnología | Responsabilidad |
| --- | --- | --- |
| Interfaz web | Next.js, React y TypeScript | Panel, transmisión, resumen e historial |
| API | FastAPI y Uvicorn | API REST, control de cámara y publicación de evidencias |
| Detección y seguimiento | Ultralytics YOLO y OpenCV | Detectar y seguir personas en los fotogramas |
| Persistencia | PostgreSQL y psycopg2 | Guardar eventos y consultar métricas |

La API inicia el detector al arrancar y libera la cámara al cerrarse. Ejecuta
**una sola instancia del backend por cámara**; no ejecutes `main.py` al mismo
tiempo que la API, ya que ambos procesos intentarían acceder a la cámara.

## Requisitos

- Windows 10/11 (los comandos de esta guía usan PowerShell).
- Python 3.12.
- Node.js 20.9 o posterior y npm.
- PostgreSQL accesible desde el equipo del backend.
- Una cámara compatible con OpenCV conectada al equipo del backend.
- Pesos compatibles de Ultralytics guardados como `yolo11n.pt` en la raíz del
  proyecto.

El rendimiento de la inferencia depende del hardware, la cámara y los pesos
utilizados. La configuración actual procesa fotogramas con un tamaño de entrada
de 416 px.

## Configuración local

### 1. Preparar PostgreSQL

Crea una base de datos y un usuario en PostgreSQL. Desde la raíz del proyecto,
ejecuta el esquema inicial con `psql`:

```powershell
psql -h localhost -p 5432 -U <usuario> -d <base_de_datos> -f database/schema.sql
```

Sustituye `<usuario>` y `<base_de_datos>` por tus valores. `psql` solicitará la
contraseña del usuario según la configuración local de PostgreSQL.

### 2. Configurar variables de entorno

Copia la plantilla y completa los datos de la base de datos:

```powershell
Copy-Item .env.example .env
```

Edita `.env`:

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=visionguard
DB_USER=tu_usuario
DB_PASSWORD=tu_contraseña
```

No publiques `.env` ni guardes credenciales en el código fuente. Para la
interfaz, la URL del backend se configura en `frontend/.env.local`; la plantilla
correspondiente es `frontend/.env.example`.

### 3. Instalar dependencias de Python

Desde la raíz del proyecto:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. Instalar dependencias de la interfaz

```powershell
Set-Location frontend
npm ci
Copy-Item .env.example .env.local
Set-Location ..
```

Si el backend no está en `http://127.0.0.1:8000`, ajusta
`NEXT_PUBLIC_API_URL` en `frontend/.env.local` antes de iniciar Next.js.

### 5. Iniciar la aplicación

Abre dos terminales en la raíz del proyecto.

**Terminal 1 — API y cámara:**

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main_api:app --reload --reload-dir app
```

**Terminal 2 — interfaz web:**

```powershell
Set-Location frontend
npm run dev
```

Abre <http://localhost:3000> para acceder al panel. La documentación
interactiva de FastAPI está disponible en <http://127.0.0.1:8000/docs>.

Al iniciar la API, la cámara se activa automáticamente. Si no se puede abrir,
comprueba los permisos del sistema, que ninguna otra aplicación la esté usando
y que `yolo11n.pt` se encuentre en la raíz del proyecto. Si PostgreSQL no está
disponible, el detector puede continuar, pero no podrá guardar ni consultar
eventos.

## API

La API local usa por defecto `http://127.0.0.1:8000`.

| Método | Ruta | Descripción |
| --- | --- | --- |
| `GET` | `/` | Comprueba que la API está activa |
| `GET` | `/dashboard/summary` | Devuelve el resumen y el estado de la cámara |
| `GET` | `/camera/status` | Devuelve el estado actual de la cámara |
| `POST` | `/camera/start` | Inicia el detector de cámara |
| `POST` | `/camera/stop` | Detiene el detector y cierra los eventos activos |
| `GET` | `/camera/stream.mjpg` | Transmisión MJPEG en vivo |
| `GET` | `/events/` | Lista los eventos registrados |
| `GET` | `/events/active` | Lista los eventos sin hora de salida |
| `GET` | `/events/today` | Lista los eventos del día |
| `GET` | `/events/filtered` | Filtra eventos por fecha, seguimiento y confianza |
| `GET` | `/events/{event_id}` | Consulta un evento por su ID |
| `DELETE` | `/events/{event_id}` | Elimina un evento |
| `GET` | `/evidence/{filename}` | Sirve una evidencia disponible |

Los filtros de `/events/filtered` son `start_date`, `end_date` (`YYYY-MM-DD`),
`track_id` y `min_confidence` (entre `0` y `1`). Si la detención de la cámara
tarda más de cinco segundos, la API responde con un error en lugar de indicar
que la cámara ya se detuvo.

## Pruebas

Desde la raíz del proyecto, con el entorno de Python configurado:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -p "test_*.py" -v
```

Para comprobar la interfaz:

```powershell
Set-Location frontend
npm run lint
npm run build
```

Las pruebas que importan la API también necesitan las variables de PostgreSQL
definidas; usa el archivo `.env` local para cargarlas.

## Estructura del proyecto

```text
.
├── app/
│   ├── api/             # Rutas de cámara, eventos y panel
│   ├── repositories/    # Consultas y escritura en PostgreSQL
│   ├── schema/          # Modelos de respuesta de la API
│   ├── services/        # Cámara, detección y seguimiento
│   ├── config.py        # Variables de entorno
│   ├── database.py      # Conexión a PostgreSQL
│   └── main_api.py      # Aplicación FastAPI
├── database/
│   └── schema.sql       # Esquema inicial de PostgreSQL
├── events/              # Evidencias generadas localmente; no se publican
├── frontend/
│   └── src/app/         # Aplicación Next.js
├── requirements.txt
├── test_*.py
└── yolo11n.pt           # Pesos requeridos por el detector
```

## Publicar el proyecto en GitHub

Se recomienda el nombre de aplicación **VisionGuard** y el nombre de repositorio
`visionguard-person-tracking`. Otras opciones claras son
`visionguard-monitoring-dashboard` y `visionguard-people-analytics`.

1. Crea en GitHub un repositorio vacío llamado `visionguard-person-tracking`.
   No selecciones la opción para añadir un README, `.gitignore` o licencia: este
   proyecto ya tiene su README y `.gitignore`.
2. Abre PowerShell en la raíz del proyecto y confirma que no se incluyan
   secretos, capturas de cámara ni dependencias generadas:

   ```powershell
   git status --short
   git check-ignore .env frontend/.env.local .venv frontend/node_modules events
   ```

3. Si todavía no existe un repositorio Git local, inicialízalo y publica la
   rama `main`:

   ```powershell
   git init
   git branch -M main
   git add .
   git status --short
   git commit -m "docs: prepare VisionGuard for GitHub"
   git remote add origin https://github.com/<usuario>/visionguard-person-tracking.git
   git push -u origin main
   ```

   Reemplaza `<usuario>` por tu nombre de usuario u organización de GitHub. Si
   el repositorio local ya está inicializado, omite `git init` y
   `git branch -M main` cuando corresponda; si ya existe el remoto `origin`,
   actualízalo en lugar de volver a añadirlo.
4. Completa la autenticación en GitHub cuando Git la solicite. No introduzcas
   tokens en el código, en `.env` compartidos ni en los comandos guardados en el
   repositorio.

Antes de hacer público el repositorio, revisa los términos de distribución de
los pesos de YOLO que utilices y cualquier requisito de privacidad aplicable a
las capturas y al uso de cámaras. Las evidencias pueden contener imágenes de
personas: mantenlas fuera del control de versiones y limita su acceso.

## Privacidad y limitaciones

- Los IDs de seguimiento distinguen detecciones durante el seguimiento; no son
  identidades personales persistentes.
- Las fotografías de evidencia se almacenan en `events/` localmente y se sirven
  mediante la API. No subas esa carpeta a GitHub.
- Protege la cámara, el panel, la API, las evidencias y la base de datos con
  controles adecuados antes de cualquier uso fuera de un entorno local.
- El proyecto no incluye autenticación de usuarios ni está presentado como un
  sistema de identificación biométrica.
