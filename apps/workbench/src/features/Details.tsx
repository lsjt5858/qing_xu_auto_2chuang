import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useSnapshot } from '../app/workspace-context';
import { Dialog } from '../components/Dialog';
import { MaterialVisual } from '../components/MaterialCard';
import { MediaPreview } from '../components/MediaPreview';
import { Button, EmptyState, Notice, Progress, TaskBadge } from '../components/ui';
import type { Material, Task } from '../domain/types';
import {
  formatBytes,
  formatDate,
  formatDuration,
  materialLabels,
  materialStatusLabels,
  outputLabels,
  stepLabels,
} from '../domain/workspace';
import { TaskActions } from '../components/TaskActions';
import { CreateTaskDialog } from './CreateTaskDialog';
import { ImportFiles } from './ImportFiles';

function MaterialDetails({ material, onClose }: { material: Material; onClose: () => void }) {
  const { mode } = useSnapshot();
  const live = mode === 'live';
  const [tab, setTab] = useState('overview');
  return (
    <Dialog
      drawer
      title="素材详情"
      subtitle={`ASSET / ${material.id}`}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>关闭</Button>
          <Link
            className="button primary"
            to={material.kind === 'image' ? '/studio' : `?create=1&materials=${material.id}`}
          >
            {material.kind === 'image' ? '去混剪工作室' : '创建处理任务'}
          </Link>
        </>
      }
    >
      {live && material.kind !== 'image' ? (
        <MediaPreview
          src={material.fileUrl ?? `/api/materials/${encodeURIComponent(material.id)}/file`}
          name={material.name}
        />
      ) : (
        <div className="drawer-preview">
          <MaterialVisual material={material} />
        </div>
      )}
      <h2 className="detail-heading">{material.name}</h2>
      <div className="detail-tabs" aria-label="素材详情分类">
        {[
          ['overview', '基本信息'],
          ['scenes', '镜头'],
          ['transcript', '转录'],
        ].map(([key, label]) => (
          <button
            key={key}
            className={`detail-tab ${tab === key ? 'active' : ''}`}
            aria-pressed={tab === key}
            onClick={() => setTab(key!)}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === 'overview' && (
        <dl className="summary-list">
          <dt>素材类型</dt>
          <dd>{materialLabels[material.kind]}</dd>
          <dt>时长 / 大小</dt>
          <dd>
            {material.kind === 'image' ? '照片' : formatDuration(material.durationSeconds)} ·{' '}
            {formatBytes(material.sizeBytes)}
          </dd>
          <dt>处理状态</dt>
          <dd>{materialStatusLabels[material.status]}</dd>
          <dt>素材来源</dt>
          <dd>
            {live
              ? '本地素材库 · 实际文件'
              : material.source === 'local'
                ? '已登记的本地文件 · 未上传'
                : '示例数据'}
          </dd>
          <dt>导入时间</dt>
          <dd>{formatDate(material.createdAt)}</dd>
        </dl>
      )}
      {tab === 'scenes' &&
        (material.scenes.length ? (
          <>
            <p className="field-help">
              共 {material.scenes.length} 个原始镜头{live ? '' : ' · 示例时间段'}
            </p>
            <div className="scene-list">
              {material.scenes.map((scene, index) => (
                <div className="scene-cell" key={scene.id}>
                  <strong>{String(index + 1).padStart(2, '0')}</strong>
                  <span>
                    {formatDuration(scene.startSeconds)} →{' '}
                    {formatDuration(scene.startSeconds + scene.durationSeconds)}
                  </span>
                  <small>{scene.durationSeconds} 秒</small>
                </div>
              ))}
            </div>
          </>
        ) : (
          <EmptyState
            icon="scissors"
            title="还没有镜头分析"
            description="完成原始切镜后，在这里查看镜头结构。"
          />
        ))}
      {tab === 'transcript' &&
        (material.transcript.length ? (
          material.transcript.map((segment) => (
            <div className="activity-row" key={segment.startSeconds}>
              <time className="mono muted">{formatDuration(segment.startSeconds)}</time>
              <div>
                {segment.text}
                <small>{live ? '转录结果' : '转录示例'}</small>
              </div>
            </div>
          ))
        ) : (
          <EmptyState
            icon="file"
            title="暂无转录结果"
            description="完成音频转录后，在这里查看带时间戳的文本。"
          />
        ))}
    </Dialog>
  );
}

function TaskDetails({ task, onClose }: { task: Task; onClose: () => void }) {
  const { snapshot, busy, execute, mode } = useSnapshot();
  return (
    <Dialog
      drawer
      title="任务详情"
      subtitle={`${task.id} · ${task.kind === 'mix' ? '混剪任务' : '分析任务'}`}
      onClose={onClose}
      busy={busy}
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>
            关闭
          </Button>
          {task.status !== 'completed' && <TaskActions task={task} />}
        </>
      }
    >
      <div className="detail-title-row">
        <h2>{task.name}</h2>
        <TaskBadge status={task.status} />
      </div>
      <div className="detail-progress">
        <div className="progress-label">
          <span>{task.stage}</span>
          <span>{task.progress === null ? '进度未知' : `${task.progress}%`}</span>
        </div>
        <Progress value={task.progress} label="任务处理进度" />
      </div>
      <ol className="log-list">
        {task.events.map((event, index) => (
          <li
            key={`${event.at}-${index}`}
            className={index === task.events.length - 1 ? 'current' : ''}
          >
            {event.message}
            <time>{formatDate(event.at)}</time>
          </li>
        ))}
      </ol>
      {task.error && <Notice warm>{task.error}</Notice>}
      <h3 className="detail-section-heading">处理选项</h3>
      <p className="field-help">
        {task.kind === 'mix'
          ? task.requestedOutputs.map((kind) => outputLabels[kind]).join(' · ')
          : task.steps.map((step) => stepLabels[step]).join(' → ')}
      </p>
      {task.plan && (
        <>
          <h3 className="detail-section-heading">固定选片方案</h3>
          <p className="field-help mono">
            {task.plan.id} · SEED {task.plan.config.seed}
          </p>
          <p className="field-help">
            {task.plan.clips.map((clip) => `${clip.label} ${clip.durationSeconds}s`).join(' → ')}
          </p>
        </>
      )}
      <h3 className="detail-section-heading">事件日志</h3>
      <pre className="code-log">
        {task.events
          .map(
            (event) =>
              `${mode === 'demo' ? '[demo] ' : ''}${formatDate(event.at)} ${event.message}`,
          )
          .join('\n')}
      </pre>
      {mode === 'demo' && task.status === 'running' && (
        <Button
          className="full detail-action"
          disabled={busy}
          icon="arrow"
          onClick={() =>
            void execute(
              (repository) => repository.commandTask(task.id, 'advance'),
              '已推进演示阶段',
            )
          }
        >
          推进一个演示阶段
        </Button>
      )}
      {task.status === 'completed' && (
        <>
          <h3 className="detail-section-heading">任务产物</h3>
          {task.kind === 'mix'
            ? task.outputIds.map((id) => {
                const output = snapshot.outputs.find((item) => item.id === id);
                return (
                  output && (
                    <Link className="result-link" key={id} to={`/publish?output=${id}`}>
                      {output.name}
                      <span>{outputLabels[output.kind]}</span>
                    </Link>
                  )
                );
              })
            : task.materialIds.map((id) => (
                <Link className="result-link" to={`/library?material=${id}`} key={id}>
                  查看素材分析结果
                </Link>
              ))}
        </>
      )}
    </Dialog>
  );
}

export function WorkspaceDialogs() {
  const { snapshot, mode } = useSnapshot();
  const [params, setParams] = useSearchParams();
  const taskId = params.get('task'),
    materialId = params.get('material');
  const close = () =>
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        ['create', 'materials', 'import', 'task', 'material'].forEach((key) => next.delete(key));
        return next;
      },
      { replace: true },
    );
  if (params.has('create'))
    return (
      <CreateTaskDialog
        key="create"
        initialIds={(params.get('materials') ?? '').split(',')}
        onClose={close}
      />
    );
  if (params.has('import'))
    return (
      <Dialog
        title="导入素材"
        subtitle={
          mode === 'live' ? '上传本地视频，或显式扫描本机目录。' : '选择要登记到工作台的视频文件。'
        }
        onClose={close}
      >
        <ImportFiles onImported={close} />
      </Dialog>
    );
  if (taskId) {
    const task = snapshot.tasks.find((item) => item.id === taskId);
    if (task) return <TaskDetails key={task.id} task={task} onClose={close} />;
  }
  if (materialId) {
    const material = snapshot.materials.find((item) => item.id === materialId);
    if (material) return <MaterialDetails key={material.id} material={material} onClose={close} />;
  }
  if (taskId || materialId)
    return (
      <Dialog title="内容未找到" onClose={close}>
        <EmptyState
          title="内容已不在当前工作空间"
          description={
            mode === 'live'
              ? '请返回列表刷新后重新选择。'
              : '示例数据会在刷新后复原，请返回列表重新选择。'
          }
        >
          <Button onClick={close}>返回列表</Button>
        </EmptyState>
      </Dialog>
    );
  return null;
}
