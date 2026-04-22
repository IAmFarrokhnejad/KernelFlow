import type {
  Asset,
  BatchItem,
  BatchRun,
  HistoryPayload,
  Job,
  JobCompleteEvent,
  JobProgressEvent,
  OperationDefinition,
  Preset,
} from '../types';

type PreviewStreamHandlers = {
  signal?: AbortSignal;
  onProgress?: (event: JobProgressEvent) => void;
  onComplete?: (event: JobCompleteEvent) => void;
  onError?: (message: string) => void;
};

async function apiFetch<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...init?.headers,
    },
    ...init,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function fetchAssets(): Promise<Asset[]> {
  const payload = await apiFetch<{ items: Asset[] }>('/api/assets');
  return payload.items;
}

export async function uploadAssets(files: File[]): Promise<Asset[]> {
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }
  const payload = await apiFetch<{ items: Asset[] }>('/api/assets', {
    method: 'POST',
    body: formData,
  });
  return payload.items;
}

export async function fetchOperations(): Promise<OperationDefinition[]> {
  const payload = await apiFetch<{ operations: OperationDefinition[] }>('/api/operations');
  return payload.operations;
}

export async function fetchPresets(): Promise<Preset[]> {
  const payload = await apiFetch<{ items: Preset[] }>('/api/presets');
  return payload.items;
}

export async function savePreset(payload: {
  id?: number;
  name: string;
  description: string;
  mode: string;
  pipeline: unknown[];
}): Promise<Preset> {
  return apiFetch<Preset>('/api/presets', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createPreviewJob(payload: {
  asset_id: number;
  pipeline: unknown[];
  mode: string;
}): Promise<Job> {
  return apiFetch<Job>('/api/previews', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function cancelJob(jobId: number): Promise<void> {
  try {
    await apiFetch<Job>(`/api/jobs/${jobId}/cancel`, { method: 'POST' });
  } catch {
    // Best-effort cancellation for stale preview jobs.
  }
}

function dispatchEvent(block: string, handlers: PreviewStreamHandlers) {
  const lines = block.split('\n').filter(Boolean);
  let eventName = 'message';
  let dataLine = '';
  for (const line of lines) {
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim();
    }
    if (line.startsWith('data:')) {
      dataLine += line.slice(5).trim();
    }
  }

  if (!dataLine) {
    return;
  }

  const payload = JSON.parse(dataLine) as JobProgressEvent | JobCompleteEvent | { message: string };
  if (eventName === 'progress') {
    handlers.onProgress?.(payload as JobProgressEvent);
  } else if (eventName === 'complete') {
    handlers.onComplete?.(payload as JobCompleteEvent);
  } else if (eventName === 'error') {
    handlers.onError?.((payload as { message: string }).message);
  }
}

export async function streamJob(jobId: number, handlers: PreviewStreamHandlers): Promise<void> {
  const response = await fetch(`/api/jobs/${jobId}/stream`, { signal: handlers.signal });
  if (!response.ok || !response.body) {
    throw new Error(`Failed to stream job ${jobId}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split('\n\n');
    buffer = blocks.pop() ?? '';

    for (const block of blocks) {
      dispatchEvent(block, handlers);
    }
  }

  if (buffer.trim()) {
    dispatchEvent(buffer, handlers);
  }
}

export async function exportAsset(payload: {
  asset_id: number;
  pipeline: unknown[];
  format: string;
  name?: string;
}): Promise<{ job: Job; asset: Asset }> {
  return apiFetch<{ job: Job; asset: Asset }>('/api/exports', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function runBatch(payload: {
  asset_ids: number[];
  pipeline: unknown[];
  format: string;
  name?: string;
}): Promise<{ batch: BatchRun; items: BatchItem[] }> {
  return apiFetch<{ batch: BatchRun; items: BatchItem[] }>('/api/batches', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchHistory(): Promise<HistoryPayload> {
  return apiFetch<HistoryPayload>('/api/history');
}
