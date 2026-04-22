import HistogramChart from './HistogramChart';
import type { HistogramPayload, PipelineStep } from '../types';

type Props = {
  activeStep: PipelineStep | null;
  metrics: Record<string, number> | null;
  histogram: HistogramPayload | null;
};

export default function LabPanel({ activeStep, metrics, histogram }: Props) {
  return (
    <section className="workspace-section">
      <div className="workspace-header">
        <div>
          <p className="panel-kicker">Lab mode</p>
          <h2 className="workspace-title">Raster scan and analysis</h2>
        </div>
      </div>

      <div className="lab-grid">
        <div className="workspace-card">
          <p className="workspace-copy">Scan behavior</p>
          <h3 className="workspace-summary">The last enabled step streams top-to-bottom in lab mode.</h3>
          <p className="workspace-copy">
            Use custom kernels, edge masks, and crop targets here when you want inspection instead of quick editing.
          </p>
          {activeStep ? (
            <div className="lab-step">
              <span>Active step</span>
              <strong>{activeStep.operationId}</strong>
            </div>
          ) : null}
        </div>

        <div className="workspace-card">
          <p className="workspace-copy">Metrics</p>
          <div className="metric-grid">
            <div>
              <span>MSE</span>
              <strong>{metrics ? metrics.mse.toFixed(2) : '--'}</strong>
            </div>
            <div>
              <span>PSNR</span>
              <strong>{metrics ? metrics.psnr.toFixed(2) : '--'}</strong>
            </div>
            <div>
              <span>SSIM</span>
              <strong>{metrics ? metrics.ssim.toFixed(4) : '--'}</strong>
            </div>
          </div>
        </div>
      </div>

      <HistogramChart histogram={histogram} />
    </section>
  );
}
