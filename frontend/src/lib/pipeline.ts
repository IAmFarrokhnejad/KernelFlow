import type { OperationDefinition, PipelineStep, Preset, TargetSpec } from '../types';

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function createId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `step-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function createDefaultTarget(): TargetSpec {
  return {
    scope: 'global',
    bounds: { x: 0.15, y: 0.15, width: 0.5, height: 0.5 },
    featherPx: 0,
    maskGenerator: 'none',
    maskParams: { threshold: 160, low: 60, high: 180, min: 0.2, max: 1 },
    invertMask: false,
  };
}

export function createStepFromOperation(operation: OperationDefinition): PipelineStep {
  const params: Record<string, unknown> = {};
  for (const field of operation.paramsSchema) {
    params[field.key] = deepClone(field.default);
  }

  return {
    id: createId(),
    operationId: operation.id,
    enabled: true,
    previewEnabled: true,
    params,
    target: createDefaultTarget(),
  };
}

export function clonePipeline(pipeline: PipelineStep[]): PipelineStep[] {
  return pipeline.map((step) => ({
    ...deepClone(step),
    id: createId(),
  }));
}

export function pipelineFromPreset(preset: Preset): PipelineStep[] {
  return clonePipeline(preset.pipeline);
}

export function moveStep(pipeline: PipelineStep[], stepId: string, direction: -1 | 1): PipelineStep[] {
  const index = pipeline.findIndex((step) => step.id === stepId);
  if (index === -1) {
    return pipeline;
  }
  const nextIndex = index + direction;
  if (nextIndex < 0 || nextIndex >= pipeline.length) {
    return pipeline;
  }

  const next = pipeline.slice();
  const [step] = next.splice(index, 1);
  next.splice(nextIndex, 0, step);
  return next;
}

export function duplicateStep(pipeline: PipelineStep[], stepId: string): PipelineStep[] {
  const index = pipeline.findIndex((step) => step.id === stepId);
  if (index === -1) {
    return pipeline;
  }

  const next = pipeline.slice();
  next.splice(index + 1, 0, {
    ...deepClone(next[index]),
    id: createId(),
  });
  return next;
}

export function removeStep(pipeline: PipelineStep[], stepId: string): PipelineStep[] {
  return pipeline.filter((step) => step.id !== stepId);
}

export function updateStep(
  pipeline: PipelineStep[],
  stepId: string,
  updater: (step: PipelineStep) => PipelineStep,
): PipelineStep[] {
  return pipeline.map((step) => (step.id === stepId ? updater(step) : step));
}

export function summarizePipeline(
  pipeline: PipelineStep[],
  operations: OperationDefinition[],
): string {
  const labels = pipeline
    .filter((step) => step.enabled)
    .map((step) => operations.find((operation) => operation.id === step.operationId)?.label ?? step.operationId);

  if (labels.length === 0) {
    return 'Original image';
  }

  return labels.join(' -> ');
}
