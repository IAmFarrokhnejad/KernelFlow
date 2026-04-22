import type { HistogramPayload } from '../types';

type Props = {
  histogram: HistogramPayload | null;
};

export default function HistogramChart({ histogram }: Props) {
  if (!histogram) {
    return (
      <div className="rounded-3xl border border-white/10 bg-white/5 p-4 text-sm text-white/45">
        Run a preview to inspect the tonal distribution.
      </div>
    );
  }

  const points = Array.from({ length: histogram.bins }, (_, index) => ({
    original: histogram.original[index] ?? 0,
    processed: histogram.processed[index] ?? 0,
  }));
  const max = Math.max(...points.flatMap((point) => [point.original, point.processed]), 0.0001);

  return (
    <div className="rounded-3xl border border-white/10 bg-black/20 p-4">
      <div className="mb-3 flex items-center justify-between text-xs uppercase tracking-[0.28em] text-white/45">
        <span>Histogram</span>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-sky-300" />
            Original
          </span>
          <span className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-orange-300" />
            Processed
          </span>
        </div>
      </div>

      <div className="grid h-32 grid-cols-[repeat(48,minmax(0,1fr))] items-end gap-[2px]">
        {points.map((point, index) => (
          <div key={index} className="relative h-full rounded-full bg-white/[0.04]">
            <div
              className="absolute inset-x-0 bottom-0 rounded-full bg-sky-300/80"
              style={{ height: `${(point.original / max) * 100}%` }}
            />
            <div
              className="absolute inset-x-0 bottom-0 rounded-full bg-orange-300/70"
              style={{ height: `${(point.processed / max) * 100}%`, clipPath: 'inset(40% 0 0 0)' }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
