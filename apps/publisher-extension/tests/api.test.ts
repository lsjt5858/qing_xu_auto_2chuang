// @vitest-environment node
import { describe, expect, it, vi } from 'vitest';
import { Api } from '../src/api';
import { readIdentityInMain } from '../src/identity';
import { MAX_FILE_BYTES, type Job } from '../src/protocol';

const job: Job = { id: 'p/1', outputId: 'o', accountId: 'a', accountUid: '123',
  title: '', caption: '', mode: 'prefill', fileName: 'clip.mp4', sizeBytes: 4, leaseToken: 'lease' };
const account = { uid: '123', nickname: 'N', unique_id: 'H', short_id: 'S' };

describe('本地 API 客户端', () => {
  it('配对无认证头；后续带认证头，只发送四字段身份', async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(Response.json({ token: 'secret' }))
      .mockResolvedValueOnce(Response.json({ ok: true }));
    const api = new Api(8766, 'extension', '', fetcher);
    expect(await api.pair('code')).toBe('secret');
    api.token = 'secret';
    await api.heartbeat({ ...account, cookie: 'never' } as typeof account);
    const [url, init] = fetcher.mock.calls[1];
    expect(url).toBe('http://127.0.0.1:8766/api/extension/heartbeat');
    expect(init.headers.get('Authorization')).toBe('Bearer secret');
    expect(init.headers.get('X-Extension-Id')).toBe('extension');
    expect(init.redirect).toBe('error');
    expect(init.credentials).toBe('omit');
    expect(JSON.parse(init.body)).toEqual({ account });
    expect(fetcher.mock.calls[0][1].headers.has('Authorization')).toBe(false);
  });
  it('文件携带租约，流式下载校验完整大小', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(new Uint8Array([1, 2, 3, 4])));
    const api = new Api(8766, 'id', 'token', fetcher);
    const blob = await api.file(job, new AbortController().signal);
    expect(blob.size).toBe(4);
    expect(fetcher.mock.calls[0][0]).toContain('/p%2F1/file');
    expect(fetcher.mock.calls[0][1].headers.get('X-Lease-Token')).toBe('lease');
  });
  it('持续活跃的文件下载可以超过 15 秒总时长', async () => {
    vi.useFakeTimers();
    try {
      vi.spyOn(AbortSignal, 'timeout').mockImplementation(milliseconds => {
        const controller = new AbortController();
        setTimeout(() => controller.abort(new DOMException('Timed out', 'TimeoutError')), milliseconds);
        return controller.signal;
      });
      const fetcher = vi.fn(async (_url: string | URL | Request, init?: RequestInit) => {
        const signal = init?.signal;
        let sent = 0;
        return new Response(new ReadableStream<Uint8Array>({
          start(controller) {
            const push = () => {
              if (signal?.aborted) {
                controller.error(signal.reason);
                return;
              }
              controller.enqueue(new Uint8Array([++sent]));
              if (sent === job.sizeBytes) controller.close();
              else setTimeout(push, 10_000);
            };
            signal?.addEventListener('abort', () => controller.error(signal.reason), { once: true });
            push();
          },
        }));
      });
      const download = new Api(8766, 'id', 'token', fetcher).file(job, new AbortController().signal);

      await vi.advanceTimersByTimeAsync(30_000);

      await expect(download).resolves.toHaveProperty('size', job.sizeBytes);
    } finally {
      vi.useRealTimers();
    }
  });
  it('文件流空闲 15 秒就停止并取消读取', async () => {
    vi.useFakeTimers();
    try {
      const cancel = vi.fn();
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new Uint8Array([1]));
        },
        cancel,
      });
      const download = new Api(8766, 'id', 'token', async () => new Response(stream))
        .file(job, new AbortController().signal);
      const rejected = expect(download).rejects.toThrow(/空闲/);

      await vi.advanceTimersByTimeAsync(15_000);

      await rejected;
      expect(cancel).toHaveBeenCalledOnce();
    } finally {
      vi.useRealTimers();
    }
  });
  it.each([3, 5])('文件实际大小 %s 与任务不一致就停止', async size => {
    const api = new Api(8766, 'id', 'token', async () => new Response(new Uint8Array(size)));
    await expect(api.file(job, new AbortController().signal)).rejects.toThrow(/大小/);
  });
  it('文件上限在 fetch 前检查', async () => {
    const fetcher = vi.fn();
    const api = new Api(8766, 'id', 'token', fetcher);
    await expect(api.file({ ...job, sizeBytes: MAX_FILE_BYTES + 1 }, new AbortController().signal)).rejects.toThrow(/512 MiB/);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it('断线或错误不重试，不把服务返回的敏感文本带到 UI', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response('secret-token', { status: 401 }));
    await expect(new Api(8766, 'id', 'token', fetcher).claim('123')).rejects.toThrow(/401/);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it('拒绝格式不正确的 claim 响应', async () => {
    const api = new Api(8766, 'id', 'token', async () => Response.json({ ok: true }));
    await expect(api.claim('123')).rejects.toThrow();
  });
});

describe('MAIN world 身份读取', () => {
  it('仅同源 fetch 并仅返回白名单', async () => {
    const fetcher = vi.fn().mockResolvedValue(Response.json({ status_code: 0, user: { ...account, cookies: 'no' } }));
    vi.stubGlobal('fetch', fetcher);
    expect(await readIdentityInMain()).toEqual(account);
    expect(fetcher.mock.calls[0][0]).toBe('/web/api/media/user/info/');
    expect(fetcher.mock.calls[0][1].credentials).toBe('include');
    vi.unstubAllGlobals();
  });
  it.each([
    { status_code: 1, user: account },
    { status_code: '0', user: account },
    { status_code: 0, user: { ...account, uid: 9007199254740993 } },
    { status_code: 0, data: account },
  ])('未登录、无效结构和不精确 UID 返回 null', async body => {
    vi.stubGlobal('fetch', async () => Response.json(body));
    expect(await readIdentityInMain()).toBeNull();
    vi.unstubAllGlobals();
  });
});
