import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import type { WorkspaceRepository, WorkspaceSnapshot } from '../domain/types';
import { Toast } from '../components/Toast';
import { WorkspaceContext } from './workspace-context';

const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : '操作失败，请重试。';

export function WorkspaceProvider({
  repository,
  children,
}: {
  repository: WorkspaceRepository;
  children: ReactNode;
}) {
  const [snapshot, setSnapshot] = useState<WorkspaceSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const locked = useRef(false);
  const revision = useRef(0);
  const reload = useRef<() => void>(() => {});
  const toastTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    let active = true;
    let reading = false;
    const load = async () => {
      if (reading || locked.current) return;
      reading = true;
      const started = revision.current;
      try {
        const data = await repository.load();
        if (active && started === revision.current) {
          setSnapshot(data);
          setError(null);
        }
      } catch (cause) {
        if (active && started === revision.current) setError(errorMessage(cause));
      } finally {
        reading = false;
        if (active) setLoading(false);
      }
    };
    reload.current = () => void load();
    void load();
    const timer = repository.mode === 'live' ? setInterval(() => void load(), 3000) : undefined;
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [repository]);

  useEffect(() => () => clearTimeout(toastTimer.current), []);

  const notify = useCallback((text: string) => {
    clearTimeout(toastTimer.current);
    setMessage(text);
    toastTimer.current = setTimeout(() => setMessage(''), 4500);
  }, []);

  const run = useCallback(
    async <T,>(command: (adapter: WorkspaceRepository) => Promise<T>, success?: string) => {
      if (locked.current) return null;
      locked.current = true;
      revision.current++;
      setBusy(true);
      try {
        const updated = await command(repository);
        if (success) notify(success);
        return updated;
      } catch (cause) {
        notify(errorMessage(cause));
        return null;
      } finally {
        revision.current++;
        locked.current = false;
        setBusy(false);
      }
    },
    [repository, notify],
  );

  const execute = useCallback(
    async (
      command: (adapter: WorkspaceRepository) => Promise<WorkspaceSnapshot>,
      success: string,
    ) => {
      const updated = await run(command, success);
      if (updated) {
        setSnapshot(updated);
        setError(null);
      }
      return updated;
    },
    [run],
  );

  return (
    <WorkspaceContext
      value={{
        mode: repository.mode,
        snapshot,
        loading,
        error,
        busy,
        execute,
        run,
        notify,
        refresh: () => reload.current(),
      }}
    >
      {children}
      <Toast message={message} />
    </WorkspaceContext>
  );
}
