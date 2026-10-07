import { Link, useSearchParams } from 'react-router-dom';
import { useSnapshot } from '../app/workspace-context';
import { Icon } from '../components/Icon';
import { TaskActions } from '../components/TaskActions';
import { Button, EmptyState, Notice, PageHeader, SearchField, TaskBadge } from '../components/ui';
import { formatDate, taskLabels } from '../domain/workspace';

export function TasksPage() {
  const { snapshot, mode } = useSnapshot();
  const [params, setParams] = useSearchParams();
  const filter = params.get('status') ?? 'all';
  const query = params.get('q') ?? '';
  const tasks = snapshot.tasks.filter(
    (task) =>
      (filter === 'all' || task.status === filter) &&
      `${task.name} ${task.id}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
  );
  function update(key: string, value: string) {
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      },
      { replace: true },
    );
  }
  return (
    <>
      <PageHeader title="任务中心" subtitle="查看每一步的进度，处理需要关注的任务。">
        <Link className="button primary" to="?create=1">
          <Icon name="plus" />
          新建任务
        </Link>
      </PageHeader>
      <div className="filter-bar">
        <div className="tabs" aria-label="任务状态">
          {Object.entries({ all: '全部', ...taskLabels })
            .filter(([key]) => mode === 'demo' || key !== 'paused')
            .map(([key, label]) => (
              <button
                key={key}
                className={`tab ${filter === key ? 'active' : ''}`}
                aria-pressed={filter === key}
                onClick={() => update('status', key)}
              >
                {label}
                <small>
                  {snapshot.tasks.filter((task) => key === 'all' || task.status === key).length}
                </small>
              </button>
            ))}
        </div>
        <SearchField
          label="搜索任务名称或编号"
          value={query}
          onChange={(value) => update('q', value)}
        />
      </div>
      {!tasks.length ? (
        <EmptyState
          icon="tasks"
          title="这里还没有任务"
          description="切换筛选，或从素材创建一个新任务。"
        >
          <Button onClick={() => setParams({})}>查看全部</Button>
        </EmptyState>
      ) : (
        <div className="table-wrap" role="region" aria-label="任务列表" tabIndex={0}>
          <table>
            <thead>
              <tr>
                <th scope="col">任务名称</th>
                <th scope="col">类型</th>
                <th scope="col">状态 / 当前阶段</th>
                <th scope="col">创建时间</th>
                <th scope="col">操作</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task.id}>
                  <td>
                    <div className="table-name">
                      <span className="task-mini-icon">
                        <Icon name={task.kind === 'mix' ? 'scissors' : 'film'} />
                      </span>
                      <Link to={`?task=${task.id}`}>
                        {task.name}
                        <small>{task.id}</small>
                      </Link>
                    </div>
                  </td>
                  <td className="muted">{task.kind === 'mix' ? '混剪任务' : '分析任务'}</td>
                  <td>
                    <TaskBadge status={task.status} />
                    <div className="task-step">{task.stage}</div>
                  </td>
                  <td className="muted mono">{formatDate(task.createdAt)}</td>
                  <td>
                    <div className="table-actions">
                      <TaskActions task={task} />
                      <Link
                        className="icon-button"
                        aria-label={`查看${task.name}任务详情`}
                        to={`?task=${task.id}`}
                      >
                        <Icon name="chevron" />
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Notice>
        {mode === 'live'
          ? '任务由本地服务自动串行执行，状态定期刷新。支持取消排队或运行中的任务；失败、中断或取消后可重新排队。'
          : '当前为示例任务。你可以暂停、继续、重试，或在详情中手动推进演示阶段。'}
      </Notice>
    </>
  );
}
