import { DemoWorkspaceRepository } from './demo-repository';
import { HttpWorkspaceRepository } from './http-repository';
import type { WorkspaceRepository } from '../domain/types';

export function createWorkspaceRepository(search: string): WorkspaceRepository {
  return new URLSearchParams(search).get('demo') === '1'
    ? new DemoWorkspaceRepository()
    : new HttpWorkspaceRepository();
}
