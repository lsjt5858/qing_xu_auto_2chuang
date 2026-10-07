import { CREATOR_ORIGIN, UPLOAD_PATH, Stop, requireThat } from './protocol';

export interface MediaFields { fileName: string; sizeBytes: number; title: string; caption: string }

export interface EditorProfile {
  name: string;
  matches(doc: Document): boolean;
  title: string;
  caption: string;
  publish: string;
  uploaded(doc: Document, file?: File): { fileName: string; sizeBytes: number } | null;
  success(doc: Document): string | null;
}

const TITLE = 'input[placeholder*="填写作品标题"]';
const CAPTION = 'div.zone-container[contenteditable="true"], [contenteditable="true"][data-placeholder*="作品描述"], textarea[placeholder*="作品描述"]';
const exactText = (doc: Document, selector: string, pattern: RegExp) =>
  Array.from(doc.querySelectorAll(selector)).filter(el => visible(el) && pattern.test(el.textContent?.trim() ?? ''));

// Public-source selectors, NOT claimed as a live-tested editor. All signals must agree.
const SEMANTIC_EDITOR: EditorProfile = {
  name: 'douyin-semantic-v1',
  matches: doc => Boolean(doc.querySelector(TITLE) && doc.querySelector(CAPTION)),
  title: TITLE, caption: CAPTION, publish: 'button',
  uploaded: (doc, file) => {
    if (!file) return null;
    if (exactText(doc, 'span, div, p, button', /^(上传中.*|正在上传.*|.*上传失败.*|.*转码中.*)$/).length) return null;
    if (Array.from(doc.querySelectorAll('[role="progressbar"]')).some(el =>
      visible(el) && (!el.hasAttribute('aria-valuenow') || Number(el.getAttribute('aria-valuenow')) < 100))) return null;
    const videos = Array.from(doc.querySelectorAll('video')).filter(el => visible(el) && (el.currentSrc || el.getAttribute('src')));
    const complete = exactText(doc, 'span, div, p, button', /^(重新上传|上传成功|上传完成)$/);
    return videos.length === 1 && complete.length > 0 ? { fileName: file.name, sizeBytes: file.size } : null;
  },
  success: doc => {
    const matches = exactText(doc, '[role="alert"], [role="status"], [class*="message"], [class*="success"]', /^(发布成功|作品发布成功)[！!。]?$/);
    return matches.length > 0 ? `douyin-semantic-v1: ${matches[0].textContent!.trim()}` : null;
  },
};

export function visible(element: Element): boolean {
  for (let node: Element | null = element; node; node = node.parentElement) {
    const style = node.ownerDocument.defaultView?.getComputedStyle(node);
    if (node.hasAttribute('hidden') || node.getAttribute('aria-hidden') === 'true'
      || style?.display === 'none' || style?.visibility === 'hidden') return false;
  }
  return true;
}

export class DomAdapter {
  private clicked = new Set<string>();
  private submittedProfile?: EditorProfile;
  private file?: File;
  private input?: HTMLInputElement;
  private preview?: string;
  constructor(private readonly doc: Document, private readonly href: () => string,
    private readonly profiles: readonly EditorProfile[] = [SEMANTIC_EDITOR]) {}

  bindFile(file: File, input?: HTMLInputElement): void {
    requireThat(!this.file, 'duplicate', '该页面已注入文件，禁止重复上传');
    this.file = file;
    this.input = input;
  }

  guard(): void {
    const url = new URL(this.href());
    requireThat(url.origin === CREATOR_ORIGIN && url.pathname.startsWith('/creator-micro/'), 'page', '不是支持的抖音创作者页面');
    const editorFields = new Set<Element>();
    for (const profile of this.profiles) {
      for (const selector of [profile.title, profile.caption]) {
        try {
          this.doc.querySelectorAll(selector).forEach(element => editorFields.add(element));
        } catch {
          // Invalid profiles are rejected later by normal selector matching.
        }
      }
    }
    const belongsToEditor = (element: Element) =>
      Array.from(editorFields).some(field => field === element || field.contains(element));
    const text = Array.from(this.doc.querySelectorAll('body *'))
      .filter(el => !belongsToEditor(el) && !['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(el.tagName) && visible(el))
      .map(el => Array.from(el.childNodes).filter(node => node.nodeType === 3).map(node => node.textContent).join(''))
      .join(' ').replace(/\s+/g, '');
    requireThat(!/你还有上次未发布的视频|是否继续编辑|继续编辑上次|恢复草稿/.test(text),
      'old_draft', '检测到旧草稿，已停止；不会继续、放弃或覆盖');
    requireThat(!/安全验证|请完成验证|拖动滑块|验证码|扫码登录|登录后发布/.test(text),
      'verification', '检测到验证码或登录提示，请人工处理后重新核验');
    requireThat(!/请等待视频上传成功|发生错误，请重新上传|请选择\/?上传封面|请先设置封面后再发布/.test(text),
      'upload_guard', '检测到上传或封面校验提示，已停止');
    for (const el of this.doc.querySelectorAll('iframe, [id], [class]')) {
      if (!visible(el)) continue;
      const marker = `${el.id} ${el.getAttribute('class')} ${el.getAttribute('src')}`;
      requireThat(!/captcha|verify[-_]?code|secsdk[-_]?captcha/i.test(marker),
        'verification', '检测到验证控件，已停止');
    }
    requireThat(!Array.from(this.doc.querySelectorAll('[role=dialog], dialog[open], [aria-modal=true]')).some(visible),
      'dialog', '页面存在弹窗，无法安全继续');
  }

  private noExistingContent(except: Element[] = []): void {
    const fields = this.doc.querySelectorAll('textarea, input:not([type=file]):not([type=hidden]), [contenteditable]');
    for (const el of fields) {
      if (except.includes(el) || !visible(el)) continue;
      if (el instanceof HTMLInputElement && ['button', 'submit', 'checkbox', 'radio'].includes(el.type)) continue;
      const value = el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement ? el.value : el.textContent;
      requireThat(!value?.trim(), 'existing_content', '页面已有内容，禁止覆盖；请人工准备空白上传页');
    }
  }

  uploadInput(): HTMLInputElement {
    this.guard();
    const url = new URL(this.href());
    requireThat(url.pathname === UPLOAD_PATH && !url.search && !url.hash, 'page', '仅支持已核验的空白视频上传页面');
    this.noExistingContent();
    requireThat(!Array.from(this.doc.querySelectorAll('video')).some(el => el.currentSrc || el.getAttribute('src')),
      'existing_content', '页面已有视频，禁止覆盖');
    const candidates = Array.from(this.doc.querySelectorAll<HTMLInputElement>('input[type=file]')).filter(el => {
      const accepted = el.accept.toLowerCase().split(',').map(s => s.trim());
      return accepted.some(s => s.startsWith('video/') || ['.mp4', '.mov', '.webm', '.m4v'].includes(s));
    });
    requireThat(candidates.length > 0, 'not_ready', '未匹配已知视频上传 input，页面未就绪或不支持');
    requireThat(candidates.length === 1, 'ambiguous', '视频上传选择器歧义，已停止');
    const input = candidates[0];
    requireThat(!input.disabled && !input.files?.length, 'existing_content', '上传控件不可用或已有文件，禁止覆盖');
    return input;
  }

  private profile(): EditorProfile {
    this.guard();
    const profiles = this.profiles.filter(p => p.matches(this.doc));
    requireThat(profiles.length > 0, 'not_ready', '未匹配支持的编辑页面，不能猜测填写');
    requireThat(profiles.length === 1, 'ambiguous', '编辑页面 profile 歧义');
    return profiles[0];
  }

  private one(selector: string, publish = false): Element {
    const elements = Array.from(this.doc.querySelectorAll(selector)).filter(el => visible(el)
      && (!publish || el.textContent?.trim() === '发布'));
    requireThat(elements.length > 0, 'not_ready', '编辑控件尚未就绪');
    requireThat(elements.length === 1, 'ambiguous', '编辑选择器歧义，已停止');
    requireThat(elements[0].isConnected, 'page', '编辑控件已失效');
    return elements[0];
  }

  private field(selector: string): HTMLElement {
    const el = this.one(selector);
    requireThat(el instanceof HTMLTextAreaElement || (el instanceof HTMLInputElement && ['text', ''].includes(el.type))
      || (el instanceof HTMLElement && el.getAttribute('contenteditable') === 'true'),
      'editor_type', '未核验的编辑控件类型');
    requireThat(!('disabled' in el && el.disabled) && !('readOnly' in el && el.readOnly), 'disabled', '编辑控件不可用');
    return el as HTMLElement;
  }

  private uploaded(p: EditorProfile, media: MediaFields): void {
    if (this.input?.isConnected) requireThat(this.input.files?.[0] === this.file, 'file_changed', '文件选择已被修改');
    const uploaded = p.uploaded(this.doc, this.file);
    requireThat(uploaded && uploaded.fileName === media.fileName && uploaded.sizeBytes === media.sizeBytes,
      'upload_pending', '上传未完成或文件身份无法核验，已停止');
    if (p === SEMANTIC_EDITOR) {
      const video = Array.from(this.doc.querySelectorAll('video')).find(visible)!;
      const src = video.currentSrc || video.getAttribute('src')!;
      requireThat(!this.preview || this.preview === src, 'file_changed', '视频预览已被替换，已停止');
      this.preview = src;
    }
  }

  ready(media: MediaFields): void {
    this.uploaded(this.profile(), media);
  }

  private value(el: HTMLElement): string {
    return el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement ? el.value : el.textContent ?? '';
  }

  private normalizedValue(el: HTMLElement): string {
    return this.value(el).replace(/\u200b/g, '');
  }

  async fill(media: MediaFields): Promise<void> {
    const p = this.profile();
    this.uploaded(p, media);
    const title = this.field(p.title);
    const caption = this.field(p.caption);
    requireThat(title !== caption, 'ambiguous', '标题和文案匹配到相同控件');
    requireThat(
      this.normalizedValue(title).trim() === '' && this.normalizedValue(caption).trim() === '',
      'existing_content', '标题或作品简介已有内容，禁止覆盖',
    );
    for (const [el, value] of [[title, media.title], [caption, media.caption]] as const) {
      const max = el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement ? el.maxLength : -1;
      requireThat(max < 0 || value.length <= max, 'length', '冻结内容超过页面字数限制，不会截断');
    }
    for (const [el, value] of [[title, media.title], [caption, media.caption]] as const) {
      this.guard();
      requireThat(
        el.isConnected && this.normalizedValue(el).trim() === '',
        'existing_content', '填写期间标题或作品简介出现已有内容，已停止',
      );
      if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) {
        const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto, 'value')!.set!.call(el, value);
      } else {
        el.focus();
        const range = this.doc.createRange();
        range.selectNodeContents(el);
        const selection = this.doc.getSelection();
        selection?.removeAllRanges();
        selection?.addRange(range);
        if (!this.doc.execCommand?.('insertText', false, value)) el.textContent = value;
      }
      el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: value }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }
    await waitFor(this.doc, () => this.verify(media), 3000, undefined, 0);
  }

  verify(media: MediaFields): void {
    const p = this.profile();
    this.uploaded(p, media);
    const title = this.field(p.title);
    const caption = this.field(p.caption);
    requireThat(
      this.normalizedValue(title) === media.title
        && this.normalizedValue(caption) === media.caption,
      'content_mismatch', '页面内容与冻结任务不一致',
    );
    const button = this.one(p.publish, true);
    requireThat(button instanceof HTMLButtonElement && !button.disabled && button.getAttribute('aria-disabled') !== 'true',
      'disabled', '发布按钮不可用或控件类型未核验');
  }

  clickOnce(id: string, media: MediaFields): void {
    requireThat(!this.clicked.has(id), 'duplicate', '拒绝重复点击发布');
    this.verify(media);
    const p = this.profile();
    requireThat(p.success(this.doc) === null, 'stale_success', '页面已有成功信号，无法归属本次任务');
    const button = this.one(p.publish, true) as HTMLButtonElement;
    this.clicked.add(id);
    this.submittedProfile = p;
    button.click();
  }

  evidence(): string | null {
    this.guard();
    return this.submittedProfile?.success(this.doc) ?? null;
  }
}

export function waitFor<T>(doc: Document, inspect: () => T, timeout = 5000, signal?: AbortSignal,
  stableMilliseconds = 350): Promise<T> {
  return new Promise((resolve, reject) => {
    let stableAt = 0;
    let settled = false;
    const start = Date.now();
    const observer = new MutationObserver(() => { stableAt = 0; check(); });
    const finish = (error?: unknown, value?: T) => {
      if (settled) return;
      settled = true;
      observer.disconnect();
      clearInterval(timer);
      signal?.removeEventListener('abort', abort);
      if (error) reject(error); else resolve(value as T);
    };
    const abort = () => finish(new Stop('cancelled', '操作已停止'));
    const check = () => {
      if (signal?.aborted) return abort();
      try {
        const value = inspect();
        if (stableMilliseconds === 0) return finish(undefined, value);
        if (!stableAt) stableAt = Date.now();
        if (Date.now() - stableAt >= stableMilliseconds) return finish(undefined, value);
      } catch (error) {
        stableAt = 0;
        if (!(error instanceof Stop) || !['not_ready', 'upload_pending'].includes(error.code)) return finish(error);
      }
      if (Date.now() - start >= timeout) finish(new Stop('timeout', '页面就绪或上传状态等待超时，已停止'));
    };
    const timer = setInterval(check, 75);
    observer.observe(doc.documentElement, { subtree: true, childList: true, attributes: true, characterData: true });
    signal?.addEventListener('abort', abort, { once: true });
    check();
  });
}
