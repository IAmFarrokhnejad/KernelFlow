import type { Asset, Job, Preset } from '../types';

type Props = {
  assets: Asset[];
  activeAssetId: number | null;
  presets: Preset[];
  jobs: Job[];
  presetName: string;
  exportFormat: string;
  onFilesSelected: (files: File[]) => void;
  onSelectAsset: (id: number) => void;
  onApplyPreset: (preset: Preset) => void;
  onPresetNameChange: (value: string) => void;
  onSavePreset: () => void;
  onExportFormatChange: (value: string) => void;
  onExport: () => void;
};

export default function AssetRail({
  assets,
  activeAssetId,
  presets,
  jobs,
  presetName,
  exportFormat,
  onFilesSelected,
  onSelectAsset,
  onApplyPreset,
  onPresetNameChange,
  onSavePreset,
  onExportFormatChange,
  onExport,
}: Props) {
  const recentJobs = jobs.slice(0, 6);

  return (
    <aside className="panel-shell">
      <div className="panel-header">
        <div>
          <p className="panel-kicker">Library</p>
          <h2 className="panel-title">Assets and presets</h2>
        </div>
      </div>

      <label className="upload-well">
        <input
          className="hidden"
          type="file"
          accept="image/png,image/jpeg,image/webp,image/bmp,image/tiff,image/gif"
          multiple
          onChange={(event) => {
            const fileList = Array.from(event.target.files ?? []);
            if (fileList.length > 0) {
              onFilesSelected(fileList);
            }
            event.currentTarget.value = '';
          }}
        />
        <span className="upload-kicker">Import</span>
        <strong>Drop or browse images</strong>
        <span>PNG, JPG, WEBP, BMP, TIFF, GIF</span>
      </label>

      <div className="panel-section">
        <div className="panel-section-head">
          <div>
            <p className="panel-kicker">Assets</p>
            <h3 className="panel-section-title">Library</h3>
          </div>
          <span className="panel-badge">{assets.length}</span>
        </div>

        <div className="asset-list">
          {assets.map((asset) => (
            <button
              key={asset.id}
              type="button"
              className={`asset-row ${asset.id === activeAssetId ? 'asset-row-selected' : ''}`}
              onClick={() => onSelectAsset(asset.id)}
            >
              {asset.thumbnailUrl ? <img src={asset.thumbnailUrl} alt={asset.filename} /> : <div className="asset-thumb-fallback" />}
              <div>
                <strong>{asset.filename}</strong>
                <span>
                  {asset.width}x{asset.height}
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="panel-section">
        <div className="panel-section-head">
          <div>
            <p className="panel-kicker">Presets</p>
            <h3 className="panel-section-title">Starting points</h3>
          </div>
        </div>

        <div className="preset-list">
          {presets.map((preset) => (
            <button key={preset.id} type="button" className="preset-row" onClick={() => onApplyPreset(preset)}>
              <strong>{preset.name}</strong>
              <span>{preset.description}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="panel-section">
        <div className="panel-section-head">
          <div>
            <p className="panel-kicker">Persist</p>
            <h3 className="panel-section-title">Save and export</h3>
          </div>
        </div>

        <div className="inspector-grid">
          <label className="inspector-control">
            <span>Preset name</span>
            <input className="studio-input" value={presetName} onChange={(event) => onPresetNameChange(event.target.value)} />
          </label>
          <button type="button" className="studio-button" onClick={onSavePreset}>
            Save preset
          </button>

          <label className="inspector-control">
            <span>Export format</span>
            <select className="studio-select" value={exportFormat} onChange={(event) => onExportFormatChange(event.target.value)}>
              <option value="png">PNG</option>
              <option value="jpg">JPG</option>
              <option value="webp">WEBP</option>
            </select>
          </label>

          <button type="button" className="studio-button studio-button-strong" onClick={onExport}>
            Export current asset
          </button>
        </div>
      </div>

      <div className="panel-section">
        <div className="panel-section-head">
          <div>
            <p className="panel-kicker">History</p>
            <h3 className="panel-section-title">Recent runs</h3>
          </div>
        </div>

        <div className="history-list">
          {recentJobs.map((job) => (
            <div key={job.id} className="history-row">
              <div>
                <strong>{job.kind}</strong>
                <span>{job.status}</span>
              </div>
              {job.outputUrl ? (
                <a href={job.outputUrl} target="_blank" rel="noreferrer">
                  Open
                </a>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
