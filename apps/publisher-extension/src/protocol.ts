export const MAX_FILE_BYTES = 512 * 1024 * 1024;
export const CHUNK_BYTES = 256 * 1024;
export const LEASE_MS = 45_000;
export const HEARTBEAT_MS = 10_000;
export const CREATOR_ORIGIN = 'https://creator.douyin.com';
export const UPLOAD_PATH = '/creator-micro/content/upload';
export const CHANNEL = 'jingflow-publisher-v1';

export interface Account {
  uid: string;
  nickname: string;
  unique_id: string;
  short_id: string;
}

export interface Job {
  id: string;
  outputId: string;
  accountId: string;
  accountUid: string;
  title: string;
  caption: string;
  mode: 'prefill' | 'direct';
  fileName: string;
  sizeBytes: number;
  leaseToken: string;
}

export type Status = 'queued' | 'uploading' | 'filling' | 'awaiting_confirmation'
  | 'submitting' | 'submitted' | 'unknown' | 'blocked';

export class Stop extends Error {
  constructor(public readonly code: string, message: string) {
    super(message);
    this.name = 'Stop';
  }
}

export function requireThat(condition: unknown, code: string, message: string): asserts condition {
  if (!condition) throw new Stop(code, message);
}

export function record(value: unknown): Record<string, unknown> {
  requireThat(value !== null && typeof value === 'object' && !Array.isArray(value), 'schema', '响应格式不符合契约');
  return value as Record<string, unknown>;
}

function text(value: unknown, name: string, empty = false): string {
  requireThat(typeof value === 'string' && (empty || value.trim().length > 0), 'schema', `${name} 必须是字符串`);
  return value;
}

export function accountFields(value: unknown): Account {
  const a = record(value);
  return {
    uid: text(a.uid, 'uid'),
    nickname: text(a.nickname, 'nickname', true),
    unique_id: text(a.unique_id, 'unique_id', true),
    short_id: text(a.short_id, 'short_id', true),
  };
}

export function localOrigin(port: string | number = 8766): string {
  const raw = String(port);
  requireThat(/^\d{1,5}$/.test(raw) && Number(raw) >= 1 && Number(raw) <= 65535, 'port', '只允许本机端口 1-65535');
  return `http://127.0.0.1:${Number(raw)}`;
}

export function fileSize(size: unknown): asserts size is number {
  requireThat(Number.isSafeInteger(size) && Number(size) > 0 && Number(size) <= MAX_FILE_BYTES,
    'size', '视频必须为 1 字节至 512 MiB（536870912 字节）');
}

export function parseJob(value: unknown): Readonly<Job> {
  const j = record(value);
  fileSize(j.sizeBytes);
  const fileName = text(j.fileName, 'fileName');
  requireThat(!/[/\\\x00-\x1f]/.test(fileName) && fileName !== '.' && fileName !== '..', 'filename', '文件名不得包含本地路径');
  requireThat(j.mode === 'prefill' || j.mode === 'direct', 'mode', '不支持的发布模式');
  return Object.freeze({
    id: text(j.id, 'id'), outputId: text(j.outputId, 'outputId'),
    accountId: text(j.accountId, 'accountId'), accountUid: text(j.accountUid, 'accountUid'),
    title: text(j.title, 'title', true), caption: text(j.caption, 'caption', true),
    mode: j.mode, fileName, sizeBytes: j.sizeBytes, leaseToken: text(j.leaseToken, 'leaseToken'),
  });
}

const next: Record<Status, readonly Status[]> = {
  queued: ['uploading', 'blocked'],
  uploading: ['filling', 'blocked'],
  filling: ['awaiting_confirmation', 'submitting', 'blocked'],
  awaiting_confirmation: [], submitting: ['submitted', 'unknown'],
  submitted: [], unknown: [], blocked: [],
};

export function transition(from: Status, to: Status, evidence?: string): Status {
  requireThat(next[from].includes(to), 'transition', `拒绝状态迁移 ${from} -> ${to}`);
  requireThat(to !== 'submitted' || Boolean(evidence?.trim()), 'evidence', '缺少明确发布成功证据');
  return to;
}

export function sameAccount(account: Account, uid: string): void {
  requireThat(account.uid === uid, 'uid_mismatch', '账号 UID 不匹配，已停止；请重新手动选择账号');
}

export function messageOf(error: unknown): string {
  return error instanceof Stop ? error.message : '通信、页面或存储异常；已停止，不会自动重试';
}
