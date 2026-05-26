import clsx from "clsx";

export function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    running: "bg-accent/15 text-accent border-accent/30",
    stopped: "bg-white/5 text-gray-300 border-white/10",
    paused: "bg-warn/15 text-warn border-warn/30",
  };
  const dot =
    status === "running" ? "bg-accent" :
    status === "paused" ? "bg-warn" : "bg-gray-500";
  return (
    <span
      className={clsx(
        "px-2.5 py-1 rounded-md text-xs font-medium border inline-flex items-center gap-2 uppercase tracking-wider",
        map[status] || map.stopped,
      )}
    >
      <span className={clsx("w-1.5 h-1.5 rounded-full", dot, status === "running" && "animate-pulse")} />
      {status}
    </span>
  );
}

