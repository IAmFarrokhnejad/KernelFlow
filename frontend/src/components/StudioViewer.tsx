import type { TargetSpec } from '../types';

type Props = {
  originalUrl: string | null;
  processedUrl: string | null;
  selectedTarget: TargetSpec | null;
  split: number;
  zoom: number;
  onSplitChange: (value: number) => void;
  onZoomChange: (value: number) => void;
};

function clampPercent(value: number): number {
  return Math.min(0.9, Math.max(0.1, value));
}

export default function StudioViewer({
  originalUrl,
  processedUrl,
  selectedTarget,
  split,
  zoom,
  onSplitChange,
  onZoomChange,
}: Props) {
  const hasImages = Boolean(originalUrl);
  const scope = selectedTarget?.scope ?? 'global';
  const bounds = selectedTarget?.bounds;

  return (
    <section className="viewer-shell">
      <div className="viewer-toolbar">
        <div>
          <p className="viewer-kicker">Workspace</p>
          <h2 className="viewer-title">Before / after compare</h2>
        </div>

        <div className="viewer-controls">
          <label className="viewer-range">
            <span>Split</span>
            <input
              type="range"
              min={10}
              max={90}
              value={Math.round(split * 100)}
              onChange={(event) => onSplitChange(clampPercent(Number(event.target.value) / 100))}
            />
          </label>
          <label className="viewer-range">
            <span>Zoom</span>
            <input
              type="range"
              min={1}
              max={4}
              step={0.1}
              value={zoom}
              onChange={(event) => onZoomChange(Number(event.target.value))}
            />
          </label>
        </div>
      </div>

      <div className="viewer-stage">
        {!hasImages ? (
          <div className="viewer-empty">
            <p className="viewer-empty-title">Import an image to start building a pipeline.</p>
            <p className="viewer-empty-copy">
              The editor will render proxy previews automatically, while exports and batch runs stay full resolution.
            </p>
          </div>
        ) : (
          <div className="viewer-media" style={{ transform: `scale(${zoom})` }}>
            <img className="viewer-image" src={originalUrl ?? undefined} alt="Original asset" />
            {processedUrl ? (
              <>
                <div className="viewer-processed" style={{ clipPath: `inset(0 ${100 - split * 100}% 0 0)` }}>
                  <img className="viewer-image" src={processedUrl} alt="Processed preview" />
                </div>
                <div className="viewer-divider" style={{ left: `${split * 100}%` }} />
              </>
            ) : null}

            {scope !== 'global' && bounds ? (
              <div
                className={`viewer-target viewer-target-${scope}`}
                style={{
                  left: `${bounds.x * 100}%`,
                  top: `${bounds.y * 100}%`,
                  width: `${bounds.width * 100}%`,
                  height: `${bounds.height * 100}%`,
                }}
              />
            ) : null}
          </div>
        )}
      </div>
    </section>
  );
}
