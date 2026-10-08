import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api } from "./api";
import { Icon, LogoMark } from "./icons";
import { Modal } from "./ui";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Teachers from "./pages/Teachers";
import Accounts from "./pages/Accounts";
import Sessions from "./pages/Sessions";
import Stats from "./pages/Stats";
import Settings from "./pages/Settings";

const MAIN = [
  { to: "/", label: "Bosh sahifa", short: "Bosh", icon: Icon.Home, end: true },
  { to: "/teachers", label: "O'qituvchilar", short: "Ustozlar", icon: Icon.Users },
  { to: "/accounts", label: "Zoom akkauntlar", short: "Akkaunt", icon: Icon.Video },
  { to: "/sessions", label: "Darslar tarixi", short: "Darslar", icon: Icon.Clock },
];
const EXTRA = [
  { to: "/stats", label: "Statistika", icon: Icon.Chart },
  { to: "/settings", label: "Sozlamalar", icon: Icon.Gear },
];

export default function App() {
  const [user, setUser] = useState<{ username: string } | null | undefined>(undefined);
  const [more, setMore] = useState(false);
  const loc = useLocation();
  const nav = useNavigate();

  useEffect(() => {
    api("/auth/me").then(setUser).catch(() => setUser(null));
    const h = () => setUser(null);
    window.addEventListener("unauthorized", h);
    return () => window.removeEventListener("unauthorized", h);
  }, []);
  useEffect(() => { setMore(false); window.scrollTo(0, 0); }, [loc.pathname]);

  if (user === undefined) return null;
  if (!user) return <Login onLogin={setUser} />;

  const logout = async () => {
    await api("/auth/logout", { method: "POST" });
    setUser(null);
  };
  const moreActive = EXTRA.some((e) => loc.pathname.startsWith(e.to));
  const initial = user.username.slice(0, 1).toUpperCase();

  return (
    <div className="layout">
      {/* Kompyuter: yon panel */}
      <aside className="side">
        <div className="brand"><span className="logo"><LogoMark /></span>Zoom Platform</div>
        <nav>
          {[...MAIN, ...EXTRA].map((n) => (
            <NavLink key={n.to} to={n.to} end={(n as any).end}><n.icon />{n.label}</NavLink>
          ))}
        </nav>
        <div className="me"><span className="avatar" style={{ background: "var(--primary)" }}>{initial}</span>{user.username}<button className="sm" onClick={logout}>Chiqish</button></div>
      </aside>

      {/* Telefon: yuqori panel */}
      <header className="topbar">
        <div className="brand"><span className="logo"><LogoMark /></span>Zoom Platform</div>
        <div className="who"><span className="avatar">{initial}</span></div>
      </header>

      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/teachers" element={<Teachers />} />
          <Route path="/accounts" element={<Accounts />} />
          <Route path="/sessions" element={<Sessions />} />
          <Route path="/stats" element={<Stats />} />
          <Route path="/settings" element={<Settings me={user.username} />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>

      {/* Telefon: pastki navigatsiya */}
      <nav className="tabbar" aria-label="Asosiy menyu">
        {MAIN.map((n) => (
          <NavLink key={n.to} to={n.to} end={(n as any).end}><n.icon />{n.short}</NavLink>
        ))}
        <button className={moreActive ? "active" : ""} onClick={() => setMore(true)}><Icon.Grid />Yana</button>
      </nav>

      {more && (
        <Modal title="Menyu" onClose={() => setMore(false)}>
          <div className="more-list" style={{ marginTop: 14 }}>
            {EXTRA.map((e) => (
              <a key={e.to} href={e.to} onClick={(ev) => { ev.preventDefault(); nav(e.to); }}><e.icon />{e.label}</a>
            ))}
            <button className="item danger" onClick={logout}><Icon.Out />Chiqish ({user.username})</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
