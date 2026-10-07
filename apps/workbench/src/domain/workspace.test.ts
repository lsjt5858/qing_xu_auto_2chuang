import { describe, expect, it } from 'vitest';
import { createInitialSnapshot } from '../data/fixtures';
import {
  createMixPlan,
  getOverview,
  matchesMixConfig,
  normalizeSteps,
  validateProcessing,
  validatePublish,
  validateSettings,
} from './workspace';
import type { MixConfig, ProcessingRequest, PublishRequest } from './types';

const fixture = createInitialSnapshot();
const processing: ProcessingRequest = {
  materialIds: ['m1'],
  name: '',
  steps: ['scenes'],
  threshold: 27,
};
const publishing: PublishRequest = {
  outputId: 'o1',
  accountId: 'douyin-demo',
  title: '法式美甲',
  caption: '#美甲',
  mode: 'prefill',
  confirmed: true,
};

describe('processing validation', () => {
  it('adds semantic prerequisites and gives a stable execution order', () => {
    expect(normalizeSteps(['semantic', 'clean', 'transcribe'])).toEqual([
      'clean',
      'scenes',
      'transcribe',
      'semantic',
    ]);
  });
  it('deduplicates selected videos and trims the name', () => {
    expect(
      validateProcessing(
        { ...processing, materialIds: ['m1', 'm1'], name: ' 教学 ' },
        fixture.materials,
      ),
    ).toMatchObject({ materialIds: ['m1'], name: '教学' });
  });
  it.each([{ materialIds: [] }, { materialIds: ['missing'] }, { materialIds: ['m3'] }])(
    'rejects unusable selections $materialIds',
    ({ materialIds }) => {
      expect(() => validateProcessing({ ...processing, materialIds }, fixture.materials)).toThrow();
    },
  );
  it.each([NaN, Infinity, 0, 101])('rejects threshold %s', (threshold) => {
    expect(() => validateProcessing({ ...processing, threshold }, fixture.materials)).toThrow(
      '1–100',
    );
  });
  it('requires a processing operation', () => {
    expect(() => validateProcessing({ ...processing, steps: [] }, fixture.materials)).toThrow(
      '处理步骤',
    );
  });
});

describe('fixed composition plans', () => {
  const config: MixConfig = { seed: '20261006', template: 'teaching', pool: 'all' };
  it('gives identical plans with the same seed even if the UI reorders materials', () => {
    expect(createMixPlan(config, fixture.materials)).toEqual(
      createMixPlan(config, [...fixture.materials].reverse()),
    );
  });
  it('uses only the selected pool and preserves the template duration', () => {
    const plan = createMixPlan({ ...config, pool: 'shots' }, fixture.materials);
    expect(plan.durationSeconds).toBe(42);
    expect(plan.clips.every((clip) => ['m5', 'm6'].includes(clip.materialId))).toBe(true);
  });
  it('detects changes that require regenerating a plan', () => {
    const plan = createMixPlan(config, fixture.materials);
    expect(matchesMixConfig(plan, config)).toBe(true);
    for (const changed of [
      { ...config, seed: '1' },
      { ...config, template: 'showcase' as const },
      { ...config, pool: 'shots' as const },
    ]) {
      expect(matchesMixConfig(plan, changed)).toBe(false);
    }
  });
  it('rejects an empty pool and blank seed', () => {
    expect(() => createMixPlan(config, [])).toThrow('没有可用素材');
    expect(() => createMixPlan({ ...config, seed: ' ' }, fixture.materials)).toThrow('随机种子');
  });
});

describe('publish validation and overview', () => {
  it.each([
    { confirmed: false },
    { accountId: 'another-account' },
    { outputId: 'o3' },
    { outputId: 'missing' },
    { title: ' ' },
    { title: '字'.repeat(56) },
    { caption: '字'.repeat(1001) },
  ])('rejects unsafe or incomplete publish input %j', (change) => {
    expect(() => validatePublish({ ...publishing, ...change }, fixture.outputs)).toThrow();
  });
  it('requires an explicit confirmation even for prefill', () => {
    expect(() => validatePublish(publishing, fixture.outputs)).not.toThrow();
    expect(() => validatePublish({ ...publishing, confirmed: false }, fixture.outputs)).toThrow();
  });
  it('derives counts and removes handled outputs from the pending list', () => {
    const data = createInitialSnapshot();
    expect(getOverview(data)).toMatchObject({
      materialCount: 8,
      runningCount: 1,
      queuedCount: 1,
      sceneCount: 38,
    });
    data.receipts.push({
      ...publishing,
      id: 'receipt',
      createdAt: new Date().toISOString(),
      status: 'awaiting_confirmation',
      simulated: true,
    });
    expect(getOverview(data).readyOutputs).toHaveLength(0);
  });
  it('rejects missing settings without writing anything', () => {
    expect(() => validateSettings({ ...fixture.settings, outputDirectory: '  ' })).toThrow('目录');
  });
});
