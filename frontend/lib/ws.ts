import { api } from "./api";

export type LogEvent = {
  ts: string;
  level: "INFO" | "ANALYSIS" | "BUY" | "SELL" | "PROFIT" | "LOSS" | "ERROR";
  category: string;
  message: string;
};

export function connectLogs(onLog: (e: LogEvent) => void, onState: (s: "open" | "closed") => void) {
  const url = api.base.replace(/^http/, "ws") + `/ws?token=${encodeURIComponent(api.token)}`;
  let ws: WebSocket | null = null;
  let closed = false;

  const open = () => {
    ws = new WebSocket(url);
    ws.onopen = () => onState("open");
    ws.onclose = () => {
      onState("closed");
      if (!closed) setTimeout(open, 2000);
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "log") onLog(msg.data);
      } catch {}
    };
  };
  open();
  return () => {
    closed = true;
    ws?.close();
  };
}
