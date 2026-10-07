import { beforeEach, describe, expect, it } from 'vitest';
import { DemoWorkspaceRepository } from './demo-repository';
import { createMixPlan } from '../domain/workspace';

describe('demo workspace lifecycle', () => {
  let repository: DemoWorkspaceRepository;
  beforeEach(() => {
    repository = new DemoWorkspaceRepository();
  });

  it('keeps callers from mutating the repository snapshot', async () => {
    const snapshot = await repository.load();
    snapshot.tasks.length = 0;
    expect((await repository.load()).tasks).toHaveLength(5);
  });

  it('creates batch tasks atomically and keeps unique ids across analysis and mix', async () => {
    await expect(
      repository.createTasks({
        materialIds: ['m1', 'missing'],
        name: '',
        steps: ['scenes'],
        threshold: 27,
      }),
    ).rejects.toThrow();
    expect((await repository.load()).tasks).toHaveLength(5);
    const updated = await repository.createTasks({
      materialIds: ['m1', 'm2', 'm1'],
      name: '批量教学',
      steps: ['semantic'],
      threshold: 20,
    });
    expect(updated.tasks.slice(0, 2).map((task) => task.name)).toEqual([
      '批量教学 · 1',
      '批量教学 · 2',
    ]);
    expect(updated.tasks[0]!.steps).toEqual(['scenes', 'transcribe', 'semantic']);
    const plan = createMixPlan({ seed: '1', template: 'showcase', pool: 'all' }, updated.materials);
    const result = await repository.createMixTask(plan, ['preview']);
    expect(new Set(result.tasks.map((task) => task.id)).size).toBe(result.tasks.length);
  });

  it('supports pause/resume and rejects stale commands', async () => {
    await repository.commandTask('JF-1026', 'pause');
    await expect(repository.commandTask('JF-1026', 'advance')).rejects.toThrow('状态');
    const resumed = await repository.commandTask('JF-1026', 'resume');
    expect(resumed.tasks.find((task) => task.id === 'JF-1026')).toMatchObject({
      status: 'running',
      progress: 68,
    });
    await expect(repository.commandTask('JF-1026', 'retry')).rejects.toThrow('状态');
  });

  it('retries a failure and exposes analysis results after completion', async () => {
    const retried = await repository.commandTask('JF-1022', 'retry');
    expect(retried.tasks.find((task) => task.id === 'JF-1022')).toMatchObject({
      status: 'queued',
      progress: 0,
    });
    expect(retried.tasks.find((task) => task.id === 'JF-1022')?.error).toBeUndefined();
    await repository.commandTask('JF-1022', 'start');
    for (let i = 0; i < 4; i++) await repository.commandTask('JF-1022', 'advance');
    const done = await repository.load();
    expect(done.tasks.find((task) => task.id === 'JF-1022')?.status).toBe('completed');
    expect(
      done.materials.find((material) => material.id === 'm8')?.transcript.length,
    ).toBeGreaterThan(0);
    await expect(repository.commandTask('JF-1022', 'advance')).rejects.toThrow('状态');
  });

  it('keeps the exact preview plan and creates only requested output types', async () => {
    const source = await repository.load();
    const plan = createMixPlan(
      { seed: '24680', template: 'teaching', pool: 'shots' },
      source.materials,
    );
    const created = await repository.createMixTask(plan, ['draft']);
    const task = created.tasks[0]!;
    expect(task.plan).toEqual(plan);
    plan.clips[0]!.label = 'modified externally';
    expect((await repository.load()).tasks[0]!.plan?.clips[0]?.label).not.toBe(
      'modified externally',
    );
    await repository.commandTask(task.id, 'start');
    for (let i = 0; i < 4; i++) await repository.commandTask(task.id, 'advance');
    const done = await repository.load();
    expect(
      done.outputs.filter((output) => output.taskId === task.id).map((output) => output.kind),
    ).toEqual(['draft']);
    expect(done.tasks[0]!.outputIds).toHaveLength(1);
  });

  it('registers local file metadata without inventing video analysis', async () => {
    const imported = await repository.importFiles([
      new File(['test-video-bytes'], 'local.mp4', { type: 'video/mp4' }),
    ]);
    const local = imported.materials[0]!;
    expect(local).toMatchObject({ source: 'local', durationSeconds: null, scenes: [] });
    const created = await repository.createTasks({
      materialIds: [local.id],
      name: '',
      steps: ['scenes', 'transcribe'],
      threshold: 27,
    });
    const id = created.tasks[0]!.id;
    await repository.commandTask(id, 'start');
    for (let i = 0; i < 4; i++) await repository.commandTask(id, 'advance');
    expect(
      (await repository.load()).materials.find((material) => material.id === local.id),
    ).toMatchObject({ status: 'pending', transcript: [], scenes: [] });
  });

  it('rejects invalid imports without partially adding files', async () => {
    await expect(
      repository.importFiles([new File(['bytes'], 'good.mp4'), new File(['bytes'], 'bad.txt')]),
    ).rejects.toThrow();
    await expect(repository.importFiles([new File([], 'empty.mp4')])).rejects.toThrow();
    expect((await repository.load()).materials).toHaveLength(8);
  });

  it('records only confirmed publishes and distinguishes prefill from submission', async () => {
    const request = {
      outputId: 'o1',
      accountId: 'douyin-demo',
      title: '课堂',
      caption: '',
      mode: 'prefill' as const,
      confirmed: true,
    };
    await expect(repository.publish({ ...request, confirmed: false })).rejects.toThrow();
    expect((await repository.load()).receipts).toHaveLength(0);
    expect((await repository.publish(request)).receipts[0]?.status).toBe('awaiting_confirmation');
    expect((await repository.publish({ ...request, mode: 'direct' })).receipts[0]).toMatchObject({
      status: 'submitted',
      simulated: true,
    });
  });

  it('preserves valid settings for the session and rejects invalid replacement', async () => {
    const settings = { ...(await repository.load()).settings, outputDirectory: './new-output' };
    await repository.saveSettings(settings);
    await expect(repository.saveSettings({ ...settings, sourceDirectory: '' })).rejects.toThrow();
    expect((await repository.load()).settings.outputDirectory).toBe('./new-output');
    expect((await new DemoWorkspaceRepository().load()).settings.outputDirectory).toBe('./output');
  });
});
