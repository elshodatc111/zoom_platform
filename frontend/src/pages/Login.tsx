import { FormEvent, useState } from "react";
import { api } from "../api";
import { LogoMark } from "../icons";

export default function Login({ onLogin }: { onLogin: (u: any) => void }) {
  const [username, setU] = useState("");
  const [password, setP] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      onLogin(await api("/auth/login", { method: "POST", body: { username, password } }));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <div className="login-hero">
        <span className="logo"><LogoMark /></span>
        <h1>Zoom Platform</h1>
        <p>Dars havolalari har 40 daqiqada avtomatik yaratiladi va o'qituvchilarga yuboriladi.</p>
        <div className="blocks" aria-hidden="true">
          <span className="blk on" /><span className="blk on" /><span className="blk on" /><span className="blk" />
        </div>
      </div>
      <form className="login" onSubmit={submit}>
        <h2>Admin panelga kirish</h2>
        <label htmlFor="u">Login</label>
        <input id="u" value={username} onChange={(e) => setU(e.target.value)} autoComplete="username" autoCapitalize="none" autoCorrect="off" />
        <label htmlFor="p">Parol</label>
        <input id="p" type="password" value={password} onChange={(e) => setP(e.target.value)} autoComplete="current-password" />
        {err && <div className="err">{err}</div>}
        <button className="primary" disabled={busy || !username || !password}>{busy ? "Kirilmoqda…" : "Kirish"}</button>
      </form>
    </div>
  );
}
