import { describe, expect, it, vi } from 'vitest';
import { ContentController } from '../src/content';
import { CHANNEL } from '../src/protocol';

const sender = {
  id: 'extension-id',
  url: 'chrome-extension://extension-id/runner.html',
} as chrome.runtime.MessageSender;
const job = { id: 'j1', fileName: 'clip.mp4', sizeBytes: 4, title: '标题', caption: '文案' };

describe('content消息边界', () => {
  it('只接受本扩展runner页面', async () => {
    const controller = new ContentController(
      document, () => 'https://creator.douyin.com/creator-micro/content/upload',
      'extension-id', sender.url!, vi.fn(),
    );
    const result = await controller.handle(
      { channel: CHANNEL, type: 'prepare', job },
      { ...sender, id: 'other' },
    );
    expect(result).toEqual({ ok: false, error: expect.stringMatching(/来源/) });
  });

  it('按顺序重组完整File后才注入页面', async () => {
    document.body.innerHTML = '<input type=file accept="video/*">';
    const inject = vi.fn();
    const controller = new ContentController(
      document, () => 'https://creator.douyin.com/creator-micro/content/upload',
      'extension-id', sender.url!, inject,
    );
    expect(await controller.handle({ channel: CHANNEL, type: 'prepare', job }, sender)).toEqual({ ok: true });
    expect(await controller.handle({ channel: CHANNEL, type: 'chunk', index: 0, data: 'dGVzdA==' }, sender))
      .toEqual({ ok: true });
    expect(inject).not.toHaveBeenCalled();
    expect(await controller.handle({ channel: CHANNEL, type: 'upload' }, sender)).toEqual({ ok: true });
    const file = inject.mock.calls[0][1] as File;
    expect(file.name).toBe('clip.mp4');
    const contents = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.addEventListener('load', () => resolve(String(reader.result)));
      reader.addEventListener('error', () => reject(reader.error));
      reader.readAsText(file);
    });
    expect(contents).toBe('test');
  });
});
