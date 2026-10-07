import type {
  MixPlan,
  OutputKind,
  ProcessingRequest,
  PublishRequest,
  Settings,
  Task,
  TaskCommand,
  WorkspaceRepository,
  WorkspaceSnapshot,
} from '../domain/types';
import {
  sampleScenes,
  validateProcessing,
  validatePublish,
  validateSettings,
} from '../domain/workspace';
import { createInitialSnapshot } from './fixtures';

/** Explicit in-memory implementation: no uploads, disk writes or fake HTTP endpoints. */
export class DemoWorkspaceRepository implements WorkspaceRepository {
  readonly mode = 'demo' as const;
  private snapshot: WorkspaceSnapshot;
  private sequence = 1027;

  constructor(initial = createInitialSnapshot()) {
    this.snapshot = structuredClone(initial);
  }

  async load(): Promise<WorkspaceSnapshot> {
    return structuredClone(this.snapshot);
  }

  async importFiles(files: File[]): Promise<WorkspaceSnapshot> {
    if (!files.length) throw new Error('请选择本地视频文件。');
    if (files.some((file) => !/\.(mp4|mov|mkv|webm)$/i.test(file.name) || file.size === 0)) {
      throw new Error('请选择非空的 MP4、MOV、MKV 或 WebM 视频。');
    }
    const now = new Date().toISOString();
    const imported = files.map((file) => ({
      id: `local-${crypto.randomUUID()}`,
      name: file.name,
      kind: 'video' as const,
      category: '本地视频',
      tone: 0 as const,
      durationSeconds: null,
      sizeBytes: file.size,
      createdAt: now,
      status: 'pending' as const,
      scenes: [],
      transcript: [],
      source: 'local' as const,
    }));
    this.snapshot.materials.unshift(...imported);
    return this.load();
  }

  async createTasks(request: ProcessingRequest): Promise<WorkspaceSnapshot> {
    const validated = validateProcessing(request, this.snapshot.materials);
    const now = new Date().toISOString();
    const created: Task[] = validated.materialIds.map((id, index) => {
      const material = this.snapshot.materials.find((item) => item.id === id)!;
      return {
        id: `JF-${this.sequence++}`,
        name: validated.name
          ? `${validated.name}${validated.materialIds.length > 1 ? ` · ${index + 1}` : ''}`
          : material.name,
        kind: 'analysis',
        status: 'queued',
        progress: 0,
        stage: '等待开始演示',
        createdAt: now,
        materialIds: [id],
        steps: validated.steps,
        threshold: validated.threshold,
        requestedOutputs: [],
        outputIds: [],
        events: [{ at: now, message: '已加入演示队列' }],
      };
    });
    this.snapshot.tasks.unshift(...created);
    return this.load();
  }

  async commandTask(id: string, command: TaskCommand): Promise<WorkspaceSnapshot> {
    const task = this.snapshot.tasks.find((item) => item.id === id);
    if (!task) throw new Error('任务不存在，请刷新列表。');
    const expected = {
      start: 'queued',
      pause: 'running',
      resume: 'paused',
      retry: 'failed',
      advance: 'running',
      cancel: 'unsupported',
    };
    if (task.status !== expected[command]) throw new Error('任务状态已变化，请刷新后再试。');
    if (command === 'pause') {
      task.status = 'paused';
      task.stage = '演示已暂停';
    } else if (command === 'retry') {
      task.status = 'queued';
      task.stage = '已重新加入演示队列';
      task.progress = 0;
      delete task.error;
    } else if (command === 'start' || command === 'resume') {
      task.status = 'running';
      task.stage = '处理中（演示）';
    } else {
      task.progress = Math.min(100, (task.progress ?? 0) + 25);
      task.stage = '生成结果（演示）';
      if (task.progress === 100) {
        task.status = 'completed';
        task.stage = '演示完成';
        this.completeTask(task);
      }
    }
    task.events.push({ at: new Date().toISOString(), message: task.stage });
    return this.load();
  }

  private completeTask(task: Task) {
    if (task.kind === 'mix' && task.plan) {
      for (const kind of task.requestedOutputs) {
        const id = `output-${crypto.randomUUID()}`;
        this.snapshot.outputs.unshift({
          id,
          taskId: task.id,
          name: `${task.name} · ${kind === 'preview' ? '预览' : '草稿'}`,
          kind,
          materialId: task.plan.clips[0]!.materialId,
          durationSeconds: task.plan.durationSeconds,
          sizeBytes: null,
          title: task.name.slice(0, 55),
          caption: '',
        });
        task.outputIds.push(id);
      }
      return;
    }
    for (const id of task.materialIds) {
      const material = this.snapshot.materials.find((item) => item.id === id);
      if (!material || material.source === 'local') continue; // Never fabricate analysis of a real user file.
      if (task.steps.includes('scenes') && !material.scenes.length) {
        material.scenes = sampleScenes(material.durationSeconds ?? 60, 8);
      }
      if (task.steps.includes('transcribe') && !material.transcript.length) {
        material.transcript = [{ startSeconds: 0, text: '这里是完成任务后展示的转录示例。' }];
      }
      material.status = 'analyzed';
    }
  }

  async createMixTask(
    plan: MixPlan,
    outputs: Exclude<OutputKind, 'final'>[],
  ): Promise<WorkspaceSnapshot> {
    if (!outputs.length) throw new Error('请选择至少一种输出内容。');
    if (
      !plan.clips.length ||
      plan.clips.some(
        (clip) => !this.snapshot.materials.some((material) => material.id === clip.materialId),
      )
    ) {
      throw new Error('选片素材已不可用，请重新生成方案。');
    }
    if (
      plan.clips.some((clip) => !Number.isFinite(clip.durationSeconds) || clip.durationSeconds <= 0)
    ) {
      throw new Error('选片时长无效，请重新生成方案。');
    }
    const now = new Date().toISOString();
    this.snapshot.tasks.unshift({
      id: `JF-${this.sequence++}`,
      name: `美甲教学 · 混剪 ${plan.id.slice(-6)}`,
      kind: 'mix',
      status: 'queued',
      progress: 0,
      stage: '固定选片，等待合成演示',
      createdAt: now,
      materialIds: [...new Set(plan.clips.map((clip) => clip.materialId))],
      steps: [],
      plan: structuredClone(plan),
      requestedOutputs: [...new Set(outputs)],
      outputIds: [],
      events: [{ at: now, message: `已固定选片方案 ${plan.id}` }],
    });
    return this.load();
  }

  async publish(request: PublishRequest): Promise<WorkspaceSnapshot> {
    validatePublish(request, this.snapshot.outputs);
    const { confirmed: _confirmed, ...content } = request;
    void _confirmed;
    this.snapshot.receipts.unshift({
      ...content,
      id: `PUB-DEMO-${crypto.randomUUID().slice(0, 8).toUpperCase()}`,
      title: content.title.trim(),
      createdAt: new Date().toISOString(),
      status: request.mode === 'prefill' ? 'awaiting_confirmation' : 'submitted',
      simulated: true,
    });
    return this.load();
  }

  async saveSettings(settings: Settings): Promise<WorkspaceSnapshot> {
    validateSettings(settings);
    this.snapshot.settings = structuredClone(settings);
    return this.load();
  }
}
