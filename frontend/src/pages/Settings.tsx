import { useState } from "react";
import { api, fmtDT } from "../api";
import { Field, Modal, useLoad } from "../ui";

export default function Settings({ me }: { me: string }) {
  const admins = useLoad<any[]>("/admins");
  const [page, setPage] = useState(1);
  const audit = useLoad<any>(`/audit?page=${page}&size=20`);
  const [pw, setPw] = useState({ old_password: "", new_password: "" });
  const [pwMsg, setPwMsg] = useState("");
  const [newAdmin, setNewAdmin] = useState<{ username: string; password: string } | null>(null);
  const [err, setErr] = useState("");

  const changePw = async () => {
    try {
      await api("/auth/change-password", { method: "POST", body: pw });
      setPwMsg("✅ Parol o'zgartirildi");
      setPw({ old_password: "", new_password: "" });
    } catch (e: any) {
      setPwMsg("❌ " + e.message);
    }
  };

  const addAdmin = async () => {
    try {
      await api("/admins", { method: "POST", body: newAdmin });
      setNewAdmin(null);
      setErr("");
      admins.reload();
    } catch (e: any) {
      setErr(e.message);
    }
  };

  const toggle = async (a: any) => {
    try { await api(`/admins/${a.id}`, { method: "PATCH", body: { is_active: !a.is_active } }); } catch (e: any) { alert(e.message); }
    admins.reload();
  };

  const pages = audit.data ? Math.max(1, Math.ceil(audit.data.total / 20)) : 1;

  return (
    <>
      <div className="page-head"><h2>Sozlamalar</h2></div>
      <div className="card" style={{ maxWidth: 460 }}>
        <h3 style={{ marginTop: 0 }}>Parolni almashtirish ({me})</h3>
        <Field label="Eski parol"><input type="password" value={pw.old_password} onChange={(e) => setPw({ ...pw, old_password: e.target.value })} /></Field>
        <Field label="Yangi parol (kamida 8 belgi)"><input type="password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
        {pwMsg && <div style={{ margin: "8px 0" }}>{pwMsg}</div>}
        <button className="primary" style={{ marginTop: 10 }} disabled={pw.new_password.length < 8 || !pw.old_password} onClick={changePw}>O'zgartirish</button>
      </div>

      <div className="card table-wrap">
        <div className="page-head" style={{ marginBottom: 6 }}>
          <h3 style={{ margin: 0 }}>Adminlar</h3>
          <button onClick={() => { setErr(""); setNewAdmin({ username: "", password: "" }); }}>+ Admin</button>
        </div>
        <table>
          <thead><tr><th>Login</th><th>Yaratilgan</th><th>Holat</th><th></th></tr></thead>
          <tbody>{(admins.data ?? []).map((a) => (
            <tr key={a.id}><td className="title">{a.username}</td><td data-label="Yaratilgan">{fmtDT(a.created_at)}</td>
              <td data-label="Holat"><span className={"badge " + (a.is_active ? "ok" : "bad")}>{a.is_active ? "faol" : "o'chirilgan"}</span></td>
              <td className="actions"><button className="sm" onClick={() => toggle(a)}>{a.is_active ? "O'chirib qo'yish" : "Yoqish"}</button></td></tr>
          ))}</tbody>
        </table>
      </div>

      <div className="card table-wrap">
        <h3 style={{ marginTop: 0 }}>Audit log</h3>
        <table>
          <thead><tr><th>Vaqt</th><th>Kim</th><th>Amal</th><th>Tafsilot</th></tr></thead>
          <tbody>{(audit.data?.items ?? []).map((r: any) => (
            <tr key={r.id}><td data-label="Vaqt">{fmtDT(r.created_at)}</td><td data-label="Kim">{r.actor}</td><td data-label="Amal">{r.action}</td><td className="muted" data-label="Tafsilot">{r.detail}</td></tr>
          ))}</tbody>
        </table>
        <div className="pager">
          <button disabled={page <= 1} onClick={() => setPage(page - 1)}>←</button>
          <span className="muted">{page} / {pages}</span>
          <button disabled={page >= pages} onClick={() => setPage(page + 1)}>→</button>
        </div>
      </div>

      {newAdmin && (
        <Modal title="Yangi admin" onClose={() => setNewAdmin(null)}>
          <Field label="Login"><input value={newAdmin.username} onChange={(e) => setNewAdmin({ ...newAdmin, username: e.target.value })} /></Field>
          <Field label="Parol (kamida 8 belgi)"><input type="password" value={newAdmin.password} onChange={(e) => setNewAdmin({ ...newAdmin, password: e.target.value })} /></Field>
          {err && <div className="err">{err}</div>}
          <div className="row actions-bar">
            <button onClick={() => setNewAdmin(null)}>Bekor</button>
            <button className="primary" disabled={newAdmin.username.length < 3 || newAdmin.password.length < 8} onClick={addAdmin}>Yaratish</button>
          </div>
        </Modal>
      )}
    </>
  );
}
