import { useState } from "react";
import { api, fmtMin } from "../api";
import { Field, Modal, useLoad } from "../ui";

type T = { id?: number; full_name: string; telegram_id: string; tg_username: string; phone: string; note: string; is_active: boolean };
const empty: T = { full_name: "", telegram_id: "", tg_username: "", phone: "", note: "", is_active: true };

export default function Teachers() {
  const { data, error, reload } = useLoad<any[]>("/teachers", 10000);
  const [edit, setEdit] = useState<T | null>(null);
  const [err, setErr] = useState("");

  const save = async () => {
    if (!edit) return;
    const body = {
      full_name: edit.full_name,
      telegram_id: edit.telegram_id ? Number(edit.telegram_id) : null,
      tg_username: edit.tg_username || null,
      phone: edit.phone || null,
      note: edit.note || null,
      is_active: edit.is_active,
    };
    try {
      if (edit.id) await api(`/teachers/${edit.id}`, { method: "PATCH", body });
      else await api("/teachers", { method: "POST", body });
      setEdit(null);
      setErr("");
      reload();
    } catch (e: any) {
      setErr(e.message);
    }
  };

  const remove = async (t: any) => {
    if (!confirm(`${t.full_name} o'chirilsinmi?`)) return;
    const r = await api(`/teachers/${t.id}`, { method: "DELETE" });
    alert(r.message);
    reload();
  };

  const toggle = async (t: any) => {
    await api(`/teachers/${t.id}`, { method: "PATCH", body: { is_active: !t.is_active } });
    reload();
  };

  return (
    <>
      <div className="page-head">
        <h2>O'qituvchilar</h2>
        <button className="primary" onClick={() => { setErr(""); setEdit({ ...empty }); }}>+ Qo'shish</button>
      </div>
      <div className="card table-wrap">
        {error && <div className="err">{error}</div>}
        <table>
          <thead><tr><th>F.I.Sh.</th><th>Telegram</th><th>Telefon</th><th>Shu oy</th><th>Holat</th><th></th></tr></thead>
          <tbody>
            {(data ?? []).map((t) => (
              <tr key={t.id}>
                <td className="title">{t.full_name}{t.note && <div className="muted" style={{ fontSize: 13, fontWeight: 500 }}>{t.note}</div>}</td>
                <td data-label="Telegram"><span>{t.telegram_id ?? <span className="muted">kutilmoqda</span>}{t.tg_username && <span className="muted"> @{t.tg_username}</span>}</span></td>
                <td data-label="Telefon">{t.phone ?? "—"}</td>
                <td data-label="Shu oy">{t.month_sessions} dars · {fmtMin(t.month_minutes)}</td>
                <td data-label="Holat"><span>
                  {t.in_lesson && <span className="badge ok">darsda</span>}{" "}
                  <span className={"badge " + (t.is_active ? "" : "bad")}>{t.is_active ? "faol" : "bloklangan"}</span>
                </span></td>
                <td className="actions">
                  <button className="sm" onClick={() => { setErr(""); setEdit({ id: t.id, full_name: t.full_name, telegram_id: t.telegram_id?.toString() ?? "", tg_username: t.tg_username ?? "", phone: t.phone ?? "", note: t.note ?? "", is_active: t.is_active }); }}>Tahrir</button>
                  <button className="sm" onClick={() => toggle(t)}>{t.is_active ? "Bloklash" : "Faollashtirish"}</button>
                  <button className="sm danger" onClick={() => remove(t)}>O'chirish</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data?.length === 0 && <div className="empty">Hali o'qituvchi qo'shilmagan</div>}
      </div>

      {edit && (
        <Modal title={edit.id ? "O'qituvchini tahrirlash" : "Yangi o'qituvchi"} onClose={() => setEdit(null)}>
          <Field label="F.I.Sh. *"><input value={edit.full_name} onChange={(e) => setEdit({ ...edit, full_name: e.target.value })} /></Field>
          <Field label="Telegram ID (raqam)"><input value={edit.telegram_id} onChange={(e) => setEdit({ ...edit, telegram_id: e.target.value.replace(/\D/g, "") })} placeholder="masalan: 123456789" /></Field>
          <Field label="yoki Telegram @username"><input value={edit.tg_username} onChange={(e) => setEdit({ ...edit, tg_username: e.target.value })} placeholder="@username" /></Field>
          <div className="hint">ID ni bilmasangiz, @username kiriting: o'qituvchi botga /start bosganda avtomatik bog'lanadi. Botga /id yozib ham ID ni bilish mumkin.</div>
          <Field label="Telefon"><input value={edit.phone} onChange={(e) => setEdit({ ...edit, phone: e.target.value })} /></Field>
          <Field label="Izoh"><input value={edit.note} onChange={(e) => setEdit({ ...edit, note: e.target.value })} /></Field>
          {err && <div className="err">{err}</div>}
          <div className="row actions-bar">
            <button onClick={() => setEdit(null)}>Bekor</button>
            <button className="primary" disabled={edit.full_name.trim().length < 2} onClick={save}>Saqlash</button>
          </div>
        </Modal>
      )}
    </>
  );
}
