interface StatTileProps {
  tag: string;
  value: string;
  detail?: string;
  delay?: number;
}

export function StatTile({ tag, value, detail, delay = 0 }: StatTileProps) {
  return (
    <div className="panel px-5 py-4 rise" style={{ animationDelay: `${delay}ms` }}>
      <div className="section-tag mb-2">{tag}</div>
      <div className="font-mono text-3xl font-semibold leading-none">{value}</div>
      {detail && <div className="mt-2 text-xs text-sub">{detail}</div>}
    </div>
  );
}
