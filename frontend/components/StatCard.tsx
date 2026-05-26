import { LucideIcon } from "lucide-react";
import clsx from "clsx";

export function StatCard({
  icon: Icon, label, value, sub, tone = "default",
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  sub?: string;
  tone?: "default" | "good" | "bad" | "gold" | "info";
}) {
  const valTone =
    tone === "good" ? "text-accent" :
    tone === "bad" ? "text-danger" :
    tone === "gold" ? "text-[#fbbf24]" :
    tone === "info" ? "text-info" :
    "text-white";
  const ringTone =
    tone === "good" ? "bg-accent/10 text-accent" :
    tone === "bad" ? "bg-danger/10 text-danger" :
    tone === "gold" ? "bg-[#fbbf24]/10 text-[#fbbf24]" :
    tone === "info" ? "bg-info/10 text-info" :
    "bg-white/5 text-gray-300";
  return (
    <div className="card card-hover rim flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-wider text-gray-500">{label}</span>
        <span className={clsx("w-7 h-7 rounded-lg grid place-items-center", ringTone)}>
          <Icon size={14} />
        </span>
      </div>
      <div className={clsx("num num-xl", valTone)}>{value}</div>
      {sub && <div className="text-xs text-gray-500">{sub}</div>}
    </div>
  );
}

