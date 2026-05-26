import clsx from "clsx";

export function StrategyBadge({ name }: { name: string }) {
  const color =
    name === "aggressive" ? "bg-danger/15 text-danger border-danger/30" :
    name === "conservative" ? "bg-info/15 text-info border-info/30" :
    "bg-accent/15 text-accent border-accent/30";
  return (
    <span
      className={clsx(
        "px-2.5 py-1 rounded-md text-xs font-medium border uppercase tracking-wider",
        color,
      )}
    >
      {name}
    </span>
  );
}

