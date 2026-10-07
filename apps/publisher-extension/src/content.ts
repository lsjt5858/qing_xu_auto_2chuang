import { DomAdapter, waitFor, type MediaFields } from './dom';
import { CHANNEL, fileSize, messageOf, record, requireThat, Stop } from './protocol';
import { ChunkReceiver } from './transfer';
import type { BridgeMessage } from './bridge';

type ContentResponse = { ok: true; value?: string | null } | { ok: false; error: string };
type InjectFile = (input: HTMLInputElement, file: File) => void;

function jobFields(value: unknown): MediaFields & { id: string } {
  const job = record(value);
  requireThat(typeof job.id === 'string' && job.id.length > 0, 'schema', '任务 id 无效');
  requireThat(typeof job.fileName === 'string' && job.fileName.length > 0, 'schema', '视频文件名无效');
  requireThat(typeof job.title === 'string' && typeof job.caption === 'string', 'schema', '任务文案无效');
  fileSize(job.sizeBytes);
  return {
    id: job.id,
    fileName: job.fileName,
    sizeBytes: job.sizeBytes,
    title: job.title,
    caption: job.caption,
  };
}

function nativeInject(input: HTMLInputElement, file: File): void {
  const transfer = new DataTransfer();
  transfer.items.add(file);
  input.files = transfer.files;
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
}

export class ContentController {
  private receiver?: ChunkReceiver;
  private job?: MediaFields & { id: string };
  private adapter: DomAdapter;
  private controller = new AbortController();

  constructor(
    private readonly doc: Document,
    private readonly href: () => string,
    private readonly extensionId: string,
    private readonly runnerUrl: string,
    private readonly inject: InjectFile = nativeInject,
  ) {
    this.adapter = new DomAdapter(doc, href);
  }

  private source(sender: chrome.runtime.MessageSender): void {
    requireThat(sender.id === this.extensionId && sender.url === this.runnerUrl,
      'source', '拒绝非 runner 的消息来源');
  }

  private current(): MediaFields & { id: string } {
    requireThat(this.job, 'state', '尚未准备发布任务');
    return this.job;
  }

  private reset(): void {
    this.controller.abort();
    this.controller = new AbortController();
    this.receiver = undefined;
    this.job = undefined;
    this.adapter = new DomAdapter(this.doc, this.href);
  }

  async handle(value: unknown, sender: chrome.runtime.MessageSender): Promise<ContentResponse> {
    try {
      this.source(sender);
      const message = record(value) as unknown as BridgeMessage;
      requireThat(message.channel === CHANNEL, 'channel', '消息通道无效');
      requireThat(typeof message.type === 'string', 'schema', '消息类型无效');
      switch (message.type) {
        case 'prepare': {
          this.reset();
          this.job = jobFields(message.job);
          this.adapter.uploadInput();
          this.receiver = new ChunkReceiver(this.job.fileName, this.job.sizeBytes);
          return { ok: true };
        }
        case 'chunk':
          requireThat(this.receiver, 'state', '尚未准备文件接收');
          requireThat(typeof message.index === 'number' && typeof message.data === 'string',
            'schema', '视频分块格式无效');
          this.receiver.add(message.index, message.data);
          return { ok: true };
        case 'upload': {
          requireThat(this.receiver, 'state', '尚未准备文件接收');
          const file = this.receiver.finish();
          const input = this.adapter.uploadInput();
          this.inject(input, file);
          this.adapter.bindFile(file, input);
          return { ok: true };
        }
        case 'ready':
          await waitFor(this.doc, () => this.adapter.ready(this.current()), 120_000, this.controller.signal);
          return { ok: true };
        case 'fill':
          await this.adapter.fill(this.current());
          return { ok: true };
        case 'verify':
          this.adapter.verify(this.current());
          return { ok: true };
        case 'click':
          this.adapter.clickOnce(this.current().id, this.current());
          return { ok: true };
        case 'evidence': {
          const evidence = await waitFor(this.doc, () => {
            const result = this.adapter.evidence();
            if (!result) throw new Stop('not_ready', '等待明确发布成功证据');
            return result;
          }, 30_000, this.controller.signal, 0);
          return { ok: true, value: evidence };
        }
        case 'cancel':
          this.reset();
          return { ok: true };
        default:
          throw new Stop('schema', '不支持的页面操作');
      }
    } catch (error) {
      return { ok: false, error: messageOf(error) };
    }
  }
}

if (typeof chrome !== 'undefined' && chrome.runtime?.onMessage) {
  const controller = new ContentController(
    document,
    () => location.href,
    chrome.runtime.id,
    chrome.runtime.getURL('runner.html'),
  );
  chrome.runtime.onMessage.addListener((message, sender, respond) => {
    if (!message || typeof message !== 'object' || message.channel !== CHANNEL) return false;
    void controller.handle(message, sender).then(respond);
    return true;
  });
}
