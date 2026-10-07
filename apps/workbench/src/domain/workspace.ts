import type {
  Material,
  MixConfig,
  MixPlan,
  Output,
  ProcessingRequest,
  ProcessingStep,
  PublishRequest,
  Scene,
  Settings,
  TaskStatus,
  WorkspaceSnapshot,
} from './types';

export const stepLabels: Record<ProcessingStep, string> = {
  clean: '视频清洗',
  scenes: '原始切镜',
  transcribe: '音频转录',
  semantic: '语义分镜',
};
export const taskLabels: Record<TaskStatus, string> = {
  queued: '排队中',
  running: '进行中',
  paused: '已暂停',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
  skipped: '已跳过',
  interrupted: '已中断',
};
export const outputLabels = { final: '已确认成片', preview: '预览 MP4', draft: '剪映草稿' };
export const materialLabels = { video: '原始视频', shot: '镜头片段', image: '作品照片' };
export const materialStatusLabels = { pending: '待处理', analyzed: '已分析', ready: '可用' };
export const demoAccount = { id: 'douyin-demo', name: '青序美甲课堂', handle: '@qingxu_demo' };

export function formatDuration(seconds: number | null): string {
  if (seconds === null) return '待分析';
  const total = Math.max(0, Math.floor(seconds));
  return [Math.floor(total / 60), total % 60]
    .map((value) => String(value).padStart(2, '0'))
    .join(':');
}

export function formatBytes(bytes: number | null): string {
  if (bytes === null) return '草稿目录';
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function formatDate(date: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(date));
}

export function normalizeSteps(steps: readonly ProcessingStep[]): ProcessingStep[] {
  const selected = new Set(steps);
  if (selected.has('semantic')) {
    selected.add('scenes');
    selected.add('transcribe');
  }
  return (Object.keys(stepLabels) as ProcessingStep[]).filter((step) => selected.has(step));
}

export function validateProcessing(
  request: ProcessingRequest,
  materials: Material[],
): ProcessingRequest {
  const materialIds = [...new Set(request.materialIds)];
  if (!materialIds.length) throw new Error('请至少选择一个视频。');
  if (
    materialIds.some(
      (id) => !materials.some((material) => material.id === id && material.kind !== 'image'),
    )
  ) {
    throw new Error('处理任务只能使用当前素材库中的视频或镜头片段。');
  }
  const steps = normalizeSteps(request.steps);
  if (!steps.length) throw new Error('请至少选择一个处理步骤。');
  if (!Number.isFinite(request.threshold) || request.threshold < 1 || request.threshold > 100) {
    throw new Error('切镜阈值必须为 1–100。');
  }
  if (request.name.trim().length > 80) throw new Error('任务名称最多 80 个字符。');
  return { ...request, materialIds, steps, name: request.name.trim() };
}

/** Stable selection also survives changes to the presentation order of materials. */
export function createMixPlan(config: MixConfig, materials: Material[]): MixPlan {
  if (!config.seed.trim() || config.seed.length > 24)
    throw new Error('请填写 1–24 个字符的随机种子。');
  const pool = materials
    .filter(
      (material) =>
        material.source === 'sample' && (config.pool !== 'shots' || material.kind === 'shot'),
    )
    .sort((a, b) => a.id.localeCompare(b.id));
  if (!pool.length) throw new Error('素材池没有可用素材，请更换素材池。');
  let seed = 2166136261;
  const fingerprint = JSON.stringify({ ...config, ids: pool.map((material) => material.id) });
  for (const char of fingerprint) seed = Math.imul(seed ^ char.charCodeAt(0), 16777619) >>> 0;
  const id = `PLAN-${seed.toString(16).toUpperCase()}`;
  const labels =
    config.template === 'teaching'
      ? ['开场', '手法示范', '细节特写', '课堂过程', '作品展示']
      : ['开场', '作品一', '作品二', '细节', '收尾'];
  const durations = config.template === 'teaching' ? [5, 9, 10, 10, 8] : [4, 5, 6, 6, 5];
  const clips = labels.map((label, index) => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    const material = pool[Math.floor((seed / 4294967296) * pool.length)]!;
    return { materialId: material.id, label, durationSeconds: durations[index]! };
  });
  return {
    id,
    config: { ...config },
    clips,
    durationSeconds: clips.reduce((sum, clip) => sum + clip.durationSeconds, 0),
  };
}

export function matchesMixConfig(plan: MixPlan, config: MixConfig): boolean {
  return (
    plan.config.seed === config.seed &&
    plan.config.pool === config.pool &&
    plan.config.template === config.template &&
    JSON.stringify(plan.config.materialIds ?? []) === JSON.stringify(config.materialIds ?? [])
  );
}

export function validatePublish(request: PublishRequest, outputs: Output[]): void {
  const output = outputs.find((item) => item.id === request.outputId);
  if (!output || output.kind === 'draft') throw new Error('请选择 MP4 成片；剪映草稿需要先导出。');
  if (request.accountId !== demoAccount.id) throw new Error('目标账号不匹配，请重新核对。');
  if (!request.confirmed) throw new Error('请先核对成片、文案和目标账号。');
  if (!request.title.trim() || request.title.length > 55) throw new Error('标题需为 1–55 个字符。');
  if (request.caption.length > 1000) throw new Error('文案最多 1000 个字符。');
}

export function validateSettings(settings: Settings): void {
  if (
    ![settings.sourceDirectory, settings.outputDirectory, settings.draftDirectory].every((value) =>
      value.trim(),
    )
  ) {
    throw new Error('请填写完整的目录设置。');
  }
}

export function getOverview(snapshot: WorkspaceSnapshot) {
  return {
    materialCount: snapshot.materials.length,
    runningCount: snapshot.tasks.filter((task) => task.status === 'running').length,
    queuedCount: snapshot.tasks.filter((task) => task.status === 'queued').length,
    sceneCount: snapshot.materials.reduce((count, material) => count + material.scenes.length, 0),
    readyOutputs: snapshot.outputs.filter(
      (output) =>
        output.kind === 'final' &&
        !snapshot.receipts.some(
          (receipt) => receipt.outputId === output.id && receipt.status !== 'cancelled',
        ),
    ),
    failures: snapshot.tasks.filter(
      (task) => task.status === 'failed' || task.status === 'interrupted',
    ),
    recentMaterials: [...snapshot.materials]
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
      .slice(0, 4),
  };
}

export function sampleScenes(duration: number, count: number): Scene[] {
  return Array.from({ length: count }, (_, index) => ({
    id: `scene-${index + 1}`,
    startSeconds: Math.round((index * duration) / count),
    durationSeconds: Math.round(duration / count),
  }));
}
