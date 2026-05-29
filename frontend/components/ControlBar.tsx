"use client";
import { useEffect, useRef, useState } from "react";
import { Square, Trash2, Play, ChevronDown, Check, Cpu, RotateCw, Zap } from "lucide-react";
import clsx from "clsx";
import { api } from "@/lib/api";
import { StrategyBadge } from "./StrategyBadge";
import { StatusPill } from "./StatusPill";

const STRATEGY_DESC: Record<string, string> = {
  conservative: "EMA 9/34 · slower, safer trend filter",
  balanced: "EMA 9/21 · default, balanced setups",
  aggressive: "EMA 5/13 · fast crossovers, more trades",
};

export function ControlBar({
  status, strategy, strategies, onChanged, onManualTrade,
}: {
  status: string;
  strategy: string;
  strategies: string[];
  onChanged: () => void;
  onManualTrade?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [picked, setPicked] = useState(strategy);
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setPicked(strategy); }, [strategy]);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    try { await fn(); } catch (e) { alert(String(e)); }
    finally { setBusy(false); onChanged(); }
  }

  async function restart() {
    setBusy(true);
    try { await api.stop().catch(() => {}); await api.start(picked); }
    catch (e) { alert(String(e)); }
    finally { setBusy(false); onChanged(); }
  }

  const running = status === "running";
  const options = strategies.length ? strategies : ["conservative", "balanced", "aggressive"];

  return (
    <div className="card rim flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-7 h-7 rounded-lg grid place-items-center bg-white/5 text-gray-300">
            <Cpu size={14} />
          </span>
          <h3 className="font-semibold text-white text-sm tracking-wide">Engine Control</h3>
        </div>
        <div className="flex items-center gap-2">
          <StrategyBadge name={strategy} />
          <StatusPill status={status} />
        </div>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div ref={menuRef} className="relative flex-1 min-w-[200px]">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="w-full bg-white/[0.03] hover:bg-white/[0.06] border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white flex items-center justify-between transition"
          >
            <span className="flex flex-col items-start leading-tight">
              <span className="text-[10px] uppercase tracking-wider text-gray-500">Strategy</span>
              <span className="font-medium">{picked || "select"}</span>
            </span>
            <ChevronDown size={14} className={clsx("transition", open && "rotate-180")} />
          </button>
          {open && (
            <div className="absolute z-50 mt-1 w-full rounded-lg border border-white/10 bg-[#0d121b] shadow-2xl overflow-hidden">
              {options.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => { setPicked(s); setOpen(false); }}
                  className={clsx(
                    "w-full text-left px-3 py-2.5 text-sm flex items-start justify-between hover:bg-white/5 transition",
                    s === picked ? "text-accent bg-accent/5" : "text-white",
                  )}
                >
                  <span className="flex flex-col">
                    <span className="font-medium">{s}</span>
                    <span className="text-[11px] text-gray-500">{STRATEGY_DESC[s]}</span>
                  </span>
                  {s === picked && <Check size={14} className="mt-1" />}
                </button>
              ))}
            </div>
          )}
        </div>

        {!running ? (
          <button
            disabled={busy}
            onClick={() => run(() => api.start(picked))}
            className="px-4 py-2.5 rounded-lg bg-accent/15 text-accent border border-accent/30 inline-flex items-center gap-2 text-sm font-medium hover:bg-accent/25 transition disabled:opacity-50"
          >
            <Play size={14} /> Start
          </button>
        ) : (
          <>
            <button
              disabled={busy}
              onClick={restart}
              className="px-3 py-2.5 rounded-lg bg-info/10 text-info border border-info/30 inline-flex items-center gap-2 text-sm font-medium hover:bg-info/20 transition disabled:opacity-50"
              title="Stop and start with current strategy"
            >
              <RotateCw size={14} /> Restart
            </button>
            <button
              disabled={busy}
              onClick={() => run(api.stop)}
              className="px-4 py-2.5 rounded-lg bg-danger/15 text-danger border border-danger/30 inline-flex items-center gap-2 text-sm font-medium hover:bg-danger/25 transition disabled:opacity-50"
            >
              <Square size={14} /> Stop
            </button>
          </>
        )}
        <button
          disabled={busy}
          onClick={() => {
            if (confirm("Delete bot state? This clears trade & log history.")) run(api.remove);
          }}
          className="px-3 py-2.5 rounded-lg border border-white/10 inline-flex items-center gap-2 text-sm text-gray-400 hover:bg-white/5 transition disabled:opacity-50"
        >
          <Trash2 size={14} /> Reset
        </button>
      </div>

      {onManualTrade && (
        <button
          onClick={onManualTrade}
          className="w-full px-4 py-3 rounded-lg bg-gradient-to-r from-amber-500/20 via-yellow-500/20 to-amber-500/20 hover:from-amber-500/30 hover:via-yellow-500/30 hover:to-amber-500/30 border border-amber-500/40 text-amber-300 inline-flex items-center justify-center gap-2 text-sm font-semibold transition shadow-lg shadow-amber-500/10"
        >
          <Zap size={16} /> Place Manual Trade
        </button>
      )}
    </div>
  );
}
