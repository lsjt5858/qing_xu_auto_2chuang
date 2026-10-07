import { Link } from 'react-router-dom';
import { useSnapshot } from '../app/workspace-context';
import { Icon, type IconName } from '../components/Icon';
import { MaterialCard, MaterialVisual } from '../components/MaterialCard';
import { EmptyState, PageHeader, Progress, SectionHeader, TaskBadge } from '../components/ui';
import { formatDate, formatDuration, getOverview } from '../domain/workspace';

export function DashboardPage() {
  const { snapshot, mode } = useSnapshot();
  const summary = getOverview(snapshot);
  const current =
    snapshot.tasks.find((task) => task.status === 'running') ??
    snapshot.tasks.find((task) => ['queued', 'paused'].includes(task.status)) ??
    snapshot.tasks[0];
  const material = snapshot.materials.find((item) => item.id === current?.materialIds[0]);
  const ready = summary.readyOutputs[0];
  const readyMaterial = snapshot.materials.find((item) => item.id === ready?.materialId);
  const metrics: { title: string; icon: IconName; value: number; description: string }[] = [
    {
      title: '素材总览',
      icon: 'folder',
      value: summary.materialCount,
      description: '份素材已入库',
    },
    {
      title: '进行中的任务',
      icon: 'tasks',
      value: summary.runningCount,
      description: `${summary.queuedCount} 个排队中`,
    },
    {
      title: '可用镜头',
      icon: 'scissors',
      value: summary.sceneCount,
      description: '来自已分析素材',
    },
    {
      title: '待发布成片',
      icon: 'send',
      value: summary.readyOutputs.length,
      description: '等待你的确认',
    },
  ];
  const today = new Intl.DateTimeFormat('zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  }).format(new Date());
  return (
    <>
      <PageHeader title="工作台" subtitle={`${today} · 查看当前任务与最近素材。`}>
        <Link className="button secondary-action" to="/library?import=1">
          <Icon name="upload" />
          导入素材
        </Link>
        <Link className="button primary" to="?create=1">
          <Icon name="plus" />
          新建任务
        </Link>
      </PageHeader>
      <div className="metric-strip">
        {metrics.map((metric) => (
          <div className="metric" key={metric.title}>
            <div className="metric-label">
              <Icon name={metric.icon} />
              {metric.title}
            </div>
            <div className="metric-value">
              {metric.value}
              <small>{metric.description}</small>
            </div>
          </div>
        ))}
      </div>
      <div className="dashboard-main">
        <section>
          <SectionHeader title="继续创作" eyebrow="IN PROGRESS" to="/tasks" action="任务中心" />
          {current ? (
            <>
              <div className="analysis-feature">
                <div className="analysis-heading">
                  <span className="overline">PROJECT / {current.id}</span>
                  <span>
                    {current.kind === 'mix' ? '混剪选片' : '镜头分析'}
                    {mode === 'demo' ? ' · 示例' : ''}
                  </span>
                </div>
                <div className="analysis-main">
                  <div>
                    <h3>{current.name}</h3>
                    <p>
                      {material
                        ? `${formatDuration(material.durationSeconds)} 原片 · ${material.source === 'sample' ? '示例素材' : '本地文件'}`
                        : '等待素材信息'}
                    </p>
                  </div>
                  <div className="shot-count">
                    <strong>{current.plan?.clips.length ?? material?.scenes.length ?? '—'}</strong>
                    <span>{current.kind === 'mix' ? '个选片' : '原始镜头'}</span>
                  </div>
                </div>
                <div className="shot-map" aria-label="镜头结构示意">
                  {(current.plan?.clips ?? material?.scenes ?? []).map((scene, index) => (
                    <span
                      key={index}
                      style={{ flex: scene.durationSeconds }}
                      className={
                        index <
                        Math.floor(
                          ((current.progress ?? 0) / 100) *
                            (current.plan?.clips.length ?? material?.scenes.length ?? 0),
                        )
                          ? 'analyzed'
                          : ''
                      }
                    />
                  ))}
                </div>
                <div className="shot-map-label">
                  <span>00:00</span>
                  <span>保留原始镜头结构</span>
                  <span>
                    {formatDuration(
                      current.plan?.durationSeconds ?? material?.durationSeconds ?? null,
                    )}
                  </span>
                </div>
              </div>
              <div className="feature-foot">
                <div className="feature-progress">
                  <div className="progress-label">
                    <span>
                      <TaskBadge status={current.status} />
                      {current.stage}
                    </span>
                    <span>{current.progress === null ? '进度未知' : `${current.progress}%`}</span>
                  </div>
                  <Progress value={current.progress} label={`${current.name}进度`} />
                </div>
                <Link className="button small" to={`/tasks?task=${current.id}`}>
                  查看任务
                </Link>
              </div>
              {snapshot.tasks
                .filter((task) => task.id !== current.id)
                .slice(0, 2)
                .map((task) => (
                  <Link className="task-mini" to={`/tasks?task=${task.id}`} key={task.id}>
                    <span className="task-mini-icon">
                      <Icon name={task.kind === 'mix' ? 'scissors' : 'film'} />
                    </span>
                    <span className="task-mini-title">
                      {task.name}
                      <small>
                        {task.stage} · {formatDate(task.createdAt)}
                      </small>
                    </span>
                    <TaskBadge status={task.status} />
                    <Icon name="chevron" />
                  </Link>
                ))}
            </>
          ) : (
            <EmptyState title="从第一个任务开始" description="导入素材后，就可以安排视频处理。">
              <Link className="button primary" to="?create=1">
                新建任务
              </Link>
            </EmptyState>
          )}
        </section>
        <aside className="right-rail">
          <div className="rail-group">
            <div className="rail-title">需要关注</div>
            <div className="attention-item">
              <span className="attention-number">01</span>
              <div>
                <h3>
                  {summary.failures.length
                    ? `${summary.failures.length} 个任务需要重试`
                    : '暂无异常任务'}
                </h3>
                <p>{summary.failures[0]?.name ?? '任务状态正常，可以继续创作。'}</p>
                <Link
                  className="text-button"
                  to={summary.failures[0] ? `/tasks?task=${summary.failures[0].id}` : '/tasks'}
                >
                  {summary.failures.length ? '查看原因' : '查看任务'}
                  <Icon name="arrow" />
                </Link>
              </div>
            </div>
            <div className="attention-item">
              <span className="attention-number">02</span>
              <div>
                <h3>继续整理镜头池</h3>
                <p>用已有片段制作下一支成片。</p>
                <Link className="text-button" to="/studio">
                  打开混剪工作室
                  <Icon name="arrow" />
                </Link>
              </div>
            </div>
          </div>
          <div className="rail-group">
            <div className="rail-divider" />
            <div className="rail-title">准备好发布</div>
            {ready ? (
              <>
                <div className="ready-media">
                  <MaterialVisual material={readyMaterial} />
                  <span className="duration">{formatDuration(ready.durationSeconds)}</span>
                </div>
                <h3 className="ready-title">{ready.name}</h3>
                <p className="ready-meta">
                  {ready.width && ready.height ? `${ready.width} × ${ready.height} · ` : ''}MP4 ·
                  已确认成片
                </p>
                <Link className="button full small" to={`/publish?output=${ready.id}`}>
                  <Icon name="send" />
                  前往发布
                </Link>
              </>
            ) : (
              <div className="rail-empty">
                <Icon name="check" />
                <p>暂无待发布成片</p>
                <Link className="text-button" to="/publish">
                  查看成片与记录
                  <Icon name="arrow" />
                </Link>
              </div>
            )}
          </div>
        </aside>
      </div>
      <section className="recent-section">
        <SectionHeader title="最近素材" eyebrow="RECENT ASSETS" to="/library" action="查看素材库" />
        {summary.recentMaterials.length ? (
          <div className="media-grid">
            {summary.recentMaterials.map((item) => (
              <MaterialCard key={item.id} material={item} />
            ))}
          </div>
        ) : (
          <EmptyState title="素材库为空" description="选择本地视频，开始整理你的内容。" />
        )}
      </section>
    </>
  );
}
