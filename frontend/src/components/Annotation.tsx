/**
 * Editorial-style callouts: a short grey leader line from a point of
 * interest to a small caption, the way data-journalism graphics label
 * parts of a chart. Desktop-only (a fixed-percentage leader line doesn't
 * survive small-screen reflow), purely decorative/explanatory -- it labels
 * real UI that's already there, it doesn't add any new claims.
 */
interface AnnotationItem {
  /** Anchor dot position, as a percentage of the relatively-positioned parent. */
  x: number;
  y: number;
  /** Offset (percentage points) from the anchor to the label/line end. */
  dx: number;
  dy: number;
  text: string;
}

export function AnnotationLayer({ items }: { items: AnnotationItem[] }) {
  return (
    <div className="pointer-events-none absolute inset-0 z-20 hidden lg:block" aria-hidden="true">
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
        {items.map((item, i) => (
          <g key={i} style={{ color: "var(--color-border)" }}>
            <circle cx={item.x} cy={item.y} r={0.45} fill="currentColor" />
            <line
              x1={item.x}
              y1={item.y}
              x2={item.x + item.dx}
              y2={item.y + item.dy}
              stroke="currentColor"
              strokeWidth={0.15}
            />
          </g>
        ))}
      </svg>
      {items.map((item, i) => {
        const labelX = item.x + item.dx;
        const labelY = item.y + item.dy;
        const alignLeft = item.dx >= 0;
        return (
          <p
            key={i}
            className="font-nav absolute max-w-[10.5rem] rounded text-[10px] uppercase leading-snug tracking-wide opacity-90"
            style={{
              top: `${labelY}%`,
              left: alignLeft ? `${labelX + 0.8}%` : undefined,
              right: alignLeft ? undefined : `${100 - labelX + 0.8}%`,
              transform: item.dy >= 0 ? "translateY(0.35rem)" : "translateY(-100%) translateY(-0.35rem)",
              textAlign: alignLeft ? "left" : "right",
              color: "var(--color-ink)",
              backgroundColor: "var(--color-bg)",
              padding: "2px 5px",
              boxShadow: "0 1px 3px rgba(0,0,0,0.12)",
            }}
          >
            {item.text}
          </p>
        );
      })}
    </div>
  );
}
