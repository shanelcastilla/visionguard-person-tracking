"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

type CameraStatus = {
  online: boolean;
  state: string;
  message: string;
  people_detected: number;
  last_frame_at: string | null;
  fps: number;
  storage_warning: string | null;
};

type DashboardSummary = {
  entries_today: number;
  people_inside: number;
  average_duration_seconds: number;
  camera: CameraStatus;
};

type EventRecord = {
  id: number;
  track_id: number;
  entry_time: string;
  exit_time: string | null;
  duration_seconds: number | null;
  confidence: number;
  image_path: string;
  evidence_url: string | null;
};

const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

const emptySummary: DashboardSummary = {
  entries_today: 0,
  people_inside: 0,
  average_duration_seconds: 0,
  camera: {
    online: false,
    state: "unknown",
    message: "Esperando respuesta del servidor.",
    people_detected: 0,
    last_frame_at: null,
    fps: 0,
    storage_warning: null,
  },
};

async function getJson<T>(path: string): Promise<T> {
  return requestJson<T>(path);
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "TimeoutError") {
      throw new Error("FastAPI no respondió en 8 segundos. Revisa que el backend esté activo.");
    }
    throw new Error("No fue posible conectar con FastAPI. Revisa la URL del backend.");
  }

  if (!response.ok) {
    if (response.status >= 500) {
      throw new Error(
        `FastAPI encontró un error interno (${response.status}) al consultar ${path}. Revisa el log del backend.`,
      );
    }
    throw new Error(`La API respondió ${response.status} al consultar ${path}.`);
  }
  return response.json() as Promise<T>;
}

async function deleteJson(path: string): Promise<void> {
  await requestJson<{ message: string }>(path, { method: "DELETE" });
}

async function postJson<T>(path: string): Promise<T> {
  return requestJson<T>(path, { method: "POST" });
}

function Icon({
  name,
  size = 18,
}: {
  name: "grid" | "camera" | "history" | "refresh" | "search" | "calendar";
  size?: number;
}) {
  const shared = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true as const,
  };

  switch (name) {
    case "grid":
      return <svg {...shared}><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /></svg>;
    case "camera":
      return <svg {...shared}><path d="M4 7h3l1.5-2h7L17 7h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1Z" /><circle cx="12" cy="13" r="3.5" /></svg>;
    case "history":
      return <svg {...shared}><path d="M3 12a9 9 0 1 0 2.64-6.36L3 8" /><path d="M3 3v5h5M12 7v5l3 2" /></svg>;
    case "refresh":
      return <svg {...shared}><path d="M20 7v5h-5M4 17v-5h5" /><path d="M5.6 9A7 7 0 0 1 18 6l2 2M4 16l2 2a7 7 0 0 0 12.4-3" /></svg>;
    case "search":
      return <svg {...shared}><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 4 4" /></svg>;
    case "calendar":
      return <svg {...shared}><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></svg>;
  }
}

function formatDuration(value: number | null | undefined) {
  if (value == null) return "En curso";
  if (value < 60) return `${value} s`;
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const seconds = value % 60;
  if (hours) return `${hours} h ${minutes} min`;
  return seconds ? `${minutes} min ${seconds} s` : `${minutes} min`;
}

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("es-MX", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function evidenceUrl(event: EventRecord) {
  return event.evidence_url ? `${API_BASE}${event.evidence_url}` : null;
}

export default function Home() {
  const [summary, setSummary] = useState(emptySummary);
  const [cameraStatus, setCameraStatus] = useState(emptySummary.camera);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [eventActionMessage, setEventActionMessage] = useState("");
  const [deletingEventId, setDeletingEventId] = useState<number | null>(null);
  const [cameraActionLoading, setCameraActionLoading] = useState(false);
  const [cameraActionMessage, setCameraActionMessage] = useState("");
  const [previewFailed, setPreviewFailed] = useState(false);
  const [streamAttempt, setStreamAttempt] = useState(0);
  const [filters, setFilters] = useState({
    start_date: "",
    end_date: "",
    track_id: "",
    min_confidence: "",
  });
  const [appliedFilters, setAppliedFilters] = useState(filters);

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    Object.entries(appliedFilters).forEach(([key, value]) => {
      if (value.trim()) params.set(key, value.trim());
    });
    return params.toString();
  }, [appliedFilters]);

  const refreshDashboard = useCallback(async () => {
    try {
      const [nextSummary, nextEvents] = await Promise.all([
        getJson<DashboardSummary>("/dashboard/summary"),
        getJson<EventRecord[]>(`/events/filtered${queryString ? `?${queryString}` : ""}`),
      ]);
      setSummary(nextSummary);
      setEvents(nextEvents);
      setError("");
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "No fue posible conectar con la API.",
      );
    } finally {
      setLoading(false);
    }
  }, [queryString]);

  const refreshCameraStatus = useCallback(async () => {
    try {
      setCameraStatus(await getJson<CameraStatus>("/camera/status"));
    } catch (cause) {
      setCameraStatus((current) => ({
        ...current,
        online: false,
        state: "error",
        message:
          cause instanceof Error
            ? cause.message
            : "No fue posible consultar el estado de la cámara.",
      }));
    }
  }, []);

  useEffect(() => {
    const initialFetch = window.setTimeout(
      () => void refreshDashboard(),
      0,
    );
    const interval = window.setInterval(() => void refreshDashboard(), 10000);
    return () => {
      window.clearTimeout(initialFetch);
      window.clearInterval(interval);
    };
  }, [refreshDashboard]);

  useEffect(() => {
    const initialStatus = window.setTimeout(
      () => void refreshCameraStatus(),
      0,
    );
    const interval = window.setInterval(
      () => void refreshCameraStatus(),
      1500,
    );
    return () => {
      window.clearTimeout(initialStatus);
      window.clearInterval(interval);
    };
  }, [refreshCameraStatus]);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      filters.start_date &&
      filters.end_date &&
      filters.start_date > filters.end_date
    ) {
      setError("La fecha inicial no puede ser posterior a la fecha final.");
      return;
    }
    setAppliedFilters({ ...filters });
  }

  function refreshManually() {
    setRefreshing(true);
    setPreviewFailed(false);
    setStreamAttempt((attempt) => attempt + 1);
    void refreshDashboard().finally(() => setRefreshing(false));
  }

  function retryCameraStream() {
    setPreviewFailed(false);
    setStreamAttempt((attempt) => attempt + 1);
    void refreshCameraStatus();
  }

  function clearFilters() {
    const cleared = {
      start_date: "",
      end_date: "",
      track_id: "",
      min_confidence: "",
    };
    setFilters(cleared);
    setAppliedFilters(cleared);
  }

  async function deleteEvent(event: EventRecord) {
    const eventLabel = `EV-${String(event.id).padStart(4, "0")}`;
    if (!window.confirm(`¿Seguro que deseas eliminar el evento ${eventLabel}? Esta acción no se puede deshacer.`)) {
      return;
    }

    setDeletingEventId(event.id);
    setEventActionMessage("");
    try {
      await deleteJson(`/events/${event.id}`);
      setEvents((current) => current.filter((item) => item.id !== event.id));
      setEventActionMessage(`El evento ${eventLabel} se eliminó correctamente.`);
      await refreshDashboard();
    } catch (cause) {
      setEventActionMessage(
        cause instanceof Error
          ? `No se pudo eliminar ${eventLabel}: ${cause.message}`
          : `No se pudo eliminar ${eventLabel}.`,
      );
    } finally {
      setDeletingEventId(null);
    }
  }

  async function toggleCamera() {
    const shouldStop = ["online", "connecting", "starting"].includes(
      cameraStatus.state,
    );
    if (
      shouldStop &&
      !window.confirm(
        "¿Finalizar la cámara? Se detendrá la detección, se liberará el dispositivo y se cerrarán las detecciones activas.",
      )
    ) {
      return;
    }

    setCameraActionLoading(true);
    setCameraActionMessage("");
    try {
      const result = await postJson<{ message: string; status: CameraStatus }>(
        shouldStop ? "/camera/stop" : "/camera/start",
      );
      setCameraStatus(result.status);
      setCameraActionMessage(result.message);
      setPreviewFailed(false);
      setStreamAttempt((attempt) => attempt + 1);
      await Promise.all([refreshCameraStatus(), refreshDashboard()]);
    } catch (cause) {
      setCameraActionMessage(
        cause instanceof Error
          ? cause.message
          : "No fue posible cambiar el estado de la cámara.",
      );
    } finally {
      setCameraActionLoading(false);
    }
  }

  const cameraOnline = cameraStatus.online;
  const metricsUnavailable = loading || Boolean(error);
  const recentEvents = events.slice(0, 5);

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#overview" aria-label="VisionGuard inicio">
          <span className="brand-mark">A<span>I</span></span>
          <span className="brand-copy">
            <strong>VISION<span>GUARD</span></strong>
            <small>MONITOREO INTELIGENTE</small>
          </span>
        </a>
        <div className="sidebar-label">ESPACIO DE TRABAJO</div>
        <nav className="side-nav" aria-label="Navegación principal">
          <a className="nav-link active" href="#overview"><Icon name="grid" /> Panel principal</a>
          <a className="nav-link" href="#monitor"><Icon name="camera" /> Monitoreo</a>
          <a className="nav-link" href="#history"><Icon name="history" /> Historial</a>
        </nav>
        <div className="sidebar-bottom">
          <div className="system-chip">
            <span className={`pulse-dot ${cameraOnline ? "online" : "offline"}`} />
            <div><strong>{cameraOnline ? "Sistema activo" : cameraStatus.state === "stopped" ? "Cámara finalizada" : "Sistema listo"}</strong><small>{cameraOnline ? "Detectando en vivo" : cameraStatus.state === "stopped" ? "Detección detenida" : "Esperando cámara"}</small></div>
          </div>
          <div className="sidebar-foot">VisionGuard <span>v1.0</span></div>
        </div>
      </aside>

      <section className="main-content">
        <header className="topbar">
          <div className="breadcrumb"><span>Espacio de trabajo</span><span className="crumb-slash">/</span><strong>Panel principal</strong></div>
          <div className="topbar-actions">
            <div className={`connection-pill ${cameraOnline ? "connected" : "disconnected"}`}>
              <span className="pulse-dot" />{cameraOnline ? "Cámara conectada" : cameraStatus.state === "stopped" ? "Cámara detenida" : "Cámara desconectada"}
            </div>
            <div className="top-date"><span className="date-icon"><Icon name="calendar" size={15} /></span>{new Intl.DateTimeFormat("es-MX", { dateStyle: "medium" }).format(new Date())}</div>
            <button className="icon-button refresh-button" onClick={refreshManually} disabled={refreshing} aria-label="Actualizar panel" title="Actualizar panel">
              <Icon name="refresh" size={17} />
            </button>
            <div className="avatar" aria-label="Usuario">AG</div>
          </div>
        </header>

        <div className="page-content">
          <section className="welcome-row" id="overview">
            <div>
              <div className="eyebrow"><span className="eyebrow-line" /> CENTRO DE CONTROL</div>
              <h1>Buenos días, <span>Administrador</span></h1>
              <p className="page-subtitle">Resumen de actividad y monitoreo de tu sistema de seguridad.</p>
            </div>
            <div className="last-updated"><span className="live-dot" /> Actualización automática <b>·</b> cada 10 s</div>
          </section>

          {error && <div className="error-banner" role="alert"><span>!</span><div><strong>No se pudo actualizar el panel</strong><p>{error}</p></div><button onClick={refreshManually}>Reintentar</button></div>}

          <section className="metric-grid" aria-label="Resumen del día">
            <article className="metric-card">
              <div className="metric-top"><span>ENTRADAS DE HOY</span><span className="metric-icon cyan"><Icon name="history" size={19} /></span></div>
              <div className="metric-value">{metricsUnavailable ? "—" : summary.entries_today}</div>
              <div className="metric-note"><span className="metric-accent">Registros</span><span>desde las 00:00</span></div>
            </article>
            <article className="metric-card">
              <div className="metric-top"><span>PERSONAS DENTRO</span><span className="metric-icon green"><Icon name="grid" size={19} /></span></div>
              <div className="metric-value">{metricsUnavailable ? "—" : summary.people_inside}</div>
              <div className="metric-note"><span className="live-dot" /> En este momento</div>
            </article>
            <article className="metric-card">
              <div className="metric-top"><span>DURACIÓN PROMEDIO</span><span className="metric-icon violet"><Icon name="camera" size={19} /></span></div>
              <div className="metric-value duration-value">{metricsUnavailable ? "—" : formatDuration(summary.average_duration_seconds)}</div>
              <div className="metric-note"><span className="metric-accent violet-text">Estancias cerradas</span><span>de hoy</span></div>
            </article>
          </section>

          <section className="monitor-grid" id="monitor">
            <article className="panel camera-panel">
              <div className="panel-heading">
                <div><div className="eyebrow">VISTA EN VIVO</div><h2>Cámara principal</h2></div>
                <div className="camera-controls">
                  <button
                    className={`camera-control-button ${cameraOnline ? "camera-stop-button" : ""}`}
                    type="button"
                    onClick={() => void toggleCamera()}
                    disabled={cameraActionLoading || cameraStatus.state === "stopping"}
                  >
                    {cameraActionLoading
                      ? "Procesando…"
                      : cameraStatus.state === "starting"
                        ? "Cancelar inicio"
                        : cameraOnline
                          ? "Finalizar cámara"
                          : "Iniciar cámara"}
                  </button>
                  <span className={`status-badge ${cameraOnline ? "status-online" : cameraStatus.state === "stopped" ? "status-stopped" : "status-offline"}`}><span className="pulse-dot" />{cameraOnline ? "EN LÍNEA" : cameraStatus.state === "stopped" ? "DETENIDA" : cameraStatus.state === "stopping" ? "FINALIZANDO" : cameraStatus.state === "starting" || cameraStatus.state === "connecting" ? "INICIANDO" : "SIN SEÑAL"}</span>
                </div>
              </div>
              <div className={`camera-view ${cameraOnline ? "camera-live" : ""}`}>
                {cameraOnline && !previewFailed ? (
                  // MJPEG is intentionally rendered as an image URL rather than fetched as JSON.
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    key={streamAttempt}
                    className="camera-stream"
                    src={`${API_BASE}/camera/stream.mjpg`}
                    alt="Transmisión en vivo con detecciones de personas"
                    onError={() => setPreviewFailed(true)}
                  />
                ) : (
                  <div className="camera-empty">
                    <div className="camera-empty-icon"><Icon name="camera" size={30} /></div>
                    <strong>{cameraOnline ? "No se pudo mostrar el video" : cameraStatus.state === "stopped" ? "Cámara finalizada" : "Esperando señal de cámara"}</strong>
                    <p>{cameraStatus.message}</p>
                    {cameraOnline ? (
                      <button className="camera-retry" onClick={retryCameraStream}>Reconectar video</button>
                    ) : (
                      <span className="camera-hint">Conecta una cámara y mantén activo el backend FastAPI</span>
                    )}
                  </div>
                )}
                <div className="camera-overlay-top"><span className={`live-tag ${cameraOnline ? "" : "live-tag-offline"}`}><i />{cameraOnline ? "LIVE" : cameraStatus.state === "stopped" ? "DETENIDA" : "SIN SEÑAL"}</span><span className="camera-name">CAM 01 <b>·</b> USB</span></div>
                {cameraOnline && <div className="camera-overlay-bottom"><span><span className="pulse-dot" /> DETECCIÓN ACTIVA</span><span>{cameraStatus.people_detected} {cameraStatus.people_detected === 1 ? "persona" : "personas"} en cuadro</span><span className="camera-fps">{cameraStatus.fps.toFixed(1)} <small>FPS</small></span></div>}
              </div>
              {cameraActionMessage && <div className={`camera-action-message ${cameraStatus.state === "error" ? "camera-action-error" : ""}`} role="status">{cameraActionMessage}</div>}
              <div className="camera-footer"><span><i className={`mini-status ${cameraOnline ? "mini-online" : ""}`} />{cameraOnline ? "Procesamiento en vivo" : cameraStatus.state === "stopped" ? "Detenida manualmente" : "La API intentará conectar al iniciar"}</span>{cameraStatus.storage_warning && <span className="camera-warning" role="status">{cameraStatus.storage_warning}</span>}<span>{cameraStatus.last_frame_at ? `Último cuadro ${formatDate(cameraStatus.last_frame_at)}` : "—"}</span></div>
            </article>

            <article className="panel activity-panel">
              <div className="panel-heading activity-heading"><div><div className="eyebrow">ACTIVIDAD RECIENTE</div><h2>Últimos eventos</h2></div><a className="text-link" href="#history">Ver historial <span>↗</span></a></div>
              <div className="activity-list">
                {recentEvents.length ? recentEvents.map((event) => (
                  <div className="activity-item" key={event.id}>
                    <span className={`activity-marker ${event.exit_time ? "marker-muted" : ""}`} />
                    <div className="activity-copy"><strong>Persona detectada <span>#{event.track_id}</span></strong><small>{formatDate(event.entry_time)}</small></div>
                    <span className={`activity-state ${event.exit_time ? "state-done" : "state-active"}`}>{event.exit_time ? "Salida" : "Dentro"}</span>
                  </div>
                )) : <div className="activity-empty">{loading ? "Cargando actividad…" : "Aún no hay eventos para mostrar."}</div>}
              </div>
              <div className="activity-summary"><span>Actualización del historial</span><strong>Cada 10 segundos</strong></div>
            </article>
          </section>

          <section className="panel history-panel" id="history">
            <div className="history-title-row">
              <div><div className="eyebrow">REGISTRO DE ACCESOS</div><h2>Historial de eventos</h2><p>Consulta entradas, salidas y evidencia de cada detección.</p></div>
              <div className="result-count"><span className="count-dot" />{events.length} {events.length === 1 ? "registro" : "registros"}</div>
            </div>
            {eventActionMessage && <div className="event-action-message" role="status">{eventActionMessage}</div>}
            <form className="filter-bar" onSubmit={applyFilters}>
              <label className="filter-field date-field"><span>Desde</span><input type="date" value={filters.start_date} onChange={(event) => setFilters({ ...filters, start_date: event.target.value })} /></label>
              <label className="filter-field date-field"><span>Hasta</span><input type="date" value={filters.end_date} onChange={(event) => setFilters({ ...filters, end_date: event.target.value })} /></label>
              <label className="filter-field id-field"><span>ID de persona</span><input type="number" min="0" placeholder="Ej. 12" value={filters.track_id} onChange={(event) => setFilters({ ...filters, track_id: event.target.value })} /></label>
              <label className="filter-field confidence-field"><span>Confianza mín.</span><select value={filters.min_confidence} onChange={(event) => setFilters({ ...filters, min_confidence: event.target.value })}><option value="">Cualquiera</option><option value="0.5">50 %</option><option value="0.7">70 %</option><option value="0.8">80 %</option><option value="0.9">90 %</option></select></label>
              <button className="search-button" type="submit"><Icon name="search" size={16} /> Filtrar</button>
              <button className="clear-button" type="button" onClick={clearFilters}>Limpiar</button>
            </form>

            <div className="table-wrap">
              <table>
                <thead><tr><th>EVENTO</th><th>PERSONA</th><th>ENTRADA</th><th>SALIDA</th><th>CONFIANZA</th><th>DURACIÓN</th><th>EVIDENCIA</th><th>ESTADO</th><th>ACCIONES</th></tr></thead>
                <tbody>
                  {events.map((event) => {
                    const image = evidenceUrl(event);
                    return <tr key={event.id}>
                      <td><span className="event-id">EV-{String(event.id).padStart(4, "0")}</span></td>
                      <td><span className="person-cell"><span className="person-avatar">{String(event.track_id).slice(-2)}</span><strong>ID {event.track_id}</strong></span></td>
                      <td><span className="table-date">{formatDate(event.entry_time)}</span></td>
                      <td><span className="table-date">{formatDate(event.exit_time)}</span></td>
                      <td><span className={`confidence ${event.confidence >= 0.8 ? "confidence-high" : "confidence-mid"}`}><i />{(event.confidence * 100).toFixed(0)}%</span></td>
                      <td className="duration-cell">{formatDuration(event.duration_seconds)}</td>
                      <td>{image ? <a className="evidence-link" href={image} target="_blank" rel="noreferrer"><span className="evidence-thumb">
                        {/* Evidence is served by FastAPI's /evidence static route. */}
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={image} alt={`Evidencia del evento ${event.id}`} loading="lazy" />
                      </span><span>Ver foto ↗</span></a> : <span className="no-evidence">Sin foto</span>}</td>
                      <td><span className={`table-status ${event.exit_time ? "table-complete" : "table-inside"}`}><i />{event.exit_time ? "Finalizado" : "Dentro"}</span></td>
                      <td><button className="delete-event-button" type="button" onClick={() => void deleteEvent(event)} disabled={deletingEventId !== null} aria-label={`Eliminar evento ${event.id}`}>{deletingEventId === event.id ? "Eliminando…" : "Borrar"}</button></td>
                    </tr>;
                  })}
                  {!events.length && <tr><td colSpan={9} className="empty-row">{loading ? "Cargando historial…" : "No hay eventos que coincidan con estos filtros."}</td></tr>}
                </tbody>
              </table>
            </div>
            <div className="table-foot"><span>Los datos se actualizan automáticamente cada 10 segundos.</span><span className="privacy-note">Evidencia almacenada localmente</span></div>
          </section>

          <footer className="page-footer"><span>VISIONGUARD <i>·</i> PANEL DE SEGURIDAD</span><span>Conectado a FastAPI <i className={error ? "footer-error" : ""} /> {error ? "Revisar conexión" : "Operativo"}</span></footer>
        </div>
      </section>
    </main>
  );
}
