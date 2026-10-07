import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useSnapshot } from '../app/workspace-context';
import { Icon } from '../components/Icon';
import { MaterialVisual } from '../components/MaterialCard';
import { MediaPreview } from '../components/MediaPreview';
import { Badge, Button, IconButton, Notice, PageHeader, Progress } from '../components/ui';
import type { MixConfig, MixPlan, OutputKind } from '../domain/types';
import { createMixPlan, formatDuration, matchesMixConfig } from '../domain/workspace';

export function StudioPage() {
  const { snapshot, busy, execute, notify, run, mode } = useSnapshot();
  const live = mode === 'live';
  const navigate = useNavigate();
  const [config, setConfig] = useState<MixConfig>({
    seed: '20261006',
    template: 'teaching',
    pool: 'all',
  });
  const [plan, setPlan] = useState<MixPlan | null>(() => {
    if (live) return null;
    try {
      return createMixPlan(config, snapshot.materials);
    } catch {
      return null;
    }
  });
  const [selectedClip, setSelectedClip] = useState(0);
  const [outputs, setOutputs] = useState<Exclude<OutputKind, 'final'>[]>(
    live && !snapshot.settings.draftDirectory ? ['preview'] : ['preview', 'draft'],
  );
  const stale = !plan || !matchesMixConfig(plan, config);
  const clip = plan?.clips[selectedClip];
  const material = snapshot.materials.find((item) => item.id === clip?.materialId);
  async function generate(nextConfig = config) {
    if (live) {
      const saved = await run((repository) => {
        if (!repository.createMixPlan) throw new Error('当前仓库不支持服务端选片。');
        return repository.createMixPlan(nextConfig);
      }, '服务端选片方案已保存，使用完整素材');
      if (saved) {
        setPlan(saved);
        setSelectedClip(0);
      }
      return;
    }
    try {
      setPlan(createMixPlan(nextConfig, snapshot.materials));
      setSelectedClip(0);
      notify('选片方案已固定');
    } catch (error) {
      notify((error as Error).message);
    }
  }
  async function createTask() {
    if (!plan || stale) return;
    const updated = await execute(
      (repository) => repository.createMixTask(plan, outputs),
      live ? '已创建混剪任务，使用服务端固定方案' : '已创建混剪演示任务，选片保持不变',
    );
    if (updated) navigate(`/tasks?task=${updated.tasks[0]!.id}`);
  }
  return (
    <>
      <PageHeader title="混剪工作室" subtitle="选好素材和节奏，先看选片方案，再创建混剪任务。">
        <Link className="button" to="/tasks?q=混剪">
          <Icon name="tasks" />
          查看混剪任务
        </Link>
      </PageHeader>
      <div className="studio-layout">
        <section className="panel studio-config">
          <h2 className="panel-title">
            <span className="step-marker">01</span>混剪配置
          </h2>
          <div className="form-field">
            <label htmlFor="mix-template">混剪模板</label>
            <select
              id="mix-template"
              value={config.template}
              onChange={(event) =>
                setConfig({ ...config, template: event.target.value as MixConfig['template'] })
              }
            >
              <option value="teaching">{live ? '教学展示 · 完整素材' : '教学展示 · 42 秒'}</option>
              <option value="showcase">{live ? '作品速览 · 完整素材' : '作品速览 · 26 秒'}</option>
            </select>
            <span className="field-help">
              {live
                ? '实际时长由服务端完整素材决定，不按示例秒数截断。'
                : config.template === 'teaching'
                  ? '开场 → 示范 → 细节 → 过程 → 作品'
                  : '开场 → 作品 → 细节 → 收尾'}
            </span>
          </div>
          <div className="form-field">
            <label htmlFor="mix-pool">素材池</label>
            <select
              id="mix-pool"
              value={config.pool}
              onChange={(event) =>
                setConfig({
                  ...config,
                  pool: event.target.value as MixConfig['pool'],
                  materialIds: undefined,
                })
              }
            >
              <option value="all">{live ? '全部视频素材' : '美甲教学 · 全部示例素材'}</option>
              <option value="shots">已切分镜头</option>
            </select>
          </div>
          {live && (
            <fieldset className="form-field">
              <legend>指定素材顺序（可选）</legend>
              <p className="field-help">不选择则由种子选片；选择后按点击顺序组装全部素材。</p>
              <div className="ordered-materials">
                {snapshot.materials
                  .filter(
                    (item) =>
                      item.kind !== 'image' && (config.pool !== 'shots' || item.kind === 'shot'),
                  )
                  .map((item) => (
                    <label className="check-label" key={item.id}>
                      <input
                        type="checkbox"
                        checked={config.materialIds?.includes(item.id) ?? false}
                        onChange={(event) => {
                          const ids = event.target.checked
                            ? [...(config.materialIds ?? []), item.id]
                            : (config.materialIds ?? []).filter((id) => id !== item.id);
                          setConfig({ ...config, materialIds: ids.length ? ids : undefined });
                        }}
                      />
                      {config.materialIds?.includes(item.id)
                        ? `${config.materialIds.indexOf(item.id) + 1}. `
                        : ''}
                      {item.name}
                    </label>
                  ))}
              </div>
            </fieldset>
          )}
          <div className="form-field">
            <label htmlFor="mix-seed">随机种子</label>
            <div className="field-inline">
              <input
                className="field-input mono"
                id="mix-seed"
                value={config.seed}
                maxLength={24}
                onChange={(event) => setConfig({ ...config, seed: event.target.value })}
              />
              <IconButton
                label="更换种子并重新选片"
                icon="refresh"
                disabled={busy}
                onClick={() => {
                  const next = {
                    ...config,
                    seed: String(crypto.getRandomValues(new Uint32Array(1))[0]),
                  };
                  setConfig(next);
                  void generate(next);
                }}
              />
            </div>
            <span className="field-help">相同素材、种子与配置会得到相同选片。</span>
          </div>
          <fieldset className="form-field">
            <legend>输出内容</legend>
            <div className="output-checks">
              {(['preview', 'draft'] as const).map((kind) => (
                <label className="check-label" key={kind}>
                  <input
                    type="checkbox"
                    checked={outputs.includes(kind)}
                    disabled={live && kind === 'draft' && !snapshot.settings.draftDirectory}
                    onChange={(event) =>
                      setOutputs(
                        event.target.checked
                          ? [...outputs, kind]
                          : outputs.filter((item) => item !== kind),
                      )
                    }
                  />
                  {kind === 'preview' ? '预览 MP4' : '剪映草稿'}
                </label>
              ))}
            </div>
          </fieldset>
          {live && !snapshot.settings.draftDirectory && (
            <p className="field-help">请先在设置填写剪映草稿绝对路径，再选择草稿输出。</p>
          )}
          <Button
            className="full"
            icon="spark"
            disabled={busy || (live && !snapshot.materials.length)}
            onClick={() => void generate()}
          >
            生成选片方案
          </Button>
          <Notice>预览 MP4 用于检查选片；剪映中的标题和关键帧仍需导出为最终成片。</Notice>
        </section>
        <section className="studio-canvas">
          <div className="section-head">
            <h2>
              选片预览<small>STORYBOARD</small>
            </h2>
            <Badge status={stale ? 'waiting' : 'completed'}>
              {stale ? '待生成新方案' : '已固定方案'}
            </Badge>
          </div>
          {live && material ? (
            <MediaPreview
              key={material.id}
              src={material.fileUrl ?? `/api/materials/${encodeURIComponent(material.id)}/file`}
              name={material.name}
            />
          ) : (
            <div className="studio-preview">
              <MaterialVisual material={material} />
              <span className="preview-tag">
                选片结构示意 · {plan ? selectedClip + 1 : 0} / {plan?.clips.length ?? 0}
              </span>
              <div className="preview-overlay">
                <h3>{clip?.label ?? '等待选片'}</h3>
                <p>{material?.name ?? '选择素材池并生成方案'}</p>
              </div>
            </div>
          )}
          <div className="preview-controls">
            <IconButton
              label="切换下一镜头"
              icon="chevron"
              disabled={!plan?.clips.length}
              onClick={() => setSelectedClip((index) => (index + 1) % (plan?.clips.length ?? 1))}
            />
            <span className="mono">
              {formatDuration(
                plan?.clips
                  .slice(0, selectedClip)
                  .reduce((sum, item) => sum + item.durationSeconds, 0) ?? 0,
              )}
            </span>
            <Progress
              value={plan?.clips.length ? ((selectedClip + 1) / plan.clips.length) * 100 : 0}
              label="当前镜头位置"
            />
            <span>{plan?.durationSeconds ?? 0} 秒</span>
            <span>{live ? '服务端方案' : '选片示意'}</span>
          </div>
          {plan && (
            <div className="timeline">
              <div className="timeline-ruler">
                {[0, 1 / 3, 2 / 3, 1].map((value) => (
                  <span key={value}>
                    {formatDuration(Math.round(plan.durationSeconds * value))}
                  </span>
                ))}
              </div>
              <div className="timeline-track">
                {plan.clips.map((item, index) => (
                  <button
                    key={index}
                    className={`timeline-clip ${selectedClip === index ? 'active' : ''}`}
                    style={{ flex: item.durationSeconds }}
                    aria-label={`预览第${index + 1}镜头：${item.label}`}
                    aria-pressed={selectedClip === index}
                    onClick={() => setSelectedClip(index)}
                  >
                    <MaterialVisual
                      material={snapshot.materials.find((source) => source.id === item.materialId)}
                    />
                    <span>
                      {item.label} · {item.durationSeconds}s
                    </span>
                  </button>
                ))}
              </div>
              <div className="audio-track">
                <Icon name="sound" />
                原片音轨 · 保留素材声音
              </div>
              <div className="plan-summary">
                <span className="mono">
                  {plan.id} · SEED {plan.config.seed}
                </span>
                <span>
                  {plan.clips.length} 个镜头 · {plan.durationSeconds} 秒
                </span>
              </div>
            </div>
          )}
          <div className="studio-bottom">
            <p>{stale ? '配置已修改，请重新生成选片方案。' : '创建任务将使用当前固定选片。'}</p>
            <Button
              variant="primary"
              icon="plus"
              disabled={
                busy ||
                stale ||
                !outputs.length ||
                (live && outputs.includes('draft') && !snapshot.settings.draftDirectory)
              }
              onClick={() => void createTask()}
            >
              创建混剪任务
            </Button>
          </div>
        </section>
      </div>
    </>
  );
}
