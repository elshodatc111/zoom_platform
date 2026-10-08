import { api, fmtMin, fmtTime } from "../api";
import { Blocks, Stat, useLoad } from "../ui";

export default function Dashboard() {
  const { data, error, reload } = useLoad<any>("/dashboard", 5000);
  if (!data) return <div className="muted" style={{ padding: 20 }}>{error || "Yuklanmoqda…"}</div>;
  const c = data.capacity;

  const stop = async (id: number) => {
    if (!confirm("Darsni to'xtatasizmi?")) return;
    await api(`/sessions/${id}/stop`, { method: "POST" });
    reload();
  };

  return (
    <>
      <div className="page-head"><h2>Bosh sahifa</h2></div>
      {!data.bot_running && <div className="card err">Telegram bot ishlamayapti: .env da BOT_TOKEN ko'rsatilmagan.</div>}
      <div className="grid">
        <Stat hero label="Hozir o'tayotgan darslar" value={data.active_sessions.length} />
        <Stat label="Bo'sh akkauntlar" value={`${c.free} / ${c.total}`} sub={`band: ${c.busy}, xatoli: ${c.total - c.healthy}`} />
        <Stat label="Faol o'qituvchilar" value={data.teachers} />
        <Stat label="Bugun" value={`${data.today.sessions} dars`} sub={fmtMin(data.today.actual_minutes)} />
        <Stat label="Shu oy" value={`${data.month.sessions} dars`} sub={fmtMin(data.month.actual_minutes)} />
      </div>

      <div className="page-head" style={{ margin: "22px 0 12px" }}><h3 style={{ fontSize: 19, fontWeight: 800 }}>Faol darslar</h3></div>
      {data.active_sessions.length === 0 ? (
        <div className="card empty">Hozir faol dars yo'q. O'qituvchi botda "Dars boshlash"ni bosganda shu yerda ko'rinadi.</div>
      ) : data.active_sessions.map((s: any) => {
        const end = new Date(new Date(s.started_at).getTime() + s.planned_minutes * 60000).toISOString();
        return (
          <div className="card live" key={s.id}>
            <div className="live-top">
              <div>
                <div className="live-name"><span className="pulse" />{s.teacher}</div>
                <div className="live-time">{fmtTime(s.started_at)} – {fmtTime(end)}</div>
              </div>
              <button className="sm danger" onClick={() => stop(s.id)}>To'xtatish</button>
            </div>
            <Blocks blocks={s.blocks} />
          </div>
        );
      })}
    </>
  );
}
