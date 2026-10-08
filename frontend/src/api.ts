export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  const res = await fetch("/api" + path, {
    method: opts.method ?? "GET",
    credentials: "same-origin",
    headers: opts.body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  if (res.status === 401 && !path.startsWith("/auth/login")) {
    window.dispatchEvent(new Event("unauthorized"));
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : Array.isArray(j.detail) ? j.detail.map((d: any) => d.msg).join("; ") : msg;
    } catch {}
    throw new ApiError(msg, res.status);
  }
  return res.json();
}

const TZ = "Asia/Tashkent";
export const fmtDT = (s?: string | null) =>
  s ? new Date(s).toLocaleString("ru-RU", { timeZone: TZ, day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";
export const fmtTime = (s?: string | null) =>
  s ? new Date(s).toLocaleTimeString("ru-RU", { timeZone: TZ, hour: "2-digit", minute: "2-digit" }) : "—";
export const fmtMin = (m?: number | null) => {
  if (!m) return "0 daq";
  const h = Math.floor(m / 60), r = m % 60;
  return h ? (r ? `${h} soat ${r} daq` : `${h} soat`) : `${r} daq`;
};
