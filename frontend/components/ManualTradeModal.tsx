"use client";
import { useState } from "react";
import { X, TrendingUp, TrendingDown, Zap } from "lucide-react";
import { api } from "@/lib/api";

interface Props {
  onClose: () => void;
  onDone: () => void;
}

export function ManualTradeModal({ onClose, onDone }: Props) {
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [qty, setQty] = useState("");
  const [sl, setSl] = useState("");
  const [tp1, setTp1] = useState("");
  const [tp2, setTp2] = useState("");
  const [tp3, setTp3] = useState("");
  const [tp4, setTp4] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setResult(null);
    try {
      const tps = [tp1, tp2, tp3, tp4].map((v) => (v ? parseFloat(v) : null));
      const res = await api.manualTrade(
        side,
        parseFloat(qty) || 0,
        sl ? parseFloat(sl) : undefined,
        tps,
      );
      const n = res.slices?.length || 1;
      setResult(`✓ ${res.side} ×${n} @ $${res.entry.toFixed(2)} — total qty ${res.total_qty}`);
      setTimeout(() => { onDone(); onClose(); }, 1800);
    } catch (e: any) {
      setResult(`✗ ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-sm mx-4 rounded-2xl border border-white/10 bg-[#0d121b] shadow-2xl p-6 flex flex-col gap-5">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap size={16} className="text-accent" />
            <h2 className="text-white font-semibold text-sm tracking-wide">Manual Trade</h2>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition">
            <X size={16} />
          </button>
        </div>

        {/* Side toggle */}
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => setSide("BUY")}
            className={`py-2.5 rounded-lg text-sm font-semibold flex items-center justify-center gap-2 border transition ${
              side === "BUY"
                ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/40"
                : "bg-white/[0.03] text-gray-500 border-white/10 hover:bg-white/[0.06]"
            }`}
          >
            <TrendingUp size={14} /> BUY / LONG
          </button>
          <button
            onClick={() => setSide("SELL")}
            className={`py-2.5 rounded-lg text-sm font-semibold flex items-center justify-center gap-2 border transition ${
              side === "SELL"
                ? "bg-rose-500/15 text-rose-400 border-rose-500/40"
                : "bg-white/[0.03] text-gray-500 border-white/10 hover:bg-white/[0.06]"
            }`}
          >
            <TrendingDown size={14} /> SELL / SHORT
          </button>
        </div>

        {/* Fields */}
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-[11px] uppercase tracking-wider text-gray-500">Qty (0 = auto-size)</span>
            <input
              type="number"
              min="0"
              step="0.001"
              placeholder="0.000"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              className="bg-white/[0.03] border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-accent/50 transition"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-[11px] uppercase tracking-wider text-gray-500">Stop Loss</span>
              <input
                type="number"
                step="0.01"
                placeholder="required for SL"
                value={sl}
                onChange={(e) => setSl(e.target.value)}
                className="bg-white/[0.03] border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-accent/50 transition"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[11px] uppercase tracking-wider text-gray-500">TP 1</span>
              <input
                type="number"
                step="0.01"
                placeholder="first target"
                value={tp1}
                onChange={(e) => setTp1(e.target.value)}
                className="bg-white/[0.03] border border-white/10 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-accent/50 transition"
              />
            </label>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-[11px] uppercase tracking-wider text-gray-500">TP 2</span>
              <input
                type="number"
                step="0.01"
                placeholder="opt"
                value={tp2}
                onChange={(e) => setTp2(e.target.value)}
                className="bg-white/[0.03] border border-white/10 rounded-lg px-2.5 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-accent/50 transition"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[11px] uppercase tracking-wider text-gray-500">TP 3</span>
              <input
                type="number"
                step="0.01"
                placeholder="opt"
                value={tp3}
                onChange={(e) => setTp3(e.target.value)}
                className="bg-white/[0.03] border border-white/10 rounded-lg px-2.5 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-accent/50 transition"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[11px] uppercase tracking-wider text-gray-500">TP 4</span>
              <input
                type="number"
                step="0.01"
                placeholder="opt"
                value={tp4}
                onChange={(e) => setTp4(e.target.value)}
                className="bg-white/[0.03] border border-white/10 rounded-lg px-2.5 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-accent/50 transition"
              />
            </label>
          </div>
        </div>

        {/* Hint */}
        <p className="text-[11px] text-gray-600 leading-relaxed">
          Qty 0 = auto-size from equity & risk %. Fill multiple TPs to split position into equal slices (e.g. 4 TPs = 25% closes at each level), all sharing the same SL.
        </p>

        {/* Result */}
        {result && (
          <p className={`text-xs rounded-lg px-3 py-2 ${result.startsWith("✓") ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"}`}>
            {result}
          </p>
        )}

        {/* Submit */}
        <button
          disabled={busy}
          onClick={submit}
          className={`py-2.5 rounded-lg text-sm font-semibold flex items-center justify-center gap-2 transition disabled:opacity-50 ${
            side === "BUY"
              ? "bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 border border-emerald-500/30"
              : "bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 border border-rose-500/30"
          }`}
        >
          {busy ? "Placing…" : `Place ${side} Order`}
        </button>
      </div>
    </div>
  );
}
