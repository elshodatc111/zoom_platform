import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fmtMin } from "../api";
import { useLoad } from "../ui";

const iso = (d: Date) => d.toISOString().slice(0, 10);

export default function Stats() {
  const today = new Date();
  const [from, setFrom] = useState(iso(new Date(today.getTime() - 29 * 86400000)));
  const [to, setTo] = useState(iso(today));
  const [group, setGroup] = useState("day");
  const [teacher, setTeacher] = useState("");

  const range = `date_from=${encodeURIComponent(new Date(from + "T00:00:00+05:00").toISOString())}&date_to=${encodeURIComponent(new Date(new Date(to + "T00:00:00+05:00").getTime() + 86400000).toISOString())}`;
  const per = useLoad<any[]>(`/stats/teachers?${range}`);
  const series = useLoad<any[]>(`/stats/timeseries?group=${group}&${range}${teacher ? "&teacher_id=" + teacher : ""}`);

  const rows = (per.data ?? []).filter((r) => r.sessions > 0 || r.is_active);
  const tot = rows.reduce((a, r) => ({ s: a.s + r.sessions, b: a.b + r.blocks, p: a.p + r.planned_minutes, m: a.m + r.actual_minutes }), { s: 0, b: 0, p: 0, m: 0 });
  const chart = (series.data ?? []).map((r) => ({ ...r, soat: +(r.actual_minutes / 60).toFixed(1) }));

  return (
    <>
      <div className="page-head">
        <h2>Statistika</h2>
        <a className="btn" href={`/api/stats/export?${range}`}>⬇ Excel (xlsx)</a>
      </div>
      <div className="card filters">
        <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        <span className="muted sep">—</span>
        <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        <select value={group} onChange={(e) => setGroup(e.target.value)}>
          <option value="day">Kunlar bo'yicha</option><option value="week">Haftalar bo'yicha</option><option value="month">Oylar bo'yicha</option>
        </select>
        <select value={teacher} onChange={(e) => setTeacher(e.target.value)}>
          <option value="">Grafik: barcha o'qituvchilar</option>
          {(per.data ?? []).map((t) => <option key={t.teacher_id} value={t.teacher_id}>{t.full_name}</option>)}
        </select>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Dars soatlari</h3>
        {chart.length === 0 ? <div className="empty">Ma'lumot yo'q</div> : (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chart} margin={{ left: -22, right: 4, top: 6 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#8884" />
              <XAxis dataKey="period" fontSize={12} />
              <YAxis fontSize={12} />
              <Tooltip cursor={{ fill: "#8884" }} contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, color: "var(--text)" }} labelStyle={{ color: "var(--text)", fontWeight: 700 }} />
              <Legend />
              <Bar dataKey="soat" name="Soat" fill="#2563eb" radius={[4, 4, 0, 0]} />
              <Bar dataKey="sessions" name="Darslar soni" fill="#16a34a" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="card table-wrap">
        <h3 style={{ marginTop: 0 }}>O'qituvchilar kesimida</h3>
        <table>
          <thead><tr><th>O'qituvchi</th><th>Darslar</th><th>Bloklar</th><th>Rejalangan</th><th>Haqiqiy</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.teacher_id}><td className="title">{r.full_name}</td><td data-label="Darslar">{r.sessions}</td><td data-label="Bloklar">{r.blocks}</td><td data-label="Rejalangan">{fmtMin(r.planned_minutes)}</td><td data-label="Haqiqiy">{fmtMin(r.actual_minutes)}</td></tr>
            ))}
            <tr style={{ fontWeight: 800 }}><td className="title">Jami</td><td data-label="Darslar">{tot.s}</td><td data-label="Bloklar">{tot.b}</td><td data-label="Rejalangan">{fmtMin(tot.p)}</td><td data-label="Haqiqiy">{fmtMin(tot.m)}</td></tr>
          </tbody>
        </table>
      </div>
    </>
  );
}
