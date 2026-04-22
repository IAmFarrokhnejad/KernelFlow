import { startTransition, useDeferredValue, useEffect, useEffectEvent, useRef, useState } from 'react';
import AssetRail from './components/AssetRail';
import BatchPanel from './components/BatchPanel';
import HistogramChart from './components/HistogramChart';
import LabPanel from './components/LabPanel';
import PipelineEditor from './components/PipelineEditor';
import StudioViewer from './components/StudioViewer';
import {
  cancelJob,
  createPreviewJob,
  exportAsset,
  fetchAssets,
  fetchHistory,
  fetchOperations,
  fetchPresets,
  runBatch,
  savePreset,
  streamJob,
  uploadAssets,
} from './lib/api';
import {
  createStepFromOperation,
  duplicateStep,
  moveStep,
  pipelineFromPreset,
  removeStep,
  summarizePipeline,
  updateStep,
} from './lib/pipeline';
import './App.css';
import type {
  Asset,
  BatchItem,
  BatchRun,
  HistogramPayload,
  HistoryPayload,
  JobCompleteEvent,
  JobProgressEvent,
  OperationDefinition,
  PipelineStep,
  Preset,
} from './types';

type ViewMode = 'editor' | 'batch' | 'lab';

function mergeImportedAssets(previous: Asset[], incoming: Asset[]): Asset[] {
  const existing = new Set(previous.map((asset) => asset.id));
  return [...incoming.filter((asset) => !existing.has(asset.id)), ...previous];
}

export default function App() {
  const [view, setView] = useState<ViewMode>('editor');
  const [assets, setAssets] = useState<Asset[]>([]);
  const [operations, setOperations] = useState<OperationDefinition[]>([]);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [history, setHistory] = useState<HistoryPayload | null>(null);
  const [activeAssetId, setActiveAssetId] = useState<number | null>(null);
  const [pipeline, setPipeline] = useState<PipelineStep[]>([]);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewStatus, setPreviewStatus] = useState<'idle' | 'loading' | 'streaming' | 'ready' | 'error'>('idle');
  const [previewLabel, setPreviewLabel] = useState<string>('Ready');
  const [previewMetrics, setPreviewMetrics] = useState<Record<string, number> | null>(null);
  const [previewHistogram, setPreviewHistogram] = useState<HistogramPayload | null>(null);
  const [split, setSplit] = useState(0.5);
  const [zoom, setZoom] = useState(1);
  const [presetName, setPresetName] = useState('My Pipeline');
  const [exportFormat, setExportFormat] = useState('png');
  const [batchSelection, setBatchSelection] = useState<number[]>([]);
  const [batchResult, setBatchResult] = useState<{ batch: BatchRun; items: BatchItem[] } | null>(null);
  const [notice, setNotice] = useState('Local-first processing. Nothing leaves this machine.');

  const deferredPipeline = useDeferredValue(pipeline);
  const activeJobIdRef = useRef<number | null>(null);
  const previewTokenRef = useRef(0);

  const activeAsset = assets.find((asset) => asset.id === activeAssetId) ?? null;
  const selectedStep = pipeline.find((step) => step.id === selectedStepId) ?? pipeline[0] ?? null;
  const pipelineSummary = summarizePipeline(pipeline, operations);

  useEffect(() => {
    let cancelled = false;

    async function loadStudio() {
      try {
        const [assetItems, operationItems, presetItems, historyPayload] = await Promise.all([
          fetchAssets(),
          fetchOperations(),
          fetchPresets(),
          fetchHistory(),
        ]);
        if (cancelled) {
          return;
        }
        setAssets(assetItems);
        setOperations(operationItems);
        setPresets(presetItems);
        setHistory(historyPayload);
        if (assetItems[0]) {
          setActiveAssetId((current) => current ?? assetItems[0].id);
        }
      } catch (error) {
        if (!cancelled) {
          setNotice(error instanceof Error ? error.message : 'Failed to load the studio.');
        }
      }
    }

    void loadStudio();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!activeAssetId && assets[0]) {
      setActiveAssetId(assets[0].id);
    }
  }, [activeAssetId, assets]);

  const refreshHistory = async () => {
    const payload = await fetchHistory();
    setHistory(payload);
    setPresets(payload.presets);
  };

  const handleProgressEvent = useEffectEvent((event: JobProgressEvent) => {
    setPreviewStatus('streaming');
    setPreviewLabel(event.label);
    setPreviewUrl(`data:image/jpeg;base64,${event.image}`);
  });

  const handleCompleteEvent = useEffectEvent((event: JobCompleteEvent) => {
    setPreviewStatus('ready');
    setPreviewLabel('Preview ready');
    setPreviewUrl(event.inlineImage || event.previewUrl);
    setPreviewMetrics(event.metrics);
    setPreviewHistogram(event.histogram);
    setNotice(`Preview finished: ${event.job.kind} #${event.job.id}`);
    void refreshHistory();
  });

  const handlePreviewError = useEffectEvent((message: string) => {
    setPreviewStatus('error');
    setNotice(message);
  });

  useEffect(() => {
    if (!activeAsset || view === 'batch') {
      return;
    }

    const mode = view === 'lab' ? 'lab' : 'editor';
    const requestToken = ++previewTokenRef.current;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(async () => {
      try {
        setPreviewStatus('loading');
        setPreviewLabel('Preparing preview');

        if (activeJobIdRef.current) {
          void cancelJob(activeJobIdRef.current);
        }

        const job = await createPreviewJob({
          asset_id: activeAsset.id,
          pipeline: deferredPipeline,
          mode,
        });

        activeJobIdRef.current = job.id;

        await streamJob(job.id, {
          signal: controller.signal,
          onProgress: (event) => {
            if (previewTokenRef.current === requestToken) {
              handleProgressEvent(event);
            }
          },
          onComplete: (event) => {
            if (previewTokenRef.current === requestToken) {
              handleCompleteEvent(event);
            }
          },
          onError: (message) => {
            if (previewTokenRef.current === requestToken) {
              handlePreviewError(message);
            }
          },
        });
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        handlePreviewError(error instanceof Error ? error.message : 'Preview failed.');
      }
    }, 260);

    return () => {
      window.clearTimeout(timeoutId);
      controller.abort();
    };
  }, [activeAsset, deferredPipeline, handleCompleteEvent, handlePreviewError, handleProgressEvent, view]);

  const handleFilesSelected = async (files: File[]) => {
    try {
      const imported = await uploadAssets(files);
      setAssets((current) => mergeImportedAssets(current, imported));
      if (imported[0]) {
        setActiveAssetId(imported[0].id);
      }
      setBatchSelection((current) => [...new Set([...imported.map((asset) => asset.id), ...current])]);
      setNotice(`Imported ${imported.length} image${imported.length === 1 ? '' : 's'}.`);
      await refreshHistory();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Import failed.');
    }
  };

  const handleApplyPreset = (preset: Preset) => {
    const nextPipeline = pipelineFromPreset(preset);
    startTransition(() => {
      setPipeline(nextPipeline);
      setSelectedStepId(nextPipeline[0]?.id ?? null);
      setView(preset.mode === 'lab' ? 'lab' : 'editor');
      setPresetName(`${preset.name} Copy`);
      setNotice(`Applied preset: ${preset.name}`);
    });
  };

  const handleAddOperation = (operationId: string) => {
    const operation = operations.find((item) => item.id === operationId);
    if (!operation) {
      return;
    }
    const step = createStepFromOperation(operation);
    startTransition(() => {
      setPipeline((current) => [...current, step]);
      setSelectedStepId(step.id);
      setView('editor');
    });
  };

  const handleRemoveStep = (stepId: string) => {
    setPipeline((current) => {
      const next = removeStep(current, stepId);
      setSelectedStepId(next[0]?.id ?? null);
      return next;
    });
  };

  const handleDuplicateStep = (stepId: string) => {
    setPipeline((current) => duplicateStep(current, stepId));
  };

  const handleMoveStep = (stepId: string, direction: -1 | 1) => {
    setPipeline((current) => moveStep(current, stepId, direction));
  };

  const handleToggleEnabled = (stepId: string) => {
    setPipeline((current) =>
      updateStep(current, stepId, (step) => ({
        ...step,
        enabled: !step.enabled,
      })),
    );
  };

  const handleTogglePreview = (stepId: string) => {
    setPipeline((current) =>
      updateStep(current, stepId, (step) => ({
        ...step,
        previewEnabled: !step.previewEnabled,
      })),
    );
  };

  const handleParamChange = (stepId: string, key: string, value: unknown) => {
    setPipeline((current) =>
      updateStep(current, stepId, (step) => ({
        ...step,
        params: {
          ...step.params,
          [key]: value,
        },
      })),
    );
  };

  const handleTargetChange = (stepId: string, patch: Partial<PipelineStep['target']>) => {
    setPipeline((current) =>
      updateStep(current, stepId, (step) => ({
        ...step,
        target: {
          ...step.target,
          ...patch,
        },
      })),
    );
  };

  const handleBoundsChange = (
    stepId: string,
    key: keyof PipelineStep['target']['bounds'],
    value: number,
  ) => {
    setPipeline((current) =>
      updateStep(current, stepId, (step) => ({
        ...step,
        target: {
          ...step.target,
          bounds: {
            ...step.target.bounds,
            [key]: value,
          },
        },
      })),
    );
  };

  const handleMaskParamChange = (stepId: string, key: string, value: number) => {
    setPipeline((current) =>
      updateStep(current, stepId, (step) => ({
        ...step,
        target: {
          ...step.target,
          maskParams: {
            ...step.target.maskParams,
            [key]: value,
          },
        },
      })),
    );
  };

  const handleSavePreset = async () => {
    if (pipeline.length === 0) {
      setNotice('Add at least one step before saving a preset.');
      return;
    }

    try {
      const preset = await savePreset({
        name: presetName.trim() || 'My Pipeline',
        description: `Saved from ${view} mode`,
        mode: view,
        pipeline,
      });
      setPresets((current) => {
        const without = current.filter((item) => item.id !== preset.id);
        return [...without, preset].sort((left, right) => left.name.localeCompare(right.name));
      });
      setNotice(`Saved preset: ${preset.name}`);
      await refreshHistory();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Failed to save preset.');
    }
  };

  const handleExport = async () => {
    if (!activeAsset) {
      setNotice('Select an asset before exporting.');
      return;
    }

    try {
      setNotice('Running full-resolution export...');
      const result = await exportAsset({
        asset_id: activeAsset.id,
        pipeline,
        format: exportFormat,
        name: presetName.trim() || activeAsset.filename,
      });

      if (result.job.outputUrl) {
        setPreviewUrl(result.job.outputUrl);
      }
      setPreviewMetrics(result.job.metrics);
      setPreviewHistogram(result.job.histogram);
      setNotice(`Export complete: ${result.asset.filename}`);
      await refreshHistory();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Export failed.');
    }
  };

  const handleToggleBatchAsset = (assetId: number) => {
    setBatchSelection((current) =>
      current.includes(assetId) ? current.filter((id) => id !== assetId) : [...current, assetId],
    );
  };

  const handleRunBatch = async () => {
    if (batchSelection.length === 0) {
      setNotice('Select one or more assets for the batch queue.');
      return;
    }

    try {
      setNotice('Running batch export...');
      const result = await runBatch({
        asset_ids: batchSelection,
        pipeline,
        format: exportFormat,
        name: presetName.trim() || 'Batch Pipeline',
      });
      setBatchResult(result);
      setView('batch');
      setNotice(`Batch complete: ${result.batch.name}`);
      await refreshHistory();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Batch run failed.');
    }
  };

  return (
    <div className="studio-app">
      <header className="studio-header">
        <div>
          <p className="studio-wordmark">KernelFlow vNext</p>
          <h1 className="studio-headline">Local-first image processing studio</h1>
        </div>

        <nav className="studio-nav">
          {(['editor', 'batch', 'lab'] as ViewMode[]).map((mode) => (
            <button
              key={mode}
              type="button"
              className={`studio-nav-button ${view === mode ? 'studio-nav-button-active' : ''}`}
              onClick={() => setView(mode)}
            >
              {mode}
            </button>
          ))}
        </nav>

        <div className="studio-status">
          <span className={`status-pill status-pill-${previewStatus}`}>{previewStatus}</span>
          <span>{previewLabel}</span>
        </div>
      </header>

      <div className="studio-notice">{notice}</div>

      <div className="studio-grid">
        <AssetRail
          assets={assets}
          activeAssetId={activeAssetId}
          presets={presets}
          jobs={history?.jobs ?? []}
          presetName={presetName}
          exportFormat={exportFormat}
          onFilesSelected={handleFilesSelected}
          onSelectAsset={(assetId) => {
            startTransition(() => {
              setActiveAssetId(assetId);
              setView((current) => (current === 'batch' ? 'editor' : current));
            });
          }}
          onApplyPreset={handleApplyPreset}
          onPresetNameChange={setPresetName}
          onSavePreset={handleSavePreset}
          onExportFormatChange={setExportFormat}
          onExport={handleExport}
        />

        <main className="studio-main">
          {view === 'batch' ? (
            <BatchPanel
              assets={assets}
              selectedAssetIds={batchSelection}
              pipelineSummary={pipelineSummary}
              batchResult={batchResult}
              onToggleAsset={handleToggleBatchAsset}
              onRunBatch={handleRunBatch}
            />
          ) : (
            <>
              <StudioViewer
                originalUrl={activeAsset?.url ?? null}
                processedUrl={previewUrl}
                selectedTarget={selectedStep?.target ?? null}
                split={split}
                zoom={zoom}
                onSplitChange={setSplit}
                onZoomChange={setZoom}
              />

              {view === 'lab' ? (
                <LabPanel
                  activeStep={selectedStep}
                  metrics={previewMetrics}
                  histogram={previewHistogram}
                />
              ) : (
                <section className="workspace-section">
                  <div className="workspace-header">
                    <div>
                      <p className="panel-kicker">Pipeline summary</p>
                      <h2 className="workspace-title">{pipelineSummary}</h2>
                    </div>
                  </div>

                  <div className="workspace-meta-grid">
                    <div className="workspace-card">
                      <p className="workspace-copy">Active asset</p>
                      <h3 className="workspace-summary">{activeAsset?.filename ?? 'No asset selected'}</h3>
                      <p className="workspace-copy">
                        {activeAsset ? `${activeAsset.width}x${activeAsset.height}` : 'Import an image to start.'}
                      </p>
                    </div>

                    <div className="workspace-card">
                      <p className="workspace-copy">Metrics</p>
                      <div className="metric-grid">
                        <div>
                          <span>MSE</span>
                          <strong>{previewMetrics ? previewMetrics.mse.toFixed(2) : '--'}</strong>
                        </div>
                        <div>
                          <span>PSNR</span>
                          <strong>{previewMetrics ? previewMetrics.psnr.toFixed(2) : '--'}</strong>
                        </div>
                        <div>
                          <span>SSIM</span>
                          <strong>{previewMetrics ? previewMetrics.ssim.toFixed(4) : '--'}</strong>
                        </div>
                      </div>
                    </div>
                  </div>

                  <HistogramChart histogram={previewHistogram} />
                </section>
              )}
            </>
          )}
        </main>

        <PipelineEditor
          operations={operations}
          pipeline={pipeline}
          selectedStepId={selectedStep?.id ?? null}
          onSelectStep={setSelectedStepId}
          onAddOperation={handleAddOperation}
          onRemoveStep={handleRemoveStep}
          onDuplicateStep={handleDuplicateStep}
          onMoveStep={handleMoveStep}
          onToggleEnabled={handleToggleEnabled}
          onTogglePreview={handleTogglePreview}
          onParamChange={handleParamChange}
          onTargetChange={handleTargetChange}
          onBoundsChange={handleBoundsChange}
          onMaskParamChange={handleMaskParamChange}
        />
      </div>
    </div>
  );
}
