const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TOKEN = process.env.NEXT_PUBLIC_API_TOKEN || "change-me-please";

const authHeader = () => ({ Authorization: `Bearer ${TOKEN}` });

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const api = {
  base: API,
  token: TOKEN,
  bot: () => fetch(`${API}/bot`).then(j<any>),
  stats: () => fetch(`${API}/stats`).then(j<any>),
  trades: (limit = 20) => fetch(`${API}/trades?limit=${limit}`).then(j<any[]>),
  logs: (limit = 200) => fetch(`${API}/logs?limit=${limit}`).then(j<any[]>),
  equity: (limit = 200) => fetch(`${API}/equity?limit=${limit}`).then(j<any[]>),
  start: (strategy: string) =>
    fetch(`${API}/bot/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeader() },
      body: JSON.stringify({ strategy }),
    }).then(j<any>),
  stop: () => fetch(`${API}/bot/stop`, { method: "POST", headers: authHeader() }).then(j<any>),
  remove: () => fetch(`${API}/bot`, { method: "DELETE", headers: authHeader() }).then(j<any>),
};
