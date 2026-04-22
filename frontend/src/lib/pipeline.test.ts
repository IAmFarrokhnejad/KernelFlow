import { describe, expect, it } from 'vitest';
import {
  createDefaultTarget,
  createStepFromOperation,
  duplicateStep,
  moveStep,
  summarizePipeline,
  updateStep,
} from './pipeline';
import type { OperationDefinition, PipelineStep } from '../types';

const operations: OperationDefinition[] = [
  {
    id: 'gaussian',
    label: 'Gaussian Blur',
    category: 'smoothing',
    supportsMask: true,
    supportsPreview: true,
    paramsSchema: [
      { key: 'ksize', label: 'Kernel', type: 'number', default: 5 },
      { key: 'sigma', label: 'Sigma', type: 'number', default: 0.8 },
    ],
  },
  {
    id: 'unsharp',
    label: 'Unsharp Mask',
    category: 'sharpen',
    supportsMask: true,
    supportsPreview: true,
    paramsSchema: [{ key: 'amount', label: 'Amount', type: 'number', default: 1.2 }],
  },
];

function createPipeline(): PipelineStep[] {
  return operations.map((operation) => createStepFromOperation(operation));
}

describe('pipeline helpers', () => {
  it('creates steps with default params and target defaults', () => {
    const step = createStepFromOperation(operations[0]);
    expect(step.operationId).toBe('gaussian');
    expect(step.params).toEqual({ ksize: 5, sigma: 0.8 });
    expect(step.target).toEqual(createDefaultTarget());
    expect(step.enabled).toBe(true);
  });

  it('duplicates a step with a new id', () => {
    const pipeline = createPipeline();
    const duplicate = duplicateStep(pipeline, pipeline[0].id);
    expect(duplicate).toHaveLength(3);
    expect(duplicate[0].id).not.toBe(duplicate[1].id);
    expect(duplicate[1].operationId).toBe(duplicate[0].operationId);
  });

  it('moves a step within the pipeline', () => {
    const pipeline = createPipeline();
    const moved = moveStep(pipeline, pipeline[1].id, -1);
    expect(moved[0].operationId).toBe('unsharp');
    expect(moved[1].operationId).toBe('gaussian');
  });

  it('updates a step without mutating its siblings', () => {
    const pipeline = createPipeline();
    const next = updateStep(pipeline, pipeline[0].id, (step) => ({
      ...step,
      params: { ...step.params, sigma: 1.6 },
    }));
    expect(next[0].params.sigma).toBe(1.6);
    expect(next[1]).toEqual(pipeline[1]);
  });

  it('summarizes enabled steps only', () => {
    const pipeline = createPipeline();
    pipeline[1].enabled = false;
    expect(summarizePipeline(pipeline, operations)).toBe('Gaussian Blur');
  });
});
