import { ReactNode, useCallback, useEffect, useState } from "react";
import { api } from "./api";

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <h3>{title}</h3>
        {children}
      </div>
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <label>{label}</label>
      {children}
    </div>
  );
}

export function Stat({ label, value, sub, hero }: { label: string; value: ReactNode; sub?: string; hero?: boolean }) {
  return (
    <div className={"card stat" + (hero ? " hero" : "")}>
      <div className="v">{value}</div>
      <div className="l">{label}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

/** Ma'lumotni yuklaydi va intervalda yangilaydi. */
export function useLoad<T>(path: string, refreshMs = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const reload = useCallback(async () => {
    try {
      setData(await api<T>(path));
      setError("");
    } catch (e: any) {
      setError(e.message);
    }
  }, [path]);
  useEffect(() => {
    reload();
    if (!refreshMs) return;
    const t = setInterval(reload, refreshMs);
    return () => clearInterval(t);
  }, [reload, refreshMs]);
  return { data, error, reload };
}

export const BLOCK_LABEL: Record<string, string> = {
  reserved: "kutilmoqda", creating: "yaratilmoqda", created: "faol", finished: "tugadi",
  failed: "xato", cancelled: "bekor", missed: "o'tkazib yuborildi",
};
export const SESSION_LABEL: Record<string, string> = {
  active: "faol", completed: "yakunlangan", cancelled: "to'xtatilgan", failed: "xato",
};

export function Blocks({ blocks }: { blocks: any[] }) {
  return (
    <div className="blocks">
      {blocks.map((b) => (
        <span key={b.id} className={"blk " + b.status} title={`${BLOCK_LABEL[b.status] ?? b.status}${b.account ? " · " + b.account : ""}${b.error ? " · " + b.error : ""}`}>
          {b.idx}
        </span>
      ))}
    </div>
  );
}
