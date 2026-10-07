import { createContext, useContext } from 'react';
import type { WorkspaceRepository, WorkspaceSnapshot } from '../domain/types';

export interface WorkspaceContextValue {
  mode: WorkspaceRepository['mode'];
  snapshot: WorkspaceSnapshot | null;
  loading: boolean;
  error: string | null;
  busy: boolean;
  refresh: () => void;
  notify: (message: string) => void;
  run: <T>(
    command: (repository: WorkspaceRepository) => Promise<T>,
    success?: string,
  ) => Promise<T | null>;
  execute: (
    command: (repository: WorkspaceRepository) => Promise<WorkspaceSnapshot>,
    success: string,
  ) => Promise<WorkspaceSnapshot | null>;
}

export const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function useWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context) throw new Error('WorkspaceProvider is required.');
  return context;
}

export function useSnapshot() {
  const context = useWorkspace();
  if (!context.snapshot) throw new Error('Workspace is not loaded.');
  return { ...context, snapshot: context.snapshot };
}
