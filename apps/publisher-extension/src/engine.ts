import {
  HEARTBEAT_MS,
  LEASE_MS,
  Stop,
  messageOf,
  sameAccount,
  transition,
  type Account,
  type Job,
  type Status,
} from './protocol';

interface ApiClient {
  heartbeat(account: Account, signal?: AbortSignal): Promise<void>;
  claim(accountUid: string, signal?: AbortSignal): Promise<Readonly<Job> | null>;
  renew(job: Job, signal?: AbortSignal): Promise<void>;
  event(job: Job, status: Status, message?: string, evidence?: string, signal?: AbortSignal): Promise<void>;
  file(job: Job, signal: AbortSignal): Promise<Blob>;
}

export interface PageBridge {
  identity(signal?: AbortSignal): Promise<Account>;
  prepare(job: Job, signal?: AbortSignal): Promise<void>;
  upload(file: Blob, job: Job, signal?: AbortSignal): Promise<void>;
  ready(job: Job, signal?: AbortSignal): Promise<void>;
  fill(job: Job, signal?: AbortSignal): Promise<void>;
  verify(job: Job, signal?: AbortSignal): Promise<void>;
  click(job: Job, signal?: AbortSignal): Promise<void>;
  evidence(job: Job, signal?: AbortSignal): Promise<string | null>;
  cancel(): void;
}

export interface JournalRecord {
  job: Job;
  status: Status;
  clickIssued: boolean;
  settled: boolean;
  updatedAt: number;
}

interface JournalStore {
  load(): Promise<JournalRecord[]>;
  save(records: JournalRecord[]): Promise<void>;
}

class LeaseKeeper {
  private readonly controller = new AbortController();
  private readonly pending = new Set<Promise<void>>();
  private interval?: ReturnType<typeof setInterval>;
  private deadline?: ReturnType<typeof setTimeout>;
  private expired = false;
  private failure?: unknown;
  private expire!: () => void;
  private readonly expiration = new Promise<void>(resolve => { this.expire = resolve; });

  constructor(private readonly api: ApiClient, private readonly job: Job) {
    this.armDeadline();
    this.interval = setInterval(() => this.renew(), HEARTBEAT_MS);
  }

  private armDeadline(): void {
    if (this.deadline) clearTimeout(this.deadline);
    this.deadline = setTimeout(() => {
      this.expired = true;
      this.controller.abort();
      this.expire();
    }, LEASE_MS);
  }

  private renew(): void {
    if (this.expired || this.failure) return;
    let request!: Promise<void>;
    request = this.api.renew(this.job, this.controller.signal)
      .then(() => this.armDeadline())
      .catch(error => {
        if (!this.controller.signal.aborted) this.failure = error;
      })
      .finally(() => this.pending.delete(request));
    this.pending.add(request);
  }

  async checkpoint(): Promise<void> {
    if (!this.expired && this.pending.size > 0) {
      await Promise.race([Promise.allSettled([...this.pending]), this.expiration]);
    }
    if (this.expired) throw new Stop('lease_expired', '任务租约已过期，已停止；不会自动重试');
    if (this.failure) throw new Stop('lease_renewal', '任务租约续期失败，已停止；不会自动重试');
  }

  pause(): void {
    if (this.interval) clearInterval(this.interval);
    this.interval = undefined;
  }

  stop(): void {
    this.pause();
    if (this.deadline) clearTimeout(this.deadline);
    this.deadline = undefined;
    this.controller.abort();
  }
}

export class Engine {
  private running = false;

  constructor(
    private readonly api: ApiClient,
    private readonly page: PageBridge,
    private readonly store: JournalStore,
  ) {}

  private async save(record: JournalRecord): Promise<void> {
    const records = await this.store.load();
    const index = records.findIndex(item => item.job.id === record.job.id);
    if (index >= 0) records[index] = structuredClone(record);
    else records.push(structuredClone(record));
    await this.store.save(records);
  }

  private record(job: Job, status: Status, clickIssued = false, settled = false): JournalRecord {
    return { job: structuredClone(job), status, clickIssued, settled, updatedAt: Date.now() };
  }

  private async identity(uid: string, signal: AbortSignal): Promise<Account> {
    const account = await this.page.identity(signal);
    sameAccount(account, uid);
    return account;
  }

  private async settle(
    record: JournalRecord,
    status: 'blocked' | 'unknown',
    error: unknown,
    signal?: AbortSignal,
  ): Promise<Status> {
    const message = messageOf(error);
    try {
      await this.api.event(record.job, status, message, undefined, signal);
    } catch {
      // The lease or prior state may already be terminal. Local replay prevention still wins.
    }
    await this.save({ ...record, status, settled: true, updatedAt: Date.now() });
    return status;
  }

  async recover(): Promise<void> {
    const records = await this.store.load();
    for (const record of records) {
      if (record.settled) continue;
      const status = record.status === 'submitting' || record.clickIssued ? 'unknown' : 'blocked';
      await this.settle(record, status, new Stop('recovery', '插件执行中断，已停止；不会自动重试'));
    }
  }

  async runOne(accountUid: string): Promise<Status | null> {
    if (this.running) throw new Stop('serial', '发布任务必须串行执行');
    this.running = true;
    const controller = new AbortController();
    let keeper: LeaseKeeper | undefined;
    let current: JournalRecord | undefined;
    try {
      const account = await this.identity(accountUid, controller.signal);
      await this.api.heartbeat(account, controller.signal);
      const claimed = await this.api.claim(accountUid, controller.signal);
      if (!claimed) return null;
      const job = { ...claimed };
      if ((await this.store.load()).some(item => item.job.id === job.id)) {
        throw new Stop('duplicate', '该任务已有本地执行记录，拒绝重复执行');
      }
      current = this.record(job, 'queued');
      keeper = new LeaseKeeper(this.api, job);

      await this.identity(job.accountUid, controller.signal);
      await this.page.prepare(job, controller.signal);
      const file = await this.api.file(job, controller.signal);
      transition(current.status, 'uploading');
      await this.api.event(job, 'uploading', undefined, undefined, controller.signal);
      current = { ...current, status: 'uploading', updatedAt: Date.now() };
      await this.save(current);
      await this.page.upload(file, job, controller.signal);
      await keeper.checkpoint();
      await this.page.ready(job, controller.signal);

      await this.identity(job.accountUid, controller.signal);
      transition(current.status, 'filling');
      await this.api.event(job, 'filling', undefined, undefined, controller.signal);
      current = { ...current, status: 'filling', updatedAt: Date.now() };
      await this.save(current);
      await this.page.fill(job, controller.signal);
      await this.page.verify(job, controller.signal);
      await keeper.checkpoint();

      if (job.mode === 'prefill') {
        keeper.pause();
        await keeper.checkpoint();
        transition(current.status, 'awaiting_confirmation');
        await this.api.event(job, 'awaiting_confirmation', undefined, undefined, controller.signal);
        current = { ...current, status: 'awaiting_confirmation', settled: true, updatedAt: Date.now() };
        await this.save(current);
        return current.status;
      }

      await this.identity(job.accountUid, controller.signal);
      await this.page.verify(job, controller.signal);
      transition(current.status, 'submitting');
      current = { ...current, status: 'submitting', clickIssued: false, updatedAt: Date.now() };
      await this.save(current);
      await this.api.event(job, 'submitting', undefined, undefined, controller.signal);
      current = { ...current, clickIssued: true, updatedAt: Date.now() };
      await this.save(current);
      await this.page.click(job, controller.signal);
      const evidence = await this.page.evidence(job, controller.signal);
      if (!evidence?.trim()) throw new Stop('evidence', '平台没有返回明确发布成功证据');
      keeper.pause();
      await keeper.checkpoint();
      transition(current.status, 'submitted', evidence);
      await this.api.event(job, 'submitted', undefined, evidence, controller.signal);
      current = { ...current, status: 'submitted', settled: true, updatedAt: Date.now() };
      await this.save(current);
      return current.status;
    } catch (error) {
      if (!current) throw error;
      const uncertain = current.status === 'submitting' || current.clickIssued;
      return this.settle(current, uncertain ? 'unknown' : 'blocked', error, controller.signal);
    } finally {
      keeper?.stop();
      controller.abort();
      this.page.cancel();
      this.running = false;
    }
  }
}
