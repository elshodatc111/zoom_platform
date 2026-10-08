import { Fragment, useState } from "react";
import { api, fmtDT, fmtMin, fmtTime } from "../api";
import { Blocks, SESSION_LABEL, useLoad } from "../ui";

export default function Sessions() {
  const [page, setPage] = useState(1);
  const [teacher, setTeacher] = useState("");
  const [status, setStatus] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  const teachers = useLoad<any[]>("/teachers");

  const qs = new URLSearchParams({ page: String(page), size: "20" });
  if (teacher) qs.set("teacher_id", teacher);
  if (status) qs.set("status", status);
  if (from) qs.set("date_from", new Date(from + "T00:00:00+05:00").toISOString());
  if (to) qs.set("date_to", new Date(new Date(to + "T00:00:00+05:00").getTime() + 86400000).toISOString());
  const { data, error, reload } = useLoad<any>("/sessions?" + qs.toString(), 10000);
  const pages = data ? Math.max(1, Math.ceil(data.total / 20)) : 1;

  const stop = async (id: number) => {
    if (!confirm("Darsni to'xtatasizmi?")) return;
    await api(`/sessions/${id}/stop`, { method: "POST" });
    reload();
  };

  return (
    <>
      <div className="page-head"><h2>Darslar tarixi</h2></div>
      <div className="card filters">
        <select value={teacher} onChange={(e) => { setTeacher(e.target.value); setPage(1); }}>
          <option value="">Barcha o'qituvchilar</option>
          {(teachers.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.full_name}</option>)}
        </select>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">Barcha holatlar</option>
          {Object.entries(SESSION_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <input type="date" value={from} onChange={(e) => { setFrom(e.target.value); setPage(1); }} />
        <span className="muted sep">—</span>
        <input type="date" value={to} onChange={(e) => { setTo(e.target.value); setPage(1); }} />
      </div>
      <div className="card table-wrap">
        {error && <div className="err">{error}</div>}
        <table>
          <thead><tr><th>#</th><th>O'qituvchi</th><th>Boshlangan</th><th>Bloklar</th><th>Rejalangan</th><th>Haqiqiy</th><th>Holat</th><th></th></tr></thead>
          <tbody>
            {(data?.items ?? []).map((s: any) => (
              <Fragment key={s.id}>
                <tr onClick={() => setOpen(open === s.id ? null : s.id)} style={{ cursor: "pointer" }}>
                  <td className="idc">{s.id}</td><td className="title">{s.teacher}</td><td data-label="Boshlangan">{fmtDT(s.started_at)}</td>
                  <td data-label="Bloklar"><Blocks blocks={s.blocks} /></td>
                  <td data-label="Rejalangan">{fmtMin(s.planned_minutes)}</td>
                  <td data-label="Haqiqiy">{s.status === "active" ? "…" : fmtMin(s.actual_minutes)}</td>
                  <td data-label="Holat"><span className={"badge " + (s.status === "active" ? "ok" : s.status === "failed" ? "bad" : "")}>{SESSION_LABEL[s.status]}</span></td>
                  <td className="actions">{s.status === "active" && <button className="sm danger" onClick={(e) => { e.stopPropagation(); stop(s.id); }}>To'xtatish</button>}</td>
                </tr>
                {open === s.id && (
                  <tr className="detail"><td colSpan={8}>
                    <table className="inner">
                      <thead><tr><th>Blok</th><th>Akkaunt</th><th>Reja</th><th>Yaratildi</th><th>Meeting ID</th><th>Holat</th></tr></thead>
                      <tbody>{s.blocks.map((b: any) => (
                        <tr key={b.id}>
                          <td className="title">Blok {b.idx}</td><td data-label="Akkaunt">{b.account ?? "—"}</td>
                          <td data-label="Reja">{fmtTime(b.planned_start)}–{fmtTime(b.planned_end)}</td>
                          <td data-label="Yaratildi">{fmtTime(b.created_real_at)}</td><td data-label="Meeting ID">{b.meeting_id ?? "—"}</td>
                          <td data-label="Holat"><span>{b.status}{b.error && <span className="err"> {b.error}</span>}</span></td>
                        </tr>))}</tbody>
                    </table>
                  </td></tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
        {data?.items.length === 0 && <div className="empty">Darslar topilmadi</div>}
        <div className="pager">
          <button disabled={page <= 1} onClick={() => setPage(page - 1)}>←</button>
          <span className="muted">{page} / {pages}</span>
          <button disabled={page >= pages} onClick={() => setPage(page + 1)}>→</button>
        </div>
      </div>
    </>
  );
}
