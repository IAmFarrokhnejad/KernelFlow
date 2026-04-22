import type { Asset, BatchItem, BatchRun } from '../types';

type Props = {
  assets: Asset[];
  selectedAssetIds: number[];
  pipelineSummary: string;
  batchResult: { batch: BatchRun; items: BatchItem[] } | null;
  onToggleAsset: (assetId: number) => void;
  onRunBatch: () => void;
};

export default function BatchPanel({
  assets,
  selectedAssetIds,
  pipelineSummary,
  batchResult,
  onToggleAsset,
  onRunBatch,
}: Props) {
  return (
    <section className="workspace-section">
      <div className="workspace-header">
        <div>
          <p className="panel-kicker">Batch queue</p>
          <h2 className="workspace-title">Run the current pipeline across multiple assets</h2>
        </div>
        <button type="button" className="studio-button studio-button-strong" onClick={onRunBatch}>
          Process selected assets
        </button>
      </div>

      <div className="workspace-card">
        <p className="workspace-copy">Locked snapshot</p>
        <h3 className="workspace-summary">{pipelineSummary}</h3>
      </div>

      <div className="batch-grid">
        {assets.map((asset) => {
          const selected = selectedAssetIds.includes(asset.id);
          return (
            <button
              key={asset.id}
              type="button"
              className={`batch-tile ${selected ? 'batch-tile-selected' : ''}`}
              onClick={() => onToggleAsset(asset.id)}
            >
              {asset.thumbnailUrl ? <img src={asset.thumbnailUrl} alt={asset.filename} /> : null}
              <div>
                <strong>{asset.filename}</strong>
                <span>
                  {asset.width}x{asset.height}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {batchResult ? (
        <div className="panel-section">
          <div className="panel-section-head">
            <div>
              <p className="panel-kicker">Latest batch</p>
              <h3 className="panel-section-title">{batchResult.batch.name}</h3>
            </div>
            <span className="panel-badge">{batchResult.batch.status}</span>
          </div>

          <div className="history-list">
            {batchResult.items.map((item) => (
              <div key={item.job.id} className="history-row">
                <div>
                  <strong>{item.asset.filename}</strong>
                  <span>{item.job.status}</span>
                </div>
                {item.job.outputUrl ? (
                  <a href={item.job.outputUrl} target="_blank" rel="noreferrer">
                    Output
                  </a>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
