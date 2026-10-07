import { describe, expect, it } from 'vitest';
import { accountFields, parseJob, localOrigin, MAX_FILE_BYTES, transition } from '../src/protocol';

export const job = {
  id: 'p1', outputId: 'o1', accountId: 'a1', accountUid: '123',
  title: '冻结标题', caption: '冻结文案', mode: 'direct' as const,
  fileName: 'clip.mp4', sizeBytes: 4, leaseToken: 'lease-test',
};

describe('协议边界', () => {
  it('仅返回账号四字段', () => {
    expect(accountFields({ uid: '123', nickname: 'N', unique_id: 'H', short_id: 'S', cookie: 'no', token: 'no' }))
      .toEqual({ uid: '123', nickname: 'N', unique_id: 'H', short_id: 'S' });
  });
  it.each([{}, { uid: 123 }, { uid: '123', nickname: 'N' }])('拒绝不完整身份 %j', value => {
    expect(() => accountFields(value)).toThrow();
  });
  it('只允许端口，不接受地址和远端', () => {
    expect(localOrigin('8766')).toBe('http://127.0.0.1:8766');
    for (const value of ['https://evil.test', '8766/path', '0', '65536', '1.5', '']) {
      expect(() => localOrigin(value)).toThrow();
    }
  });
  it('512 MiB 是明确的包含边界', () => {
    expect(MAX_FILE_BYTES).toBe(512 * 1024 * 1024);
    expect(parseJob({ ...job, sizeBytes: MAX_FILE_BYTES })).toMatchObject({ sizeBytes: MAX_FILE_BYTES });
    expect(() => parseJob({ ...job, sizeBytes: MAX_FILE_BYTES + 1 })).toThrow(/512 MiB/);
  });
  it.each([
    { mode: 'retry' }, { sizeBytes: 0 }, { sizeBytes: 1.5 }, { fileName: '/private/clip.mp4' },
    { fileName: 'C:\\clip.mp4' }, { leaseToken: '' }, { title: null }, { accountUid: 123 },
  ])('拒绝非契约任务 %j', change => expect(() => parseJob({ ...job, ...change })).toThrow());
  it('去除未声明字段并冻结任务', () => {
    const result = parseJob({ ...job, localPath: '/secret', token: 'secret' });
    expect(Object.isFrozen(result)).toBe(true);
    expect(result).toEqual(job);
  });
  it('提交后不能回退、重试或无证据成功', () => {
    expect(transition('filling', 'submitting')).toBe('submitting');
    expect(transition('submitting', 'unknown')).toBe('unknown');
    expect(() => transition('submitting', 'blocked')).toThrow();
    expect(() => transition('unknown', 'submitting')).toThrow();
    expect(() => transition('filling', 'submitted')).toThrow();
    expect(() => transition('submitting', 'submitted')).toThrow();
    expect(transition('submitting', 'submitted', 'post_id=123')).toBe('submitted');
  });
});
