import { readFileSync } from 'node:fs';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DomAdapter, type EditorProfile, waitFor } from '../src/dom';

const url = 'https://creator.douyin.com/creator-micro/content/upload';
const media = { fileName: 'clip.mp4', sizeBytes: 4, title: '标题', caption: '文案' };
// Synthetic editor model ONLY. These selectors are never shipped as Douyin selectors.
const profile: EditorProfile = {
  name: 'synthetic-test-only',
  matches: doc => Boolean(doc.querySelector('#fixture-editor')),
  title: '#title', caption: '#caption', publish: '#publish',
  uploaded: doc => doc.querySelector('#upload-state')?.textContent === 'complete'
    ? { fileName: 'clip.mp4', sizeBytes: 4 } : null,
  success: doc => doc.querySelector('#receipt')?.textContent === 'post_id=123'
    ? 'post_id=123' : null,
};
const editor = `<main id="fixture-editor"><input id="title"><textarea id="caption"></textarea>
  <span id="upload-state">complete</span><button id="publish">发布</button></main>`;

beforeEach(() => { document.body.innerHTML = ''; });

describe('保守 DOM 适配', () => {
  it('真实已知旧草稿文案必须阻断，不点击继续或放弃', () => {
    document.documentElement.innerHTML = readFileSync('tests/fixtures/upload-observed.html', 'utf8');
    const clicks = vi.fn();
    document.querySelectorAll('button').forEach(button => button.addEventListener('click', clicks));
    expect(() => new DomAdapter(document, () => url).uploadInput()).toThrow(/旧草稿/);
    expect(clicks).not.toHaveBeenCalled();
  });
  it('仅识别唯一明确视频 input', () => {
    document.body.innerHTML = '<input type=file accept="video/*">';
    expect(new DomAdapter(document, () => url).uploadInput()).toBe(document.querySelector('input'));
    document.body.insertAdjacentHTML('beforeend', '<input type=file accept=".mp4">');
    expect(() => new DomAdapter(document, () => url).uploadInput()).toThrow(/歧义/);
  });
  it('拒绝缺少 accept 的泛化 input', () => {
    document.body.innerHTML = '<input type=file>';
    expect(() => new DomAdapter(document, () => url).uploadInput()).toThrow(/未匹配/);
  });
  it.each([
    '<div>请完成安全验证</div>', '<iframe src="https://verify.example/captcha"></iframe>',
    '<textarea>已有文案</textarea>', '<div contenteditable=true>旧文案</div>',
  ])('验证码或已有内容不能上传 %s', html => {
    document.body.innerHTML = `<input type=file accept="video/*">${html}`;
    expect(() => new DomAdapter(document, () => url).uploadInput()).toThrow();
  });
  it('路由不是已核验上传页就停止', () => {
    expect(() => new DomAdapter(document, () => 'https://creator.douyin.com/unknown').uploadInput()).toThrow(/页面/);
  });
  it('上传后未知编辑页明确停止，无猜测填充或发布', async () => {
    document.body.innerHTML = editor;
    const adapter = new DomAdapter(document, () => url);
    await expect(adapter.fill(media)).rejects.toThrow(/未匹配/);
    expect((document.querySelector('#title') as HTMLInputElement).value).toBe('');
  });
  it('歧义、未完成上传、已有内容均不能填入', async () => {
    document.body.innerHTML = editor;
    const adapter = new DomAdapter(document, () => url, [profile]);
    document.querySelector('#upload-state')!.textContent = 'uploading';
    await expect(adapter.fill(media)).rejects.toThrow(/上传未完成/);
    document.querySelector('#upload-state')!.textContent = 'complete';
    document.body.insertAdjacentHTML('beforeend', '<input id=title>');
    await expect(adapter.fill(media)).rejects.toThrow(/歧义/);
    document.body.lastElementChild!.remove();
    (document.querySelector('#caption') as HTMLTextAreaElement).value = '手工输入';
    await expect(adapter.fill(media)).rejects.toThrow(/已有内容/);
  });
  it('预填读取回验；修改后不允许提交', async () => {
    document.body.innerHTML = editor;
    const adapter = new DomAdapter(document, () => url, [profile]);
    await adapter.fill(media);
    expect(adapter.verify(media)).toBeUndefined();
    (document.querySelector('#title') as HTMLInputElement).value = '被改动';
    expect(() => adapter.verify(media)).toThrow(/内容/);
  });
  it('同一任务只点击一次，只有新明确证据可成功', async () => {
    document.body.innerHTML = editor;
    const adapter = new DomAdapter(document, () => url, [profile]);
    await adapter.fill(media);
    const clicks = vi.fn();
    document.querySelector('#publish')!.addEventListener('click', clicks);
    adapter.clickOnce('job-1', media);
    expect(() => adapter.clickOnce('job-1', media)).toThrow(/重复/);
    expect(clicks).toHaveBeenCalledTimes(1);
    expect(adapter.evidence()).toBeNull();
    document.body.insertAdjacentHTML('beforeend', '<div id=receipt>post_id=123</div>');
    expect(adapter.evidence()).toBe('post_id=123');
  });
  it('提交前已存在成功提示不是本次证据', async () => {
    document.body.innerHTML = editor;
    const adapter = new DomAdapter(document, () => url, [profile]);
    await adapter.fill(media);
    document.body.insertAdjacentHTML('beforeend', '<div id=receipt>post_id=123</div>');
    expect(() => adapter.clickOnce('j', media)).toThrow(/已有成功信号/);
  });
  it('异步 SPA 挂载后再匹配', async () => {
    const pending = waitFor(document, () => new DomAdapter(document, () => url).uploadInput(), 1500);
    setTimeout(() => { document.body.innerHTML = '<input type=file accept="video/*">'; }, 10);
    await expect(pending).resolves.toBeInstanceOf(HTMLInputElement);
  });
  it('等待中出现旧草稿立即阻断', async () => {
    const pending = waitFor(document, () => new DomAdapter(document, () => url).uploadInput(), 1500);
    setTimeout(() => { document.body.innerHTML = '<p>你还有上次未发布的视频，是否继续编辑？</p>'; }, 10);
    await expect(pending).rejects.toThrow(/旧草稿/);
  });
  it('默认 profile 支持语义编辑器和 contenteditable，不要求页面显示字节数', async () => {
    document.body.innerHTML = `<input placeholder="填写作品标题，为作品获得更多流量">
      <div class="zone-container" contenteditable="true"></div>
      <video src="blob:local-video"></video><button>重新上传</button><button>发布</button>`;
    const adapter = new DomAdapter(document, () => url);
    adapter.bindFile(new File(['test'], media.fileName));
    await adapter.fill(media);
    expect(document.querySelector('[contenteditable]')!.textContent).toBe(media.caption);
    adapter.clickOnce('real-profile', media);
    expect(adapter.evidence()).toBeNull();
    document.body.insertAdjacentHTML('beforeend', '<div role="alert">发布成功</div>');
    expect(adapter.evidence()).toContain('发布成功');
  });
  it('默认 profile 无本次注入身份、上传中或双发布按钮均停止', async () => {
    document.body.innerHTML = `<input placeholder="填写作品标题"><textarea placeholder="添加作品描述"></textarea>
      <video src="blob:video"></video><button>重新上传</button><button>发布</button>`;
    const adapter = new DomAdapter(document, () => url);
    await expect(adapter.fill(media)).rejects.toThrow(/上传未完成/);
    adapter.bindFile(new File(['test'], media.fileName));
    document.body.insertAdjacentHTML('beforeend', '<div role="progressbar" aria-valuenow="50">上传中</div>');
    await expect(adapter.fill(media)).rejects.toThrow(/上传未完成/);
    document.body.lastElementChild!.remove();
    await adapter.fill(media);
    document.body.insertAdjacentHTML('beforeend', '<button>发布</button>');
    expect(() => adapter.clickOnce('double', media)).toThrow(/歧义/);
  });
  it.each(['请等待视频上传成功', '发生错误，请重新上传', '请选择/上传封面', '请先设置封面后再发布'])(
    '真实 bundle 校验提示必须停止: %s', text => {
      document.body.innerHTML = `<input type=file accept="video/*"><div role=alert>${text}</div>`;
      expect(() => new DomAdapter(document, () => url).uploadInput()).toThrow(/上传|封面/);
    },
  );
});
