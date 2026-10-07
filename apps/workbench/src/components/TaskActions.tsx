import { Link } from 'react-router-dom';
import { useSnapshot } from '../app/workspace-context';
import type { Task, TaskCommand, TaskStatus } from '../domain/types';
import { Button } from './ui';

const actions: Record<TaskStatus, { command: TaskCommand; label: string } | null> = {
  queued: { command: 'start', label: '开始演示' },
  running: { command: 'pause', label: '暂停' },
  paused: { command: 'resume', label: '继续' },
  failed: { command: 'retry', label: '重试' },
  completed: null,
  cancelled: null,
  skipped: null,
  interrupted: null,
};

export function TaskActions({ task }: { task: Task }) {
  const { busy, execute, mode } = useSnapshot();
  const live = mode === 'live';
  const action = live
    ? ['queued', 'running'].includes(task.status)
      ? { command: 'cancel' as const, label: '取消任务' }
      : ['failed', 'cancelled', 'interrupted'].includes(task.status)
        ? { command: 'retry' as const, label: '重试' }
        : null
    : actions[task.status];
  return action ? (
    <Button
      className="small"
      disabled={busy}
      icon={action.command === 'retry' ? 'refresh' : undefined}
      onClick={() =>
        void execute(
          (repository) => repository.commandTask(task.id, action.command),
          `任务${action.label}请求已处理${live ? '' : '（演示）'}`,
        )
      }
    >
      {action.label}
    </Button>
  ) : (
    <Link className="button small" to={`/tasks?task=${task.id}`}>
      查看结果
    </Link>
  );
}
