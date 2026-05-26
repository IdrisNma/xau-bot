import clsx from "clsx";
import { TrendingUp, TrendingDown, Circle } from "lucide-react";

type Trade = {
  side: "BUY" | "SELL";
  symbol: string;
  entry_price: number;
  exit_price?: number | null;
  pnl?: number | null;
  outcome?: string | null;
  qty?: number | null;
  sl?: number | null;
  tp?: number | null;
  strategy?: string | null;
};

export function TradeCard({ trade }: { trade: Trade | null | undefined }) {
  if (!trade) {
    return (
      <div className="card rim text-center text-sm text-gray-500 py-6">
        No trades yet — the engine will publish here as soon as a setup fires.
      </div>
    );
  }
  const isWin = (trade.pnl ?? 0) > 0;
  const isLoss = (trade.pnl ?? 0) < 0;
  const isOpen = trade.outcome === "OPEN" || trade.exit_price == null;

  return (
    <div
      className={clsx(
        "card rim flex flex-col gap-3",
        isWin && "glow-green",
        isLoss && "glow-red",
        isOpen && "glow-blue",
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span
            className={clsx(
              "px-2 py-1 text-[11px] rounded-md font-semibold uppercase tracking-wider border",
              trade.side === "BUY"
                ? "bg-accent/15 text-accent border-accent/30"
                : "bg-danger/15 text-danger border-danger/30",
            )}
          >
            {trade.side === "BUY" ? <TrendingUp size={12} className="inline mr-1" /> : <TrendingDown size={12} className="inline mr-1" />}
            {trade.side}
          </span>
          <div>
            <div className="text-white font-medium leading-tight">{trade.symbol}</div>
            <div className="text-[11px] text-gray-500 uppercase tracking-wider">
              Last Trade {trade.strategy ? "· " + trade.strategy : ""}
            </div>
          </div>
        </div>
        <div className="text-right">
          {isOpen ? (
            <span className="text-info text-xs uppercase tracking-wider inline-flex items-center gap-1.5">
              <Circle size={8} className="fill-info text-info animate-pulse" /> Open
            </span>
          ) : (
            <>
              <div className={clsx("font-semibold num text-lg", isWin ? "text-accent" : "text-danger")}>
                {isWin ? "+" : ""}${trade.pnl?.toFixed(2)}
              </div>
              <div className={clsx("text-[10px] uppercase tracking-wider", isWin ? "text-accent" : "text-danger")}>
                {trade.outcome}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[12px]">
        <div className="rounded-md bg-white/[0.02] border border-white/5 px-3 py-2">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">Entry</div>
          <div className="num text-white">${trade.entry_price?.toFixed(2)}</div>
        </div>
        <div className="rounded-md bg-white/[0.02] border border-white/5 px-3 py-2">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">{isOpen ? "Live Exit" : "Exit"}</div>
          <div className="num text-white">{trade.exit_price != null ? `$${trade.exit_price.toFixed(2)}` : "—"}</div>
        </div>
        <div className="rounded-md bg-white/[0.02] border border-white/5 px-3 py-2">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">Stop Loss</div>
          <div className="num text-danger/90">{trade.sl != null ? `$${trade.sl.toFixed(2)}` : "—"}</div>
        </div>
        <div className="rounded-md bg-white/[0.02] border border-white/5 px-3 py-2">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">Take Profit</div>
          <div className="num text-accent/90">{trade.tp != null ? `$${trade.tp.toFixed(2)}` : "—"}</div>
        </div>
      </div>
    </div>
  );
}

