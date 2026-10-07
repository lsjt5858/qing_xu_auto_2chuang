import { accountFields, fileSize, localOrigin, parseJob, record, requireThat, Stop, type Account, type Job, type Status } from './protocol';

const DOWNLOAD_IDLE_MS = 15_000;

async function readChunk<T>(
  reader: ReadableStreamDefaultReader<T>,
  signal: AbortSignal,
): Promise<ReadableStreamReadResult<T>> {
  signal.throwIfAborted();
  let abort!: () => void;
  const aborted = new Promise<never>((_, reject) => {
    abort = () => reject(signal.reason ?? new Stop('cancelled', '操作已停止'));
    signal.addEventListener('abort', abort, { once: true });
  });
  try {
    return await Promise.race([reader.read(), aborted]);
  } finally {
    signal.removeEventListener('abort', abort);
  }
}

export class Api {
  readonly origin: string;
  constructor(port: number | string, readonly extensionId: string, public token = '',
    private readonly fetcher: typeof fetch = fetch) {
    this.origin = localOrigin(port);
  }

  private async request(path: string, body?: unknown, signal?: AbortSignal, leaseToken?: string,
    pair = false, timeout = true): Promise<Response> {
    const headers = new Headers({ 'X-Extension-Id': this.extensionId });
    if (!pair) {
      requireThat(this.token, 'pairing', '请先配对本地工作台');
      headers.set('Authorization', `Bearer ${this.token}`);
    }
    if (body !== undefined) headers.set('Content-Type', 'application/json');
    if (leaseToken) headers.set('X-Lease-Token', leaseToken);
    const response = await this.fetcher(`${this.origin}/api/extension${path}`, {
      method: body === undefined ? 'GET' : 'POST', headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      redirect: 'error', credentials: 'omit', cache: 'no-store',
      signal: timeout
        ? (signal ? AbortSignal.any([signal, AbortSignal.timeout(15_000)]) : AbortSignal.timeout(15_000))
        : signal,
    });
    requireThat(response.ok, 'http', `本机 API 请求失败（HTTP ${response.status}），已停止；请检查配对和租约`);
    return response;
  }

  private async ok(path: string, body: unknown, signal?: AbortSignal): Promise<void> {
    const response = record(await (await this.request(path, body, signal)).json());
    requireThat(response.ok === true, 'api', '本机 API 未确认操作');
  }

  async pair(code: string): Promise<string> {
    requireThat(code.trim().length > 0, 'pairing', '请输入工作台生成的配对码');
    const result = record(await (await this.request('/pair', {
      code: code.trim(), extensionId: this.extensionId, name: 'Jingflow Publisher',
    }, undefined, undefined, true)).json());
    requireThat(typeof result.token === 'string' && result.token.length > 0, 'pairing', '配对响应缺少 token');
    return result.token;
  }

  async heartbeat(account?: Account, signal?: AbortSignal): Promise<void> {
    await this.ok('/heartbeat', account ? { account: accountFields(account) } : {}, signal);
  }

  async claim(accountUid: string, signal?: AbortSignal): Promise<Readonly<Job> | null> {
    const response = record(await (await this.request('/claim', { accountUid }, signal)).json());
    return response.job === null ? null : parseJob(response.job);
  }

  async renew(job: Job, signal?: AbortSignal): Promise<void> {
    await this.ok(`/jobs/${encodeURIComponent(job.id)}/heartbeat`, { leaseToken: job.leaseToken }, signal);
  }

  async event(job: Job, status: Status, message?: string, evidence?: string, signal?: AbortSignal): Promise<void> {
    await this.ok(`/jobs/${encodeURIComponent(job.id)}/event`,
      { leaseToken: job.leaseToken, status, message, evidence }, signal);
  }

  async file(job: Job, signal: AbortSignal): Promise<Blob> {
    fileSize(job.sizeBytes);
    const idle = new AbortController();
    const downloadSignal = AbortSignal.any([signal, idle.signal]);
    let idleTimer: ReturnType<typeof setTimeout> | undefined;
    const armIdle = () => {
      if (idleTimer) clearTimeout(idleTimer);
      idleTimer = setTimeout(() => {
        idle.abort(new Stop('download_idle', '文件下载空闲超过 15 秒，已停止'));
      }, DOWNLOAD_IDLE_MS);
    };
    armIdle();
    try {
      const response = await this.request(
        `/jobs/${encodeURIComponent(job.id)}/file`, undefined, downloadSignal, job.leaseToken, false, false,
      );
      const declared = response.headers.get('Content-Length');
      requireThat(declared === null || Number(declared) === job.sizeBytes, 'size', '下载文件大小与冻结任务不一致');
      const reader = response.body?.getReader();
      requireThat(reader, 'download', '文件响应没有数据流');
      let total = 0;
      const parts: Uint8Array<ArrayBuffer>[] = [];
      try {
        for (;;) {
          const { done, value } = await readChunk(reader, downloadSignal);
          if (done) break;
          armIdle();
          total += value.byteLength;
          requireThat(total <= job.sizeBytes, 'size', '下载文件大小超过任务声明，已停止');
          parts.push(new Uint8Array(value));
        }
        requireThat(total === job.sizeBytes, 'size', '下载文件不完整，大小与任务不一致');
        return new Blob(parts, { type: videoMime(job.fileName) });
      } catch (error) {
        await reader.cancel().catch(() => undefined);
        throw error;
      } finally {
        reader.releaseLock();
      }
    } finally {
      if (idleTimer) clearTimeout(idleTimer);
    }
  }
}

export function videoMime(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase();
  const mime: Record<string, string> = { mp4: 'video/mp4', mov: 'video/quicktime', webm: 'video/webm', m4v: 'video/x-m4v' };
  if (!ext || !mime[ext]) throw new Stop('format', '仅支持 MP4/MOV/WEBM/M4V 视频，其他格式需要人工处理');
  return mime[ext];
}
