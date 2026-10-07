// @vitest-environment node
import { describe, expect, it, vi } from 'vitest';
import { TabBridge, type BridgeBoundary } from '../src/bridge';
import type { Job } from '../src/protocol';

const account = { uid: 'u1', nickname: '账号', unique_id: 'name', short_id: 'short' };
const job: Job = {
  id: 'j1', outputId: 'o1', accountId: 'a1', accountUid: 'u1',
  mode: 'direct', fileName: 'clip.mp4', sizeBytes: 4,
  title: '标题', caption: '文案', leaseToken: 'secret-lease',
};

function setup() {
  const boundary: BridgeBoundary = {
    executeIdentity: vi.fn(async () => ({ documentId: 'document-1', value: account })),
    send: vi.fn(async () => ({ ok: true })),
  };
  return { boundary, bridge: new TabBridge(7, boundary) };
}

describe('固定页面消息桥', () => {
  it('首次身份读取冻结documentId，页面导航后立即停止', async () => {
    const { boundary, bridge } = setup();
    await expect(bridge.identity()).resolves.toEqual(account);
    vi.mocked(boundary.executeIdentity).mockResolvedValue({ documentId: 'document-2', value: account });
    await expect(bridge.identity()).rejects.toThrow(/导航|文档/);
  });

  it('任务消息固定发送到已核验文档，且不泄露租约或本地token', async () => {
    const { boundary, bridge } = setup();
    await bridge.identity();
    await bridge.prepare(job);
    await bridge.upload(new Blob(['test']), job);
    await bridge.ready(job);
    await bridge.fill(job);
    await bridge.verify(job);
    await bridge.click(job);
    vi.mocked(boundary.send).mockResolvedValueOnce({ ok: true, value: '发布成功' });
    await expect(bridge.evidence(job)).resolves.toBe('发布成功');

    for (const call of vi.mocked(boundary.send).mock.calls) {
      expect(call[0]).toBe(7);
      expect(call[1]).toBe('document-1');
      expect(JSON.stringify(call[2])).not.toContain(job.leaseToken);
      expect(JSON.stringify(call[2])).not.toContain('token');
    }
  });
});
