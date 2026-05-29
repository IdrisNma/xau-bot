"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Target, Zap, DollarSign, Wallet, PiggyBank, TrendingUp, Activity } from "lucide-react";
import clsx from "clsx";
import { api } from "@/lib/api";
import { connectLogs, type LogEvent } from "@/lib/ws";
import { StatCard } from "@/components/StatCard";
import { TradeCard } from "@/components/TradeCard";
import { BotLogs } from "@/components/BotLogs";
import { ControlBar } from "@/components/ControlBar";
import { Sparkline } from "@/components/Sparkline";
import { ManualTradeModal } from "@/components/ManualTradeModal";

export default function Dashboard() {
  const [bot, setBot] = useState<any>({ strategy: "balanced", status: "stopped", strategies: [] });
  const [stats, setStats] = useState<any>({ trades: 0, win_rate: 0, profit: 0 });
  const [equity, setEquity] = useState<number[]>([]);
  const [logs, setLogs] = useState<LogEvent[]>([]);
  const [wsState, setWsState] = useState<"open" | "closed">("closed");
  const [showTrade, setShowTrade] = useState(false);
  const logsCapRef = useRef(2000);

  const netPnl =
    stats.balance != null && stats.starting_equity != null
      ? Number(stats.balance) - Number(stats.starting_equity)
      : null;

  const refresh = useCallback(async () => {
    const [bRes, sRes, eRes] = await Promise.allSettled([api.bot(), api.stats(), api.equity(200)]);
    if (bRes.status === "fulfilled") setBot(bRes.value);
    if (sRes.status === "fulfilled") setStats(sRes.value);
    if (eRes.status === "fulfilled") setEquity((eRes.value as any[]).map((r) => Number(r.equity)));
  }, []);

  useEffect(() => {
    refresh();
    api.logs(200).then((rows) => setLogs(rows as LogEvent[])).catch(() => {});
    const stop = connectLogs(
      (e) => setLogs((prev) => {
        const next = [...prev, e];
        if (next.length > logsCapRef.current) next.splice(0, next.length - logsCapRef.current);
        return next;
      }),
      setWsState,
    );
    const t = setInterval(refresh, 5000);
    return () => { stop(); clearInterval(t); };
  }, [refresh]);

  const balance = stats.balance != null ? Number(stats.balance) : null;
  const starting = stats.starting_equity != null ? Number(stats.starting_equity) : null;
  const pnlPct =
    netPnl != null && starting && starting > 0 ? (netPnl / starting) * 100 : null;

  return (
    <main className="max-w-6xl mx-auto px-4 md:px-6 py-6 space-y-5">
      {/* Header */}
      <header className="flex items-center justify-between fade-up">
        <div className="flex items-center gap-3">
          <div className="relative w-9 h-9 rounded-xl bg-gradient-to-br from-accent via-info to-[var(--gold)] grid place-items-center shadow-lg shadow-accent/20">
            <Activity size={16} className="text-[#08110d]" strokeWidth={2.5} />
          </div>
          <div className="leading-tight">
            <div className="font-semibold tracking-wide text-white text-[15px]">HORIZON</div>
            <div className="text-[10px] text-gray-500 uppercase tracking-[0.2em]">XAU · Quant Engine</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {bot.symbol && (
            <span className="hidden sm:inline-flex text-[10px] px-2.5 py-1 rounded-md border border-white/10 text-gray-400 uppercase tracking-wider">
              {bot.symbol}
            </span>
          )}
          <span
            className={clsx(
              "text-[10px] px-2.5 py-1 rounded-md border uppercase tracking-wider",
              bot.testnet
                ? "border-warn/30 bg-warn/10 text-warn"
                : "border-accent/30 bg-accent/10 text-accent",
            )}
          >
            {bot.testnet ? "Testnet" : "Live"}
          </span>
          <span className="inline-flex items-center gap-1.5 text-[10px] px-2.5 py-1 rounded-md border border-white/10 text-gray-400 uppercase tracking-wider">
            <span className={clsx("live-dot", wsState !== "open" && "idle")} />
            {wsState === "open" ? "stream" : "offline"}
          </span>
          <button
            onClick={() => setShowTrade(true)}
            className="inline-flex items-center gap-1.5 text-[10px] px-2.5 py-1 rounded-md border border-accent/30 bg-accent/10 text-accent uppercase tracking-wider hover:bg-accent/20 transition"
          >
            <Zap size={10} /> Manual
          </button>
        </div>
      </header>

      {showTrade && (
        <ManualTradeModal onClose={() => setShowTrade(false)} onDone={refresh} />
      )}

      {/* Hero: Balance + Sparkline + Control */}
      <section className="relative z-30 grid grid-cols-1 lg:grid-cols-3 gap-4 fade-up delay-1">
        <div className="lg:col-span-2 card card-hover rim flex flex-col gap-4">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-gray-500">Account Balance</div>
              <div className="num num-xl text-white mt-1">
                ${balance != null ? balance.toFixed(2) : "—"}
              </div>
              {starting != null && (
                <div className="text-[11px] text-gray-500 mt-1">
                  Starting equity ${starting.toFixed(2)}
                </div>
              )}
            </div>
            {netPnl != null && (
              <div
                className={clsx(
                  "px-3 py-2 rounded-xl border flex flex-col items-end",
                  netPnl >= 0
                    ? "border-accent/30 bg-accent/10 text-accent"
                    : "border-danger/30 bg-danger/10 text-danger",
                )}
              >
                <div className="text-[10px] uppercase tracking-wider opacity-80">Net PnL</div>
                <div className="num font-semibold text-lg">
                  {netPnl >= 0 ? "+" : ""}${netPnl.toFixed(2)}
                </div>
                {pnlPct != null && (
                  <div className="text-[10px] opacity-80">
                    {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%
                  </div>
                )}
              </div>
            )}
          </div>
          <Sparkline
            data={equity}
            stroke={netPnl != null && netPnl < 0 ? "#ef4444" : "#22d3a8"}
            fillFrom={netPnl != null && netPnl < 0 ? "rgba(239,68,68,0.30)" : "rgba(34,211,168,0.30)"}
            fillTo={netPnl != null && netPnl < 0 ? "rgba(239,68,68,0)" : "rgba(34,211,168,0)"}
          />
        </div>
        <ControlBar
          status={bot.status}
          strategy={bot.strategy}
          strategies={bot.strategies || []}
          onChanged={refresh}
        />
      </section>

      {/* Stats grid */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-3 fade-up delay-2">
        <StatCard
          icon={PiggyBank}
          label="Starting"
          value={starting != null ? `$${starting.toFixed(2)}` : "—"}
          tone="gold"
        />
        <StatCard
          icon={DollarSign}
          label="Realized Profit"
          value={`${(stats.profit ?? 0) >= 0 ? "+" : ""}$${(stats.profit ?? 0).toFixed(2)}`}
          sub="from closed trades"
          tone={(stats.profit ?? 0) >= 0 ? "good" : "bad"}
        />
        <StatCard
          icon={Target}
          label="Trades"
          value={String(stats.trades ?? 0)}
          sub={`${stats.closed ?? 0} closed`}
        />
        <StatCard
          icon={Zap}
          label="Win Rate"
          value={`${stats.win_rate ?? 0}%`}
          tone="good"
        />
      </section>

      {/* Last trade */}
      <section className="fade-up delay-3">
        <TradeCard trade={stats.last_trade} />
      </section>

      {/* Logs */}
      <section className="fade-up delay-4">
        <BotLogs logs={logs} />
      </section>

      <footer className="text-center text-[11px] text-gray-600 pt-4 pb-2 tracking-wider uppercase">
        Horizon Quant Engine · paper-mode
      </footer>
    </main>
  );
}
