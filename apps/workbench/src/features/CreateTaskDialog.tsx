import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSnapshot } from '../app/workspace-context';
import { Dialog } from '../components/Dialog';
import { MaterialVisual } from '../components/MaterialCard';
import { Button, Notice } from '../components/ui';
import {
  formatBytes,
  formatDuration,
  normalizeSteps,
  stepLabels,
  validateProcessing,
} from '../domain/workspace';
import type { ProcessingStep } from '../domain/types';
import { ImportFiles } from './ImportFiles';

const descriptions: Record<ProcessingStep, string> = {
  clean: '使用现有视频清洗流程',
  scenes: '按原始镜头拆分，保留长镜头',
  transcribe: '提取语音与时间戳',
  semantic: '根据镜头与转录进行语义分组',
};

export function CreateTaskDialog({
  initialIds,
  onClose,
}: {
  initialIds: string[];
  onClose: () => void;
}) {
  const { snapshot, execute, busy, mode } = useSnapshot();
  const live = mode === 'live';
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [selected, setSelected] = useState(
    () =>
      new Set(
        initialIds.filter((id) =>
          snapshot.materials.some((material) => material.id === id && material.kind !== 'image'),
        ),
      ),
  );
  const [name, setName] = useState('');
  const [steps, setSteps] = useState<ProcessingStep[]>(['scenes', 'transcribe']);
  const [threshold, setThreshold] = useState('27');
  const [error, setError] = useState('');
  const materials = snapshot.materials.filter((material) => selected.has(material.id));
  const defaultName =
    materials.length === 1 ? materials[0]!.name : `批量处理 · ${materials.length} 份素材`;
  const request = {
    materialIds: [...selected],
    name: live ? name.trim() || defaultName : name,
    steps,
    threshold: threshold.trim() ? Number(threshold) : NaN,
  };
  function next() {
    setError('');
    if (step === 2) {
      try {
        validateProcessing(request, snapshot.materials);
      } catch (cause) {
        setError((cause as Error).message);
        return;
      }
    }
    setStep((value) => value + 1);
  }
  function toggleStep(option: ProcessingStep, checked: boolean) {
    let nextSteps = checked ? [...steps, option] : steps.filter((item) => item !== option);
    if (!checked && (option === 'scenes' || option === 'transcribe'))
      nextSteps = nextSteps.filter((item) => item !== 'semantic');
    setSteps(normalizeSteps(nextSteps));
    setError('');
  }
  async function submit() {
    const updated = await execute(
      (repository) => repository.createTasks(request),
      `已创建 ${selected.size} 个${live ? '处理' : '演示'}任务`,
    );
    if (updated) navigate(`/tasks?task=${updated.tasks[0]!.id}`);
  }
  return (
    <Dialog
      title="新建处理任务"
      subtitle="选择素材，安排好下一步。"
      onClose={onClose}
      busy={busy}
      footer={
        <>
          <span>
            步骤 {step} / 3 · {live ? '本地处理' : '示例工作流'}
          </span>
          <div>
            <Button
              disabled={busy}
              onClick={
                step === 1
                  ? onClose
                  : () => {
                      setStep((value) => value - 1);
                      setError('');
                    }
              }
            >
              {step === 1 ? '取消' : '上一步'}
            </Button>
            <Button
              variant="primary"
              icon={step === 3 ? 'plus' : 'arrow'}
              disabled={busy || (step === 1 && !selected.size) || (step === 2 && !steps.length)}
              onClick={step === 3 ? () => void submit() : next}
            >
              {busy
                ? '正在创建…'
                : step === 3
                  ? live
                    ? '创建处理任务'
                    : '创建演示任务'
                  : '下一步'}
            </Button>
          </div>
        </>
      }
    >
      <ol className="steps" aria-label="创建任务步骤">
        {['选择素材', '处理选项', '确认创建'].map((label, index) => (
          <li
            className={`wizard-step ${step === index + 1 ? 'active' : step > index + 1 ? 'done' : ''}`}
            key={label}
            aria-current={step === index + 1 ? 'step' : undefined}
          >
            <span>{step > index + 1 ? '✓' : index + 1}</span>
            {label}
          </li>
        ))}
      </ol>
      {step === 1 && (
        <>
          <ImportFiles
            onImported={(ids) => setSelected((previous) => new Set([...previous, ...ids]))}
          />
          <div className="section-head">
            <h3>或选择已有素材</h3>
            <span className="field-help">已选 {selected.size} 份</span>
          </div>
          <div className="wizard-materials">
            {snapshot.materials
              .filter((material) => material.kind !== 'image')
              .map((material) => (
                <label className="wizard-material" key={material.id}>
                  <input
                    type="checkbox"
                    checked={selected.has(material.id)}
                    onChange={(event) => {
                      const checked = event.target.checked;
                      setSelected((previous) => {
                        const nextSelected = new Set(previous);
                        if (checked) nextSelected.add(material.id);
                        else nextSelected.delete(material.id);
                        return nextSelected;
                      });
                    }}
                  />
                  <MaterialVisual material={material} />
                  <span>
                    {material.name}
                    <small>
                      {formatDuration(material.durationSeconds)} · {formatBytes(material.sizeBytes)}
                    </small>
                  </span>
                </label>
              ))}
          </div>
        </>
      )}
      {step === 2 && (
        <>
          <div className="form-field">
            <label htmlFor="task-name">任务名称</label>
            <input
              id="task-name"
              value={name}
              maxLength={80}
              placeholder={defaultName}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <fieldset className="form-field">
            <legend>处理步骤</legend>
            <div className="option-grid">
              {(Object.keys(stepLabels) as ProcessingStep[]).map((option) => (
                <label className="option-tile" key={option}>
                  <input
                    type="checkbox"
                    checked={steps.includes(option)}
                    onChange={(event) => toggleStep(option, event.target.checked)}
                  />
                  <span>
                    {stepLabels[option]}
                    <small>{descriptions[option]}</small>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="form-field">
            <label htmlFor="task-threshold">切镜阈值（越低越敏感）</label>
            <input
              id="task-threshold"
              type="number"
              min="1"
              max="100"
              value={threshold}
              onChange={(event) => setThreshold(event.target.value)}
              aria-describedby="threshold-help"
            />
          </div>
          <Notice>语义分镜会同时选中原始切镜和音频转录，保证前置结果完整。</Notice>
          {live && (
            <Notice>
              转录需要 FFmpeg 与 Whisper；语义分镜使用 config/semantic_scenes.json，以及 ZAI_API_KEY
              或 ARK_API_KEY + ARK_MODEL。请在设置中查看服务端的实际依赖检测。
            </Notice>
          )}
        </>
      )}
      {step === 3 && (
        <>
          <dl className="summary-list">
            <dt>任务名称</dt>
            <dd>{name.trim() || defaultName}</dd>
            <dt>选择素材</dt>
            <dd>
              {materials.map((material) => (
                <div key={material.id}>{material.name}</div>
              ))}
            </dd>
            <dt>处理流程</dt>
            <dd>
              {normalizeSteps(steps)
                .map((option) => stepLabels[option])
                .join(' → ')}
            </dd>
            <dt>切镜阈值</dt>
            <dd>{threshold}</dd>
            <dt>输出目录</dt>
            <dd>{snapshot.settings.outputDirectory}/&lt;视频名_时间&gt;/</dd>
          </dl>
          <Notice>
            {live
              ? '确认后进入本地处理队列，由服务自动执行。'
              : '创建后进入演示队列，不运行实际视频处理。'}
          </Notice>
        </>
      )}
      {error && (
        <p className="form-error" role="alert" id="threshold-help">
          {error}
        </p>
      )}
    </Dialog>
  );
}
