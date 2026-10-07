// @vitest-environment jsdom
import { act, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { WorkspaceProvider } from './WorkspaceProvider';
import { useSnapshot, useWorkspace } from './workspace-context';
import { AppShell } from './AppShell';
import { PublishPage } from '../pages/PublishPage';
import { StudioPage } from '../pages/StudioPage';
import { SettingsPage } from '../pages/SettingsPage';
import { TasksPage } from '../pages/TasksPage';
import { ImportFiles } from '../features/ImportFiles';
import { createInitialSnapshot } from '../data/fixtures';
import type { WorkspaceRepository, WorkspaceSnapshot } from '../domain/types';

let container: HTMLDivElement;
let root: Root;
const liveSnapshot = (): WorkspaceSnapshot => ({
  ...createInitialSnapshot(),
  outputs: [
    {
      ...createInitialSnapshot().outputs[0]!,
      fileUrl: '/api/outputs/o1/file',
      width: 720,
      height: 1280,
    },
  ],
  accounts: [
    {
      id: 'a1',
      platform: 'douyin',
      uid: 'uid1',
      name: '真实账号甲',
      handle: '@first',
      extensionId: 'ext1',
      connected: true,
      lastSeenAt: new Date().toISOString(),
    },
    {
      id: 'a2',
      platform: 'douyin',
      uid: 'uid2',
      name: '真实账号乙',
      handle: '@second',
      extensionId: 'ext2',
      connected: true,
      lastSeenAt: new Date().toISOString(),
    },
  ],
  service: {
    mode: 'live',
    version: '1',
    dependencies: [{ name: 'FFmpeg', available: false, detail: '未安装 ffmpeg' }],
    extensions: [
      { id: 'ext1', name: '发布插件', connected: true, lastSeenAt: new Date().toISOString() },
      { id: 'ext2', name: '插件乙', connected: true, lastSeenAt: new Date().toISOString() },
    ],
  },
});
function adapter(snapshot = liveSnapshot()): WorkspaceRepository {
  const update = async () => structuredClone(snapshot);
  return {
    mode: 'live',
    load: vi.fn(update),
    importFiles: vi.fn(update),
    importDirectory: vi.fn(update),
    createTasks: vi.fn(update),
    commandTask: vi.fn(update),
    createMixTask: vi.fn(update),
    publish: vi.fn(update),
    saveSettings: vi.fn(update),
    importOutputs: vi.fn(update),
    confirmOutput: vi.fn(update),
    cancelPublish: vi.fn(update),
    revokePairing: vi.fn(update),
    createPairing: vi.fn(async () => ({
      code: 'AB12CD34',
      expiresAt: new Date(Date.now() + 60_000).toISOString(),
    })),
    createMixPlan: vi.fn(async (config) => ({
      id: 'server-plan',
      config,
      clips: [{ materialId: 'm1', label: '完整原片', durationSeconds: 193.5 }],
      durationSeconds: 193.5,
    })),
  };
}
async function render(repository: WorkspaceRepository, children: ReactNode) {
  await act(async () =>
    root.render(
      <MemoryRouter>
        <WorkspaceProvider repository={repository}>
          <Loaded>{children}</Loaded>
        </WorkspaceProvider>
      </MemoryRouter>,
    ),
  );
}
function Loaded({ children }: { children: ReactNode }) {
  const { snapshot } = useWorkspace();
  return snapshot ? children : null;
}
const button = (text: string) =>
  [...document.querySelectorAll('button')].find((item) => item.textContent?.includes(text))!;
async function click(element: HTMLElement) {
  await act(async () => element.click());
}
async function change(element: HTMLInputElement | HTMLSelectElement, value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(
      element instanceof HTMLSelectElement
        ? HTMLSelectElement.prototype
        : HTMLInputElement.prototype,
      'value',
    )!.set!.call(element, value);
    element.dispatchEvent(
      new Event(element instanceof HTMLSelectElement ? 'change' : 'input', { bubbles: true }),
    );
  });
}
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  vi.useFakeTimers();
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function () {
    this.open = false;
  };
  HTMLElement.prototype.showPopover = function () {};
  HTMLElement.prototype.hidePopover = function () {};
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('真实工作台交互', () => {
  it('后台刷新不卸载表单，旧读响应不能覆盖更新结果', async () => {
    const repository = adapter();
    let finishRead!: (value: WorkspaceSnapshot) => void;
    function Probe() {
      const { snapshot, loading, refresh, execute } = useSnapshot();
      return (
        <>
          <input aria-label="保留草稿" defaultValue="草稿" />
          <span>{loading ? '整页加载' : '可操作'}</span>
          <span>{snapshot.settings.outputDirectory}</span>
          <button onClick={refresh}>刷新</button>
          <button
            onClick={() => void execute((repo) => repo.saveSettings(snapshot.settings), '已保存')}
          >
            写入
          </button>
        </>
      );
    }
    await render(repository, <Probe />);
    const input = container.querySelector('input');
    vi.mocked(repository.load).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishRead = resolve;
        }),
    );
    await click(button('刷新'));
    expect(container.textContent).not.toContain('整页加载');
    const updated = liveSnapshot();
    updated.settings.outputDirectory = '/新的结果';
    vi.mocked(repository.saveSettings).mockResolvedValueOnce(updated);
    await click(button('写入'));
    await act(async () => finishRead(liveSnapshot()));
    expect(container.textContent).toContain('/新的结果');
    expect(container.querySelector('input')).toBe(input);
  });

  it('后台错误保留已有界面与草稿并允许重连', async () => {
    const repository = adapter();
    await act(async () =>
      root.render(
        <MemoryRouter>
          <WorkspaceProvider repository={repository}>
            <AppShell />
          </WorkspaceProvider>
        </MemoryRouter>,
      ),
    );
    vi.mocked(repository.load).mockRejectedValueOnce(new Error('服务断开 8766'));
    await act(async () => vi.advanceTimersByTimeAsync(3000));
    expect(container.textContent).toContain('服务断开 8766');
    expect(container.textContent).toContain('重试连接');
    expect(container.textContent).not.toContain('工作空间暂时无法加载');
  });

  it('任务仅显示真实取消/重试，不提供暂停和推进', async () => {
    const repository = adapter();
    await render(repository, <TasksPage />);
    expect(container.textContent).not.toContain('开始演示');
    expect(container.textContent).not.toContain('暂停');
    await click(button('取消任务'));
    expect(repository.commandTask).toHaveBeenCalledWith(expect.any(String), 'cancel');
  });

  it('Studio 主动请求保存服务端计划，保留完整时长', async () => {
    const repository = adapter();
    await render(repository, <StudioPage />);
    expect(repository.createMixPlan).not.toHaveBeenCalled();
    expect(container.textContent).not.toContain('42 秒');
    expect(button('创建混剪任务').disabled).toBe(true);
    await click(button('生成选片方案'));
    expect(container.textContent).toContain('193.5');
    await click(button('创建混剪任务'));
    expect(repository.createMixTask).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'server-plan', durationSeconds: 193.5 }),
      ['preview', 'draft'],
    );
  });

  it('目录导入发送用户明确填写的路径', async () => {
    const repository = adapter();
    await render(repository, <ImportFiles onImported={() => {}} />);
    await change(container.querySelector<HTMLInputElement>('#import-directory')!, '/真实素材');
    await click(button('扫描并导入'));
    expect(repository.importDirectory).toHaveBeenCalledWith('/真实素材');
  });

  it('配对码仅在点击后生成，依赖真实展示并可撤销', async () => {
    const repository = adapter();
    await render(repository, <SettingsPage />);
    expect(repository.createPairing).not.toHaveBeenCalled();
    expect(container.textContent).toContain('未安装 ffmpeg');
    await click(button('生成配对码'));
    expect(container.textContent).toContain('AB12CD34');
    await click(button('撤销配对'));
    expect(repository.revokePairing).toHaveBeenCalledWith('ext1');
  });

  it('预览必须先明确确认为成片，不可直接进入发布', async () => {
    const snapshot = liveSnapshot();
    snapshot.outputs[0]!.kind = 'preview';
    const repository = adapter(snapshot);
    await render(repository, <PublishPage />);
    expect(button('确认为最终成片').disabled).toBe(true);
    const video = container.querySelector('video')!;
    expect(video.getAttribute('src')).toBe('/api/outputs/o1/file');
    await act(async () => video.dispatchEvent(new Event('loadeddata')));
    await click(container.querySelector<HTMLInputElement>('#confirm-final')!);
    await click(button('确认为最终成片'));
    expect(repository.confirmOutput).toHaveBeenCalledWith('o1');
    expect(repository.publish).not.toHaveBeenCalled();
  });

  it('更换账号使确认失效，直接发布二次确认冻结内容', async () => {
    const repository = adapter();
    await render(repository, <PublishPage />);
    await act(async () => container.querySelector('video')!.dispatchEvent(new Event('loadeddata')));
    const select = container.querySelector<HTMLSelectElement>('#publish-account')!;
    await change(select, 'a1');
    const confirm = container.querySelector<HTMLInputElement>('#publish-confirm')!;
    await click(confirm);
    await change(select, 'a2');
    expect(confirm.checked).toBe(false);
    await click(container.querySelectorAll<HTMLInputElement>('input[name="publish-mode"]')[1]!);
    await click(confirm);
    await click(button('提交直接发布'));
    expect(repository.publish).not.toHaveBeenCalled();
    expect(document.querySelector('dialog')?.textContent).toContain('真实账号乙');
    await click(button('确认提交队列'));
    expect(repository.publish).toHaveBeenCalledWith(
      expect.objectContaining({ accountId: 'a2', mode: 'direct', confirmed: true }),
    );
  });

  it('unknown 不显示成功且不能自动重试', async () => {
    const snapshot = liveSnapshot();
    snapshot.accounts![0]!.connected = false;
    snapshot.receipts = [
      {
        id: 'job',
        outputId: 'o1',
        accountId: 'a1',
        title: '待核查',
        caption: '',
        mode: 'direct',
        simulated: false,
        status: 'unknown',
        createdAt: new Date().toISOString(),
        message: '提交后断线，请人工核查',
        accountName: '真实账号甲',
      },
    ];
    await render(adapter(snapshot), <PublishPage />);
    expect(container.textContent).toContain('提交后断线，请人工核查');
    expect(container.textContent).toContain('结果未知');
    expect(container.textContent).not.toContain('已模拟提交');
    expect(button('提交预填任务').disabled).toBe(true);
    expect(button('重试发布')).toBeUndefined();
  });
});
