// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Engine, type JournalRecord, type PageBridge } from '../src/engine';
import type { Job, Status } from '../src/protocol';
import { Stop } from '../src/protocol';

const account = { uid: 'u1', nickname: '账号', unique_id: 'name', short_id: 'short' };
const job: Job = { id: 'j1', outputId: 'o1', accountId: 'a1', accountUid: 'u1',
  mode: 'direct', fileName: 'clip.mp4', sizeBytes: 4, title: '标题', caption: '文案', leaseToken: 'lease' };

function setup(mode: Job['mode'] = 'direct') {
  const trace: string[] = [];
  let saved: JournalRecord[] = [];
  const api = {
    heartbeat: vi.fn(async (a: typeof account) => { expect(a).toEqual(account); trace.push('heartbeat'); }),
    claim: vi.fn(async () => { trace.push('claim'); return { ...job, mode }; }),
    renew: vi.fn(async () => { trace.push('renew'); }),
    event: vi.fn(async (_: Job, status: Status) => { trace.push(`api:${status}`); }),
    file: vi.fn(async () => new Blob(['test'])),
  };
  const page: PageBridge = {
    identity: vi.fn(async () => account), prepare: vi.fn(async () => {}),
    upload: vi.fn(async () => {}), ready: vi.fn(async () => {}),
    fill: vi.fn(async () => {}), verify: vi.fn(async () => {}),
    click: vi.fn(async () => { trace.push('click'); }), evidence: vi.fn(async () => '发布成功'),
    cancel: vi.fn(),
  };
  const store = {
    load: async () => structuredClone(saved),
    save: async (rows: JournalRecord[]) => {
      saved = structuredClone(rows);
      trace.push(`save:${rows.at(-1)?.status}:${rows.at(-1)?.clickIssued}`);
    },
  };
  const engine = new Engine(api, page, store);
  return { api, page, store, engine, trace, rows: () => saved };
}

afterEach(() => vi.useRealTimers());

describe('发布状态机', () => {
  it('claim前带account心跳，显式uploading，提交日志和API均先于单次click', async () => {
    const s = setup();
    expect(await s.engine.runOne('u1')).toBe('submitted');
    expect(s.trace.indexOf('heartbeat')).toBeLessThan(s.trace.indexOf('claim'));
    expect(s.trace).toContain('api:uploading');
    expect(s.trace.indexOf('save:submitting:false')).toBeLessThan(s.trace.indexOf('api:submitting'));
    expect(s.trace.indexOf('api:submitting')).toBeLessThan(s.trace.indexOf('save:submitting:true'));
    expect(s.trace.indexOf('save:submitting:true')).toBeLessThan(s.trace.indexOf('click'));
    expect(s.rows()[0].status).toBe('submitted');
    expect(s.page.identity).toHaveBeenCalledTimes(4);
    await expect(s.engine.runOne('u1')).rejects.toThrow(/重复/);
    expect(s.page.click).toHaveBeenCalledTimes(1);
  });
  it('prefill只能到awaiting_confirmation，绝不submitting', async () => {
    const s = setup('prefill');
    expect(await s.engine.runOne('u1')).toBe('awaiting_confirmation');
    expect(s.trace).not.toContain('api:submitting');
    expect(s.page.click).not.toHaveBeenCalled();
  });
  it('上传前UID变化，或claim账号错误，均blocked且不上传', async () => {
    const s = setup();
    vi.mocked(s.page.identity).mockResolvedValueOnce(account).mockResolvedValue({ ...account, uid: 'other' });
    expect(await s.engine.runOne('u1')).toBe('blocked');
    expect(s.page.upload).not.toHaveBeenCalled();
    const t = setup();
    t.api.claim.mockResolvedValue({ ...job, accountUid: 'other' });
    expect(await t.engine.runOne('u1')).toBe('blocked');
    expect(t.page.upload).not.toHaveBeenCalled();
  });
  it.each(['旧草稿', '选择器歧义', '上传未完成'])('%s 阻断不会click', async message => {
    const s = setup();
    vi.mocked(s.page.ready).mockRejectedValue(new Stop('guard', message));
    expect(await s.engine.runOne('u1')).toBe('blocked');
    expect(s.page.click).not.toHaveBeenCalled();
  });
  it('submitting接口断线不能点击且unknown，无自动重试', async () => {
    const s = setup();
    s.api.event.mockImplementation(async (_, status) => { if (status === 'submitting') throw Error('offline'); });
    expect(await s.engine.runOne('u1')).toBe('unknown');
    expect(s.page.click).not.toHaveBeenCalled();
    expect(s.rows()[0].status).toBe('unknown');
  });
  it.each([null, 'disconnect'])('click后无证据或导航断线必须unknown: %s', async failure => {
    const s = setup();
    if (failure) vi.mocked(s.page.evidence).mockRejectedValue(Error(failure));
    else vi.mocked(s.page.evidence).mockResolvedValue(null);
    expect(await s.engine.runOne('u1')).toBe('unknown');
    expect(s.page.click).toHaveBeenCalledTimes(1);
    expect(s.rows()[0].status).toBe('unknown');
  });
  it('reload恢复submitting只报告unknown一次，不重放任务', async () => {
    const s = setup();
    await s.store.save([{ job, status: 'submitting', clickIssued: true, settled: false, updatedAt: 1 }]);
    await s.engine.recover();
    await s.engine.recover();
    expect(s.api.event).toHaveBeenCalledTimes(1);
    expect(s.page.click).not.toHaveBeenCalled();
    expect(s.rows()[0].status).toBe('unknown');
  });
  it('拒绝并发runOne，终态前排空在途续租，心跳始终携带身份', async () => {
    vi.useFakeTimers();
    const s = setup();
    let finishUpload!: () => void;
    let finishRenew!: () => void;
    vi.mocked(s.page.upload).mockImplementation(() => new Promise<void>(r => { finishUpload = r; }));
    s.api.renew.mockImplementation(() => new Promise<void>(r => { finishRenew = r; }));
    const result = s.engine.runOne('u1');
    await vi.advanceTimersByTimeAsync(10_001);
    await expect(s.engine.runOne('u1')).rejects.toThrow(/串行/);
    finishUpload();
    await vi.advanceTimersByTimeAsync(1);
    expect(s.trace).not.toContain('api:submitted');
    finishRenew();
    await expect(result).resolves.toBe('submitted');
    const count = s.api.renew.mock.calls.length;
    await vi.advanceTimersByTimeAsync(60_000);
    expect(s.api.renew).toHaveBeenCalledTimes(count);
  });
  it('租约过期后异步上传返回也不能继续填写', async () => {
    vi.useFakeTimers();
    const s = setup();
    let finishUpload!: () => void;
    vi.mocked(s.page.upload).mockImplementation(() => new Promise<void>(r => { finishUpload = r; }));
    s.api.renew.mockImplementation(() => new Promise<void>(() => {}));
    const result = s.engine.runOne('u1');
    await vi.advanceTimersByTimeAsync(46_000);
    finishUpload();
    // A real API renew has a 15s timeout; draining is intentionally bounded by the abort signal.
    await expect(result).resolves.toBe('blocked');
    expect(s.page.fill).not.toHaveBeenCalled();
  });
});
