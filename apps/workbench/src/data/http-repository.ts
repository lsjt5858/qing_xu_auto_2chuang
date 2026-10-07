import type {
  MixConfig,
  MixPlan,
  OutputKind,
  PairingCode,
  ProcessingRequest,
  PublishRequest,
  Settings,
  TaskCommand,
  WorkspaceRepository,
  WorkspaceSnapshot,
} from '../domain/types';

export const serviceStartHint =
  '请在仓库根目录运行 ./run.sh workbench --execute，确认 http://127.0.0.1:8766 可用。开发模式运行 npm --prefix apps/workbench run dev，/api 代理到 8766；构建后可直接打开 8766。仅查看演示请使用 ?demo=1。';

/** Same-origin cookie session. No tokens on disk and no automatic mutation replay. */
export class HttpWorkspaceRepository implements WorkspaceRepository {
  readonly mode = 'live' as const;
  private session: Promise<string> | null = null;

  private ensureSession(): Promise<string> {
    if (!this.session) {
      this.session = this.send<{ csrfToken: string }>('/session', {
        method: 'POST',
        headers: { 'X-Workbench': '1' },
      })
        .then((value) => {
          if (!value.csrfToken || typeof value.csrfToken !== 'string') {
            throw new Error(`API 会话响应无效。${serviceStartHint}`);
          }
          return value.csrfToken;
        })
        .catch((error: unknown) => {
          this.session = null;
          throw error;
        });
    }
    return this.session;
  }

  private async send<T>(path: string, options: RequestInit): Promise<T> {
    const mutation = options.method !== 'GET' && path !== '/session';
    const uncertain = mutation ? '操作可能已生效，请先刷新检查记录，勿重复提交。' : '';
    let response: Response;
    try {
      response = await fetch(`/api${path}`, {
        ...options,
        credentials: 'same-origin',
        cache: 'no-store',
        signal: AbortSignal.timeout(120_000),
      });
    } catch {
      throw new Error(`无法连接本地服务或请求超时。${uncertain}${serviceStartHint}`);
    }
    let data: unknown;
    try {
      data = await response.json();
    } catch {
      throw new Error(
        `本地 API 未返回有效 JSON（HTTP ${response.status}）。${uncertain}${serviceStartHint}`,
      );
    }
    if (!response.ok) {
      const detail =
        data && typeof data === 'object' && 'detail' in data && typeof data.detail === 'string'
          ? data.detail
          : `请求失败（HTTP ${response.status}）`;
      if (response.status === 401 || response.status === 403) {
        this.session = null;
        throw new Error(`会话或授权失效：${detail}。请刷新后重新核对；本次请求未自动重试。`);
      }
      throw new Error(`${detail}${response.status >= 500 ? `。${uncertain}` : ''}`);
    }
    return data as T;
  }

  private async request<T>(path: string, method = 'POST', body?: unknown): Promise<T> {
    const token = await this.ensureSession();
    const headers = new Headers({ Accept: 'application/json' });
    if (method !== 'GET') headers.set('X-CSRF-Token', token);
    if (body !== undefined && !(body instanceof FormData))
      headers.set('Content-Type', 'application/json');
    return this.send<T>(path, {
      method,
      headers,
      body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
    });
  }

  load() {
    return this.request<WorkspaceSnapshot>('/snapshot', 'GET');
  }
  importFiles(files: File[]) {
    return this.upload('/materials/import', files);
  }
  importOutputs(files: File[]) {
    return this.upload('/outputs/import', files);
  }
  private upload(path: string, files: File[]) {
    if (!files.length) return Promise.reject(new Error('请选择视频文件。'));
    const body = new FormData();
    files.forEach((file) => body.append('files', file));
    return this.request<WorkspaceSnapshot>(path, 'POST', body);
  }
  importDirectory(path: string) {
    return this.request<WorkspaceSnapshot>('/materials/directory', 'POST', { path });
  }
  createTasks(request: ProcessingRequest) {
    return this.request<WorkspaceSnapshot>('/tasks', 'POST', request);
  }
  commandTask(id: string, command: TaskCommand) {
    if (command !== 'cancel' && command !== 'retry')
      return Promise.reject(new Error('真实任务仅支持 cancel / retry。'));
    return this.request<WorkspaceSnapshot>(`/tasks/${encodeURIComponent(id)}/command`, 'POST', {
      command,
    });
  }
  createMixPlan(config: MixConfig) {
    return this.request<MixPlan>('/mix/plans', 'POST', config);
  }
  createMixTask(plan: MixPlan, outputs: Exclude<OutputKind, 'final'>[]) {
    return this.request<WorkspaceSnapshot>('/mix/tasks', 'POST', { planId: plan.id, outputs });
  }
  confirmOutput(id: string) {
    return this.request<WorkspaceSnapshot>(
      `/outputs/${encodeURIComponent(id)}/confirm`,
      'POST',
      {},
    );
  }
  publish(request: PublishRequest) {
    return this.request<WorkspaceSnapshot>('/publish', 'POST', request);
  }
  cancelPublish(id: string) {
    return this.request<WorkspaceSnapshot>(`/publish/${encodeURIComponent(id)}/cancel`, 'POST', {});
  }
  saveSettings(settings: Settings) {
    return this.request<WorkspaceSnapshot>('/settings', 'PUT', settings);
  }
  createPairing() {
    return this.request<PairingCode>('/pairing', 'POST', {});
  }
  revokePairing(extensionId: string) {
    return this.request<WorkspaceSnapshot>(`/pairing/${encodeURIComponent(extensionId)}`, 'DELETE');
  }
}
