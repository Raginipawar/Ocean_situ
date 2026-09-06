import type { TrustLabel } from "../lib/types";

const LABEL_TEXT: Record<TrustLabel, string> = {
  green: "Model matches sensors",
  amber: "Partial disagreement",
  red: "Model diverges from sensors",
};

const LABEL_COLOR: Record<TrustLabel, string> = {
  green: "var(--color-trust-green)",
  amber: "var(--color-trust-amber)",
  red: "var(--color-trust-red)",
};

export function TrustBadge({ label, confidence }: { label: TrustLabel; confidence?: number }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-nav"
      style={{ backgroundColor: `color-mix(in oklab, ${LABEL_COLOR[label]} 16%, transparent)`, color: LABEL_COLOR[label] }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: LABEL_COLOR[label] }} />
      {LABEL_TEXT[label]}
      {typeof confidence === "number" && (
        <span className="font-mono-data opacity-80">{Math.round(confidence * 100)}%</span>
      )}
    </span>
  );
}
