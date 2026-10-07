import { afterEach, describe, expect, it, vi } from 'vitest';
import { HttpWorkspaceRepository } from './http-repository';
import { createWorkspaceRepository } from './repository';
import { createInitialSnapshot } from './fixtures';

const snapshot = {
  ...createInitialSnapshot(),
  accounts: [],
  service: { mode: 'live', version: '1', dependencies: [], extensions: [] },
};
const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });

function server() {
  const fetcher = vi
    .fn<typeof fetch>()
    .mockImplementation(async (input) =>
      String(input) === '/api/session' ? json({ csrfToken: 'session-csrf' }) : json(snapshot),
    );
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}

afterEach(() => vi.unstubAllGlobals());

describe('真实 HTTP 契约', () => {
  it('默认真实仓库，仅 demo=1 使用演示', () => {
    expect(createWorkspaceRepository('').mode).toBe('live');
    expect(createWorkspaceRepository('?demo=0').mode).toBe('live');
    expect(createWorkspaceRepository('?demo=1').mode).toBe('demo');
  });

  it('并发加载共用 session，写请求携带 CSRF，凭据仅同源', async () => {
    const fetcher = server();
    const repository = new HttpWorkspaceRepository();
    await Promise.all([repository.load(), repository.load()]);
    await repository.saveSettings(snapshot.settings);
    const calls = fetcher.mock.calls;
    expect(calls.filter(([url]) => url === '/api/session')).toHaveLength(1);
    expect(calls[0]?.[1]).toMatchObject({
      method: 'POST',
      credentials: 'same-origin',
    });
    expect(new Headers(calls[0]?.[1]?.headers).get('X-Workbench')).toBe('1');
    const write = calls.find(([url]) => url === '/api/settings')?.[1];
    expect(write?.method).toBe('PUT');
    expect(new Headers(write?.headers).get('X-CSRF-Token')).toBe('session-csrf');
    expect(JSON.parse(String(write?.body))).toEqual(snapshot.settings);
    expect(calls.every(([, options]) => options?.credentials === 'same-origin')).toBe(true);
  });

  it('multipart 保留文件内容，不手工设置 boundary', async () => {
    const fetcher = server();
    const repository = new HttpWorkspaceRepository();
    const files = [new File(['first'], '一.mp4'), new File(['second'], '二.mov')];
    await repository.importFiles(files);
    await repository.importOutputs(files);
    for (const path of ['/api/materials/import', '/api/outputs/import']) {
      const options = fetcher.mock.calls.find(([url]) => url === path)?.[1];
      expect(new Headers(options?.headers).has('Content-Type')).toBe(false);
      const uploaded = (options?.body as FormData).getAll('files') as File[];
      expect(uploaded.map((file) => file.name)).toEqual(files.map((file) => file.name));
      expect(await uploaded[1]?.text()).toBe('second');
    }
  });

  it('目录、取消、重试、成片确认、发布取消、配对及撤销使用约定路径', async () => {
    const fetcher = server();
    const repository = new HttpWorkspaceRepository();
    await repository.importDirectory('/实际目录');
    await repository.commandTask('task/1', 'cancel');
    await repository.commandTask('task/1', 'retry');
    await repository.confirmOutput('out/1');
    await repository.cancelPublish('pub/1');
    await repository.createPairing();
    await repository.revokePairing('ext/1');
    expect(fetcher.mock.calls.map(([url, options]) => [url, options?.method])).toEqual([
      ['/api/session', 'POST'],
      ['/api/materials/directory', 'POST'],
      ['/api/tasks/task%2F1/command', 'POST'],
      ['/api/tasks/task%2F1/command', 'POST'],
      ['/api/outputs/out%2F1/confirm', 'POST'],
      ['/api/publish/pub%2F1/cancel', 'POST'],
      ['/api/pairing', 'POST'],
      ['/api/pairing/ext%2F1', 'DELETE'],
    ]);
    expect(JSON.parse(String(fetcher.mock.calls[1]?.[1]?.body))).toEqual({ path: '/实际目录' });
  });

  it('真实任务拒绝演示命令，不发请求', async () => {
    const fetcher = server();
    const repository = new HttpWorkspaceRepository();
    await expect(repository.commandTask('1', 'advance')).rejects.toThrow('cancel');
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('使用服务端完整片段方案，创建任务只发送 planId', async () => {
    const fetcher = server();
    const repository = new HttpWorkspaceRepository();
    const config = {
      seed: '5',
      template: 'teaching' as const,
      pool: 'all' as const,
      materialIds: ['m2', 'm1'],
    };
    const plan = {
      id: 'saved-plan',
      config,
      clips: [{ materialId: 'm2', label: '完整原片', durationSeconds: 193.5 }],
      durationSeconds: 193.5,
    };
    fetcher.mockImplementation(async (url) =>
      json(
        url === '/api/session' ? { csrfToken: 'csrf' } : url === '/api/mix/plans' ? plan : snapshot,
      ),
    );
    expect(await repository.createMixPlan(config)).toEqual(plan);
    await repository.createMixTask(plan, ['preview']);
    expect(JSON.parse(String(fetcher.mock.calls.at(-1)?.[1]?.body))).toEqual({
      planId: 'saved-plan',
      outputs: ['preview'],
    });
  });

  it('按原样提交冻结发布数据，不以入队推断平台成功', async () => {
    const fetcher = server();
    const repository = new HttpWorkspaceRepository();
    const request = {
      outputId: 'real-output',
      accountId: 'real-account',
      title: '真实标题',
      caption: '#视频',
      mode: 'direct' as const,
      confirmed: true,
    };
    const queued = {
      ...snapshot,
      receipts: [
        {
          ...request,
          id: 'job',
          simulated: false,
          status: 'queued',
          createdAt: new Date().toISOString(),
        },
      ],
    };
    fetcher.mockImplementation(async (url) =>
      json(url === '/api/session' ? { csrfToken: 'csrf' } : queued),
    );
    expect((await repository.publish(request)).receipts[0]?.status).toBe('queued');
    expect(JSON.parse(String(fetcher.mock.calls.at(-1)?.[1]?.body))).toEqual(request);
  });

  it('显示服务端 detail，不吞掉业务拒绝', async () => {
    const fetcher = server();
    const repository = new HttpWorkspaceRepository();
    await repository.load();
    fetcher.mockResolvedValueOnce(json({ detail: '账号尚未配对' }, 409));
    await expect(repository.cancelPublish('job')).rejects.toThrow('账号尚未配对');
  });

  it('CSRF 失效不重放写请求，下次显式操作重新建立 session', async () => {
    const fetcher = server();
    const repository = new HttpWorkspaceRepository();
    await repository.load();
    fetcher.mockResolvedValueOnce(json({ detail: 'CSRF invalid' }, 403));
    await expect(repository.cancelPublish('job')).rejects.toThrow('会话');
    expect(fetcher.mock.calls.filter(([url]) => url === '/api/publish/job/cancel')).toHaveLength(1);
    await repository.load();
    expect(fetcher.mock.calls.filter(([url]) => url === '/api/session')).toHaveLength(2);
  });

  it('会话建立失败后可以重新连接', async () => {
    const fetcher = server();
    fetcher.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    const repository = new HttpWorkspaceRepository();
    await expect(repository.load()).rejects.toThrow('8766');
    await expect(repository.load()).resolves.toEqual(snapshot);
  });

  it('断线写请求提示结果可能已生效且不自动重试', async () => {
    const fetcher = server();
    const repository = new HttpWorkspaceRepository();
    await repository.load();
    fetcher.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    await expect(repository.cancelPublish('job')).rejects.toThrow('可能已生效');
    expect(fetcher.mock.calls.filter(([url]) => url === '/api/publish/job/cancel')).toHaveLength(1);
  });

  it.each([new Response('', { status: 502 }), new Response('<html>Vite</html>')])(
    '非 JSON 代理响应给出本地 API 启动提示',
    async (response) => {
      const fetcher = server();
      fetcher.mockResolvedValueOnce(response);
      await expect(new HttpWorkspaceRepository().load()).rejects.toThrow('127.0.0.1:8766');
    },
  );
});
