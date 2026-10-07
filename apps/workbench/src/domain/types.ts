/** Shared shapes from docs/WORKBENCH_API.md; demo-only fields remain compatible. */
export type MaterialKind = 'video' | 'shot' | 'image';
export type MaterialStatus = 'pending' | 'analyzed' | 'ready';
export type TaskStatus =
  | 'queued'
  | 'running'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'skipped'
  | 'interrupted';
export type ProcessingStep = 'clean' | 'scenes' | 'transcribe' | 'semantic';
export type OutputKind = 'final' | 'preview' | 'draft';
export type PublishMode = 'prefill' | 'direct';

export interface Scene {
  id: string;
  startSeconds: number;
  durationSeconds: number;
}

export interface TranscriptSegment {
  startSeconds: number;
  text: string;
}

export interface Material {
  id: string;
  name: string;
  kind: MaterialKind;
  category: string;
  tone: 0 | 1 | 2 | 3;
  durationSeconds: number | null;
  sizeBytes: number;
  createdAt: string;
  status: MaterialStatus;
  scenes: Scene[];
  transcript: TranscriptSegment[];
  source: 'sample' | 'local';
  fileUrl?: string;
}

export interface TaskEvent {
  at: string;
  message: string;
}

export interface ProcessingRequest {
  materialIds: string[];
  name: string;
  steps: ProcessingStep[];
  threshold: number;
}

export interface MixConfig {
  seed: string;
  template: 'teaching' | 'showcase';
  pool: 'all' | 'shots';
  materialIds?: string[];
}

export interface MixClip {
  materialId: string;
  label: string;
  durationSeconds: number;
}

export interface MixPlan {
  id: string;
  config: MixConfig;
  clips: MixClip[];
  durationSeconds: number;
}

export interface Task {
  id: string;
  name: string;
  kind: 'analysis' | 'mix';
  status: TaskStatus;
  progress: number | null;
  stage: string;
  createdAt: string;
  materialIds: string[];
  steps: ProcessingStep[];
  threshold?: number;
  plan?: MixPlan;
  requestedOutputs: Exclude<OutputKind, 'final'>[];
  outputIds: string[];
  error?: string;
  events: TaskEvent[];
}

export interface Output {
  id: string;
  taskId: string;
  name: string;
  kind: OutputKind;
  materialId: string;
  durationSeconds: number;
  sizeBytes: number | null;
  title: string;
  caption: string;
  fileUrl?: string;
  width?: number;
  height?: number;
}

export interface PublishRequest {
  outputId: string;
  accountId: string;
  title: string;
  caption: string;
  mode: PublishMode;
  confirmed: boolean;
}

export interface PublishReceipt extends Omit<PublishRequest, 'confirmed'> {
  id: string;
  createdAt: string;
  status:
    | 'awaiting_confirmation'
    | 'submitted'
    | 'queued'
    | 'uploading'
    | 'filling'
    | 'submitting'
    | 'blocked'
    | 'unknown'
    | 'cancelled';
  simulated: boolean;
  accountName?: string;
  message?: string;
  updatedAt?: string;
  evidence?: string;
}

export interface Account {
  id: string;
  platform: 'douyin';
  uid: string;
  name: string;
  handle: string;
  extensionId: string;
  connected: boolean;
  lastSeenAt: string;
}

export interface ServiceInfo {
  mode: 'live';
  version: string;
  dependencies: { name: string; available: boolean; detail: string }[];
  extensions: { id: string; name: string; lastSeenAt: string; connected: boolean }[];
}

export interface PairingCode {
  code: string;
  expiresAt: string;
}

export interface Settings {
  sourceDirectory: string;
  outputDirectory: string;
  draftDirectory: string;
  transcriptionModel: 'tiny' | 'base' | 'small' | 'medium';
  reuseAnalysis: boolean;
  preserveLongShots: boolean;
}

export interface WorkspaceSnapshot {
  materials: Material[];
  tasks: Task[];
  outputs: Output[];
  receipts: PublishReceipt[];
  settings: Settings;
  accounts?: Account[];
  service?: ServiceInfo;
}

export type TaskCommand = 'start' | 'pause' | 'resume' | 'retry' | 'advance' | 'cancel';

export interface WorkspaceRepository {
  readonly mode: 'demo' | 'live';
  load(): Promise<WorkspaceSnapshot>;
  importFiles(files: File[]): Promise<WorkspaceSnapshot>;
  createTasks(request: ProcessingRequest): Promise<WorkspaceSnapshot>;
  commandTask(id: string, command: TaskCommand): Promise<WorkspaceSnapshot>;
  createMixTask(plan: MixPlan, outputs: Exclude<OutputKind, 'final'>[]): Promise<WorkspaceSnapshot>;
  publish(request: PublishRequest): Promise<WorkspaceSnapshot>;
  saveSettings(settings: Settings): Promise<WorkspaceSnapshot>;
  importDirectory?(path: string): Promise<WorkspaceSnapshot>;
  createMixPlan?(config: MixConfig): Promise<MixPlan>;
  importOutputs?(files: File[]): Promise<WorkspaceSnapshot>;
  confirmOutput?(id: string): Promise<WorkspaceSnapshot>;
  cancelPublish?(id: string): Promise<WorkspaceSnapshot>;
  createPairing?(): Promise<PairingCode>;
  revokePairing?(extensionId: string): Promise<WorkspaceSnapshot>;
}
