import { useState } from "react";
import { api, fmtDT } from "../api";
import { Field, Modal, useLoad } from "../ui";

type A = { id?: number; name: string; email: string; zoom_account_id: string; client_id: string; client_secret: string };
const empty: A = { name: "", email: "", zoom_account_id: "", client_id: "", client_secret: "" };

export default function Accounts() {
  const { data, error, reload } = useLoad<any[]>("/accounts", 10000);
  const [edit, setEdit] = useState<A | null>(null);
  const [err, setErr] = useState("");
  const [testing, setTesting] = useState<number | null>(null);
  const [result, setResult] = useState<Record<number, string>>({});

  const save = async () => {
    if (!edit) return;
    try {
      if (edit.id) {
        const body: any = { ...edit };
        delete body.id;
        if (!body.client_secret) delete body.client_secret;
        await api(`/accounts/${edit.id}`, { method: "PATCH", body });
      } else await api("/accounts", { method: "POST", body: edit });
      setEdit(null);
      setErr("");
      reload();
    } catch (e: any) {
      setErr(e.message);
    }
  };

  const test = async (a: any) => {
    setTesting(a.id);
    try {
      const r = await api(`/accounts/${a.id}/test`, { method: "POST" });
      setResult((p) => ({ ...p, [a.id]: (r.ok ? "✅ " : "❌ ") + r.message }));
    } finally {
      setTesting(null);
      reload();
    }
  };

  const toggle = async (a: any) => { await api(`/accounts/${a.id}`, { method: "PATCH", body: { is_active: !a.is_active } }); reload(); };
  const remove = async (a: any) => {
    if (!confirm(`${a.name} o'chirilsinmi?`)) return;
    alert((await api(`/accounts/${a.id}`, { method: "DELETE" })).message);
    reload();
  };

  const st = (a: any) => !a.is_active ? <span className="badge">o'chirilgan</span>
    : a.status === "ok" ? <span className="badge ok">ishlaydi</span>
    : a.status === "error" ? <span className="badge bad">xato</span> : <span className="badge warn">tekshirilmagan</span>;

  return (
    <>
      <div className="page-head">
        <h2>Zoom akkauntlar</h2>
        <button className="primary" onClick={() => { setErr(""); setEdit({ ...empty }); }}>+ Akkaunt qo'shish</button>
      </div>
      <div className="card table-wrap">
        {error && <div className="err">{error}</div>}
        <table>
          <thead><tr><th>Nomi</th><th>Zoom email</th><th>Holat</th><th>Band</th><th>Oxirgi tekshiruv</th><th></th></tr></thead>
          <tbody>
            {(data ?? []).map((a) => (
              <tr key={a.id}>
                <td className="title">{a.name}</td>
                <td data-label="Zoom email">{a.email}</td>
                <td data-label="Holat"><span>{st(a)}{a.last_error && <div className="err" style={{ fontSize: 12, margin: 0 }}>{a.last_error}</div>}</span></td>
                <td data-label="Band">{a.busy ? <span className="badge warn">band</span> : <span className="muted">bo'sh</span>}</td>
                <td data-label="Oxirgi tekshiruv"><span>{fmtDT(a.last_checked_at)}{result[a.id] && <div style={{ fontSize: 12 }}>{result[a.id]}</div>}</span></td>
                <td className="actions">
                  <button className="sm" disabled={testing === a.id} onClick={() => test(a)}>{testing === a.id ? "…" : "Tekshirish"}</button>
                  <button className="sm" onClick={() => { setErr(""); setEdit({ id: a.id, name: a.name, email: a.email, zoom_account_id: a.zoom_account_id, client_id: a.client_id, client_secret: "" }); }}>Tahrir</button>
                  <button className="sm" onClick={() => toggle(a)}>{a.is_active ? "O'chirib qo'yish" : "Yoqish"}</button>
                  <button className="sm danger" onClick={() => remove(a)}>O'chirish</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data?.length === 0 && <div className="empty">Akkaunt yo'q. Zoom Marketplace'da Server-to-Server OAuth ilovasi yarating va ma'lumotlarini kiriting.</div>}
      </div>

      {edit && (
        <Modal title={edit.id ? "Akkauntni tahrirlash" : "Yangi Zoom akkaunt"} onClose={() => setEdit(null)}>
          <Field label="Ichki nomi * (masalan: zoom-01)"><input value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /></Field>
          <Field label="Zoom foydalanuvchi emaili * (akkaunt egasi)"><input value={edit.email} onChange={(e) => setEdit({ ...edit, email: e.target.value })} /></Field>
          <Field label="Account ID *"><input value={edit.zoom_account_id} onChange={(e) => setEdit({ ...edit, zoom_account_id: e.target.value })} /></Field>
          <Field label="Client ID *"><input value={edit.client_id} onChange={(e) => setEdit({ ...edit, client_id: e.target.value })} /></Field>
          <Field label={edit.id ? "Client Secret (o'zgartirmoqchi bo'lsangiz kiriting)" : "Client Secret *"}>
            <input type="password" value={edit.client_secret} onChange={(e) => setEdit({ ...edit, client_secret: e.target.value })} autoComplete="new-password" />
          </Field>
          {err && <div className="err">{err}</div>}
          <div className="row actions-bar">
            <button onClick={() => setEdit(null)}>Bekor</button>
            <button className="primary" disabled={!edit.name || !edit.email || !edit.zoom_account_id || !edit.client_id || (!edit.id && !edit.client_secret)} onClick={save}>Saqlash</button>
          </div>
        </Modal>
      )}
    </>
  );
}
