"use client";
import { useEffect, useRef } from "react";
import clsx from "clsx";
import { Terminal } from "lucide-react";
import type { LogEvent } from "@/lib/ws";

function fmtTs(iso: string) {
  const d = new Date(iso);
  const h = String(d.getHours()).padStart(2, "0");
  const m = String(d.getMinutes()).padStart(2, "0");
  const s = String(d.getSeconds()).padStart(2, "0");
  return `${h}:${m}:${s}`;
}

export function BotLogs({ logs }: { logs: LogEvent[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [logs]);

  return (
    <div className="card rim p-0 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-gradient-to-r from-white/[0.02] to-transparent">
        <div className="flex items-center gap-2">
          <span className="w-7 h-7 rounded-lg grid place-items-center bg-white/5 text-gray-300">
            <Terminal size={14} />
          </span>
          <h3 className="font-semibold text-white text-sm tracking-wide">Engine Logs</h3>
        </div>
        <span className="text-[11px] text-gray-500 uppercase tracking-wider">{logs.length} entries</span>
      </div>
      <div
        ref={ref}
        className="bg-[#070a10] max-h-[420px] min-h-[280px] overflow-y-auto py-2"
      >
        {logs.length === 0 && (
          <div className="px-4 py-10 text-center text-gray-500 text-sm">
            Waiting for engine to start…
          </div>
        )}
        {logs.map((e, i) => (
          <div key={i} className={clsx("log-line")}>
            <span className="text-gray-600">{fmtTs(e.ts)}</span>
            <span className="text-gray-700"> │ </span>
            <span className={clsx(`log-${e.level}`)}>{e.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

