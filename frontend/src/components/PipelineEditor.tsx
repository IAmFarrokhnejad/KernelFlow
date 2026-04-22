import type { OperationDefinition, PipelineStep } from '../types';

type Props = {
  operations: OperationDefinition[];
  pipeline: PipelineStep[];
  selectedStepId: string | null;
  onSelectStep: (id: string) => void;
  onAddOperation: (operationId: string) => void;
  onRemoveStep: (id: string) => void;
  onDuplicateStep: (id: string) => void;
  onMoveStep: (id: string, direction: -1 | 1) => void;
  onToggleEnabled: (id: string) => void;
  onTogglePreview: (id: string) => void;
  onParamChange: (id: string, key: string, value: unknown) => void;
  onTargetChange: (id: string, patch: Partial<PipelineStep['target']>) => void;
  onBoundsChange: (id: string, key: keyof PipelineStep['target']['bounds'], value: number) => void;
  onMaskParamChange: (id: string, key: string, value: number) => void;
};

const scopeOptions = [
  { label: 'Global', value: 'global' },
  { label: 'Rectangle', value: 'rectangle' },
  { label: 'Ellipse', value: 'ellipse' },
  { label: 'Crop', value: 'crop' },
] as const;

const maskOptions = [
  { label: 'None', value: 'none' },
  { label: 'Luminance', value: 'luminance' },
  { label: 'Edge', value: 'edge' },
  { label: 'Threshold', value: 'threshold' },
] as const;

function findOperation(operations: OperationDefinition[], id: string) {
  return operations.find((operation) => operation.id === id);
}

type NumberFieldProps = {
  label: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onChange: (value: number) => void;
};

function NumberField({ label, value, min, max, step, onChange }: NumberFieldProps) {
  return (
    <label className="inspector-control">
      <span>{label}</span>
      <div className="inspector-range">
        <input
          type="range"
          min={min}
          max={max}
          step={step ?? 1}
          value={value}
          onChange={(event) => onChange(Number(event.target.value))}
        />
        <input
          type="number"
          min={min}
          max={max}
          step={step ?? 1}
          value={value}
          onChange={(event) => onChange(Number(event.target.value))}
        />
      </div>
    </label>
  );
}

export default function PipelineEditor({
  operations,
  pipeline,
  selectedStepId,
  onSelectStep,
  onAddOperation,
  onRemoveStep,
  onDuplicateStep,
  onMoveStep,
  onToggleEnabled,
  onTogglePreview,
  onParamChange,
  onTargetChange,
  onBoundsChange,
  onMaskParamChange,
}: Props) {
  const selectedStep = pipeline.find((step) => step.id === selectedStepId) ?? pipeline[0] ?? null;
  const selectedOperation = selectedStep ? findOperation(operations, selectedStep.operationId) : undefined;

  return (
    <aside className="panel-shell">
      <div className="panel-header">
        <div>
          <p className="panel-kicker">Inspector</p>
          <h2 className="panel-title">Pipeline</h2>
        </div>
        <select className="studio-select" defaultValue="" onChange={(event) => event.target.value && onAddOperation(event.target.value)}>
          <option value="" disabled>
            Add operation
          </option>
          {operations.map((operation) => (
            <option key={operation.id} value={operation.id}>
              {operation.label}
            </option>
          ))}
        </select>
      </div>

      <div className="step-stack">
        {pipeline.length === 0 ? (
          <div className="panel-empty">Start with a preset or add an operation to create the first step.</div>
        ) : (
          pipeline.map((step, index) => {
            const operation = findOperation(operations, step.operationId);
            const selected = step.id === (selectedStep?.id ?? '');
            return (
              <button
                key={step.id}
                type="button"
                className={`step-card ${selected ? 'step-card-selected' : ''}`}
                onClick={() => onSelectStep(step.id)}
              >
                <div className="step-card-head">
                  <div>
                    <p className="step-index">Step {index + 1}</p>
                    <h3 className="step-label">{operation?.label ?? step.operationId}</h3>
                  </div>
                  <span className={`step-state ${step.enabled ? 'step-state-on' : 'step-state-off'}`}>
                    {step.enabled ? 'On' : 'Off'}
                  </span>
                </div>

                <div className="step-actions">
                  <button type="button" onClick={(event) => { event.stopPropagation(); onMoveStep(step.id, -1); }}>
                    Up
                  </button>
                  <button type="button" onClick={(event) => { event.stopPropagation(); onMoveStep(step.id, 1); }}>
                    Down
                  </button>
                  <button type="button" onClick={(event) => { event.stopPropagation(); onDuplicateStep(step.id); }}>
                    Duplicate
                  </button>
                  <button type="button" onClick={(event) => { event.stopPropagation(); onToggleEnabled(step.id); }}>
                    {step.enabled ? 'Disable' : 'Enable'}
                  </button>
                  <button type="button" onClick={(event) => { event.stopPropagation(); onTogglePreview(step.id); }}>
                    {step.previewEnabled ? 'Preview' : 'Skip preview'}
                  </button>
                  <button type="button" className="step-danger" onClick={(event) => { event.stopPropagation(); onRemoveStep(step.id); }}>
                    Remove
                  </button>
                </div>
              </button>
            );
          })
        )}
      </div>

      {selectedStep && selectedOperation ? (
        <div className="panel-section">
          <div className="panel-section-head">
            <div>
              <p className="panel-kicker">Selected step</p>
              <h3 className="panel-section-title">{selectedOperation.label}</h3>
            </div>
            <span className="panel-badge">{selectedOperation.category}</span>
          </div>

          {selectedOperation.paramsSchema.length === 0 ? (
            <p className="panel-copy">This operation uses its built-in defaults.</p>
          ) : (
            <div className="inspector-grid">
              {selectedOperation.paramsSchema.map((field) => {
                const value = selectedStep.params[field.key];
                if (field.type === 'boolean') {
                  return (
                    <label key={field.key} className="inspector-toggle">
                      <input
                        type="checkbox"
                        checked={Boolean(value)}
                        onChange={(event) => onParamChange(selectedStep.id, field.key, event.target.checked)}
                      />
                      <span>{field.label}</span>
                    </label>
                  );
                }

                if (field.type === 'select') {
                  return (
                    <label key={field.key} className="inspector-control">
                      <span>{field.label}</span>
                      <select
                        className="studio-select"
                        value={String(value ?? field.default ?? '')}
                        onChange={(event) => onParamChange(selectedStep.id, field.key, event.target.value)}
                      >
                        {field.options?.map((option) => (
                          <option key={String(option.value)} value={String(option.value)}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  );
                }

                if (field.type === 'matrix3x3') {
                  const matrix = (value as number[][] | undefined) ?? [[0, -1, 0], [-1, 5, -1], [0, -1, 0]];
                  return (
                    <div key={field.key} className="inspector-control">
                      <span>{field.label}</span>
                      <div className="kernel-grid">
                        {matrix.flat().map((cell, index) => (
                          <input
                            key={index}
                            type="number"
                            step="0.1"
                            value={cell}
                            onChange={(event) => {
                              const next = matrix.map((row) => row.slice());
                              const row = Math.floor(index / 3);
                              const column = index % 3;
                              next[row][column] = Number(event.target.value);
                              onParamChange(selectedStep.id, field.key, next);
                            }}
                          />
                        ))}
                      </div>
                    </div>
                  );
                }

                return (
                  <NumberField
                    key={field.key}
                    label={field.label}
                    value={Number(value ?? field.default ?? 0)}
                    min={field.min}
                    max={field.max}
                    step={field.step}
                    onChange={(nextValue) => onParamChange(selectedStep.id, field.key, nextValue)}
                  />
                );
              })}
            </div>
          )}

          <div className="panel-section-head">
            <div>
              <p className="panel-kicker">Targeting</p>
              <h3 className="panel-section-title">Region and mask</h3>
            </div>
          </div>

          {selectedOperation.supportsMask ? (
            <div className="inspector-grid">
              <label className="inspector-control">
                <span>Scope</span>
                <select
                  className="studio-select"
                  value={selectedStep.target.scope}
                  onChange={(event) => onTargetChange(selectedStep.id, { scope: event.target.value as PipelineStep['target']['scope'] })}
                >
                  {scopeOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="inspector-control">
                <span>Mask</span>
                <select
                  className="studio-select"
                  value={selectedStep.target.maskGenerator}
                  onChange={(event) => onTargetChange(selectedStep.id, { maskGenerator: event.target.value as PipelineStep['target']['maskGenerator'] })}
                >
                  {maskOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <NumberField
                label="X"
                value={selectedStep.target.bounds.x}
                min={0}
                max={1}
                step={0.01}
                onChange={(value) => onBoundsChange(selectedStep.id, 'x', value)}
              />
              <NumberField
                label="Y"
                value={selectedStep.target.bounds.y}
                min={0}
                max={1}
                step={0.01}
                onChange={(value) => onBoundsChange(selectedStep.id, 'y', value)}
              />
              <NumberField
                label="Width"
                value={selectedStep.target.bounds.width}
                min={0.05}
                max={1}
                step={0.01}
                onChange={(value) => onBoundsChange(selectedStep.id, 'width', value)}
              />
              <NumberField
                label="Height"
                value={selectedStep.target.bounds.height}
                min={0.05}
                max={1}
                step={0.01}
                onChange={(value) => onBoundsChange(selectedStep.id, 'height', value)}
              />
              <NumberField
                label="Feather"
                value={selectedStep.target.featherPx}
                min={0}
                max={50}
                step={1}
                onChange={(value) => onTargetChange(selectedStep.id, { featherPx: value })}
              />

              <label className="inspector-toggle">
                <input
                  type="checkbox"
                  checked={selectedStep.target.invertMask}
                  onChange={(event) => onTargetChange(selectedStep.id, { invertMask: event.target.checked })}
                />
                <span>Invert mask</span>
              </label>

              {selectedStep.target.maskGenerator === 'threshold' ? (
                <NumberField
                  label="Threshold"
                  value={selectedStep.target.maskParams.threshold ?? 160}
                  min={0}
                  max={255}
                  step={1}
                  onChange={(value) => onMaskParamChange(selectedStep.id, 'threshold', value)}
                />
              ) : null}

              {selectedStep.target.maskGenerator === 'edge' ? (
                <>
                  <NumberField
                    label="Low edge"
                    value={selectedStep.target.maskParams.low ?? 60}
                    min={0}
                    max={255}
                    step={1}
                    onChange={(value) => onMaskParamChange(selectedStep.id, 'low', value)}
                  />
                  <NumberField
                    label="High edge"
                    value={selectedStep.target.maskParams.high ?? 180}
                    min={0}
                    max={255}
                    step={1}
                    onChange={(value) => onMaskParamChange(selectedStep.id, 'high', value)}
                  />
                </>
              ) : null}

              {selectedStep.target.maskGenerator === 'luminance' ? (
                <>
                  <NumberField
                    label="Min luminance"
                    value={selectedStep.target.maskParams.min ?? 0.2}
                    min={0}
                    max={1}
                    step={0.01}
                    onChange={(value) => onMaskParamChange(selectedStep.id, 'min', value)}
                  />
                  <NumberField
                    label="Max luminance"
                    value={selectedStep.target.maskParams.max ?? 1}
                    min={0}
                    max={1}
                    step={0.01}
                    onChange={(value) => onMaskParamChange(selectedStep.id, 'max', value)}
                  />
                </>
              ) : null}
            </div>
          ) : (
            <p className="panel-copy">This operation changes the full image dimensions, so local targeting is disabled.</p>
          )}
        </div>
      ) : null}
    </aside>
  );
}
