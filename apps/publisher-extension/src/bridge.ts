import { accountFields, CHANNEL, record, requireThat, Stop, type Account, type Job } from './protocol';
import { readIdentityInMain } from './identity';
import { encodedChunks } from './transfer';
import type { PageBridge } from './engine';

export interface BridgeMessage {
  channel: typeof CHANNEL;
  type: 'prepare' | 'chunk' | 'upload' | 'ready' | 'fill' | 'verify' | 'click' | 'evidence' | 'cancel';
  job?: Pick<Job, 'id' | 'fileName' | 'sizeBytes' | 'title' | 'caption'>;
  index?: number;
  data?: string;
}

export interface BridgeBoundary {
  executeIdentity(tabId: number): Promise<{ documentId: string; value: unknown }>;
  send(tabId: number, documentId: string, message: BridgeMessage): Promise<unknown>;
}

const chromeBoundary: BridgeBoundary = {
  async executeIdentity(tabId) {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      world: 'MAIN',
      func: readIdentityInMain,
    });
    requireThat(results.length === 1 && typeof results[0].documentId === 'string',
      'document', '无法固定抖音页面文档，请重新选择标签页');
    return { documentId: results[0].documentId, value: results[0].result };
  },
  send(tabId, documentId, message) {
    return chrome.tabs.sendMessage(tabId, message, { documentId });
  },
};

function fields(job: Job): NonNullable<BridgeMessage['job']> {
  return {
    id: job.id,
    fileName: job.fileName,
    sizeBytes: job.sizeBytes,
    title: job.title,
    caption: job.caption,
  };
}

export class TabBridge implements PageBridge {
  private documentId?: string;

  constructor(private readonly tabId: number, private readonly boundary: BridgeBoundary = chromeBoundary) {}

  private active(signal?: AbortSignal): void {
    if (signal?.aborted) throw new Stop('cancelled', '操作已停止');
  }

  private async send(message: BridgeMessage, signal?: AbortSignal): Promise<unknown> {
    this.active(signal);
    requireThat(this.documentId, 'document', '请先核验已登录账号');
    let result: Record<string, unknown>;
    try {
      result = record(await this.boundary.send(this.tabId, this.documentId, message));
    } catch (error) {
      if (error instanceof Stop) throw error;
      throw new Stop('bridge', '抖音页面通信失败或页面已导航，已停止');
    }
    this.active(signal);
    requireThat(result.ok === true, 'bridge', typeof result.error === 'string' ? result.error : '抖音页面拒绝操作');
    return result.value;
  }

  async identity(signal?: AbortSignal): Promise<Account> {
    this.active(signal);
    const result = await this.boundary.executeIdentity(this.tabId);
    this.active(signal);
    requireThat(result.value !== null, 'identity', '未读取到已登录抖音账号');
    if (this.documentId) {
      requireThat(this.documentId === result.documentId, 'document', '抖音页面已导航或文档已变化，已停止');
    } else {
      this.documentId = result.documentId;
    }
    return accountFields(result.value);
  }

  async prepare(job: Job, signal?: AbortSignal): Promise<void> {
    await this.send({ channel: CHANNEL, type: 'prepare', job: fields(job) }, signal);
  }

  async upload(file: Blob, _job: Job, signal?: AbortSignal): Promise<void> {
    for await (const chunk of encodedChunks(file)) {
      await this.send({ channel: CHANNEL, type: 'chunk', index: chunk.index, data: chunk.data }, signal);
    }
    await this.send({ channel: CHANNEL, type: 'upload' }, signal);
  }

  async ready(job: Job, signal?: AbortSignal): Promise<void> {
    await this.send({ channel: CHANNEL, type: 'ready', job: fields(job) }, signal);
  }

  async fill(job: Job, signal?: AbortSignal): Promise<void> {
    await this.send({ channel: CHANNEL, type: 'fill', job: fields(job) }, signal);
  }

  async verify(job: Job, signal?: AbortSignal): Promise<void> {
    await this.send({ channel: CHANNEL, type: 'verify', job: fields(job) }, signal);
  }

  async click(job: Job, signal?: AbortSignal): Promise<void> {
    await this.send({ channel: CHANNEL, type: 'click', job: fields(job) }, signal);
  }

  async evidence(_job: Job, signal?: AbortSignal): Promise<string | null> {
    const value = await this.send({ channel: CHANNEL, type: 'evidence' }, signal);
    requireThat(value === null || typeof value === 'string', 'bridge', '页面成功证据格式无效');
    return value;
  }

  cancel(): void {
    if (!this.documentId) return;
    void this.boundary.send(this.tabId, this.documentId, { channel: CHANNEL, type: 'cancel' }).catch(() => undefined);
  }
}
