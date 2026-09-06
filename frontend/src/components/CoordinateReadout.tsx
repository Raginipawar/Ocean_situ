interface CoordinateReadoutProps {
  label: string;
  lat: number;
  lon: number;
  className?: string;
}

function formatCoord(value: number, positiveSuffix: string, negativeSuffix: string): string {
  const suffix = value >= 0 ? positiveSuffix : negativeSuffix;
  return `${Math.abs(value).toFixed(4)}° ${suffix}`;
}

export function CoordinateReadout({ label, lat, lon, className }: CoordinateReadoutProps) {
  return (
    <div className={`font-mono-data text-xs ${className ?? ""}`}>
      <span className="opacity-60">{label} · </span>
      {formatCoord(lat, "N", "S")} {formatCoord(lon, "E", "W")}
    </div>
  );
}
