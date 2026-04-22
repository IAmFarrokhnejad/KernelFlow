export type ScopeType = 'global' | 'rectangle' | 'ellipse' | 'crop';
export type MaskGenerator = 'none' | 'luminance' | 'edge' | 'threshold';

export interface Bounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface TargetSpec {
  scope: ScopeType;
  bounds: Bounds;
  featherPx: number;
  maskGenerator: MaskGenerator;
  maskParams: Record<string, number>;
  invertMask: boolean;
}

export interface OperationFieldOption {
  label: string;
  value: string | number | boolean;
}

export interface OperationField {
  key: string;
  label: string;
  type: 'number' | 'boolean' | 'select' | 'matrix3x3';
  min?: number;
  max?: number;
  step?: number;
  default?: unknown;
  options?: OperationFieldOption[];
}

export interface OperationDefinition {
  id: string;
  label: string;
  category: string;
  supportsMask: boolean;
  supportsPreview: boolean;
  paramsSchema: OperationField[];
}

export interface PipelineStep {
  id: string;
  operationId: string;
  enabled: boolean;
  previewEnabled: boolean;
  params: Record<string, unknown>;
  target: TargetSpec;
}

export interface Asset {
  id: number;
  filename: string;
  mimeType: string;
  width: number;
  height: number;
  url: string;
  thumbnailUrl: string | null;
  createdAt: string | null;
}

export interface Preset {
  id: number;
  name: string;
  description: string;
  mode: 'editor' | 'lab';
  pipeline: PipelineStep[];
  createdAt: string | null;
  updatedAt: string | null;
}

export interface HistogramPayload {
  original: number[];
  processed: number[];
  bins: number;
}

export interface Job {
  id: number;
  kind: string;
  mode: string;
  status: string;
  assetId: number;
  batchId: number | null;
  pipeline: PipelineStep[];
  outputUrl: string | null;
  metrics: Record<string, number> | null;
  histogram: HistogramPayload | null;
  error: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface BatchRun {
  id: number;
  name: string;
  status: string;
  assetIds: number[];
  pipeline: PipelineStep[];
  outputDir: string | null;
  format: string;
  createdAt: string | null;
  completedAt: string | null;
}

export interface BatchItem {
  asset: Asset;
  job: Job;
}

export interface HistoryPayload {
  assets: Asset[];
  jobs: Job[];
  batches: BatchRun[];
  presets: Preset[];
}

export interface JobProgressEvent {
  type: 'step' | 'scan';
  progress: number;
  label: string;
  image: string;
}

export interface JobCompleteEvent {
  job: Job;
  previewUrl: string | null;
  metrics: Record<string, number>;
  histogram: HistogramPayload;
  inlineImage: string;
}
