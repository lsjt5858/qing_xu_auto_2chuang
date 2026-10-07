import { Api } from './api';
import { TabBridge } from './bridge';
import { Engine, type JournalRecord } from './engine';
import { CREATOR_ORIGIN, Stop } from './protocol';

const keys = {
  settings: 'jingflowPublisherSettings',
  journal: 'jingflowPublisherJournal',
} as const;

interface Settings {
  port: number;
  token: string;
  tabId?: number;
  accountUid?: string;
  accountName?: string;
}

class ChromeJournal {
  async load(): Promise<JournalRecord[]> {
    const value = await chrome.storage.local.get(keys.journal);
    return Array.isArray(value[keys.journal]) ? value[keys.journal] as JournalRecord[] : [];
  }

  save(records: JournalRecord[]): Promise<void> {
    return chrome.storage.local.set({ [keys.journal]: records });
  }
}

const byId = <T extends HTMLElement>(id: string) => {
  const element = document.getElementById(id);
  if (!(element instanceof HTMLElement)) throw new Error(`Missing runner element: ${id}`);
  return element as T;
};

const port = byId<HTMLInputElement>('port');
const code = byId<HTMLInputElement>('pairing-code');
const tabs = byId<HTMLSelectElement>('creator-tab');
const pairButton = byId<HTMLButtonElement>('pair');
const refreshButton = byId<HTMLButtonElement>('refresh-tabs');
const bindButton = byId<HTMLButtonElement>('bind-tab');
const startButton = byId<HTMLButtonElement>('start');
const stopButton = byId<HTMLButtonElement>('stop');
const pairingState = byId<HTMLElement>('pairing-state');
const accountState = byId<HTMLElement>('account-state');
const runnerState = byId<HTMLElement>('runner-state');

let running = false;
let bridge: TabBridge | undefined;

function state(element: HTMLElement, message: string, tone: 'idle' | 'ok' | 'warn' = 'idle'): void {
  element.textContent = message;
  element.dataset.tone = tone;
}

async function settings(): Promise<Settings> {
  const value = await chrome.storage.local.get(keys.settings);
  const saved = value[keys.settings];
  if (!saved || typeof saved !== 'object') return { port: 8766, token: '' };
  const candidate = saved as Partial<Settings>;
  return {
    port: Number.isInteger(candidate.port) ? candidate.port! : 8766,
    token: typeof candidate.token === 'string' ? candidate.token : '',
    tabId: Number.isInteger(candidate.tabId) ? candidate.tabId : undefined,
    accountUid: typeof candidate.accountUid === 'string' ? candidate.accountUid : undefined,
    accountName: typeof candidate.accountName === 'string' ? candidate.accountName : undefined,
  };
}

async function saveSettings(update: Partial<Settings>): Promise<Settings> {
  const next = { ...await settings(), ...update };
  await chrome.storage.local.set({ [keys.settings]: next });
  return next;
}

function api(config: Settings): Api {
  return new Api(config.port, chrome.runtime.id, config.token);
}

async function refreshTabs(selected?: number): Promise<void> {
  const available = (await chrome.tabs.query({ url: `${CREATOR_ORIGIN}/*` }))
    .filter(tab => tab.id !== undefined && tab.url?.startsWith(`${CREATOR_ORIGIN}/creator-micro/`));
  tabs.replaceChildren();
  for (const tab of available) {
    const option = document.createElement('option');
    option.value = String(tab.id);
    option.textContent = `${tab.title || '抖音创作者中心'} · #${tab.id}`;
    option.selected = tab.id === selected;
    tabs.append(option);
  }
  if (available.length === 0) {
    const option = document.createElement('option');
    option.textContent = '未找到已打开的创作者页面';
    option.disabled = true;
    option.selected = true;
    tabs.append(option);
  }
  bindButton.disabled = available.length === 0;
}

async function pair(): Promise<void> {
  const selectedPort = Number(port.value);
  pairButton.disabled = true;
  try {
    const client = new Api(selectedPort, chrome.runtime.id);
    const token = await client.pair(code.value);
    await saveSettings({ port: selectedPort, token, tabId: undefined, accountUid: undefined, accountName: undefined });
    code.value = '';
    state(pairingState, '已配对本地工作台', 'ok');
  } catch (error) {
    state(pairingState, error instanceof Error ? error.message : '配对失败', 'warn');
  } finally {
    pairButton.disabled = false;
  }
}

async function bind(): Promise<void> {
  const config = await settings();
  if (!config.token) throw new Stop('pairing', '请先配对本地工作台');
  const tabId = Number(tabs.value);
  if (!Number.isInteger(tabId)) throw new Stop('tab', '请选择创作者标签页');
  const candidate = new TabBridge(tabId);
  const account = await candidate.identity();
  await api(config).heartbeat(account);
  bridge = candidate;
  await saveSettings({ tabId, accountUid: account.uid, accountName: account.nickname });
  state(accountState, `${account.nickname || '抖音账号'} · UID ${account.uid}`, 'ok');
  startButton.disabled = false;
}

const wait = (milliseconds: number) => new Promise(resolve => setTimeout(resolve, milliseconds));

async function loop(): Promise<void> {
  if (running) throw new Stop('serial', 'runner 已在执行');
  const config = await settings();
  if (!config.token || config.tabId === undefined || !config.accountUid) {
    throw new Stop('binding', '请先配对并绑定账号');
  }
  bridge ??= new TabBridge(config.tabId);
  running = true;
  startButton.disabled = true;
  stopButton.disabled = false;
  await navigator.locks.request('jingflow-publisher-runner', { ifAvailable: true }, async lock => {
    if (!lock) throw new Stop('lock', '另一个 runner 正在执行');
    const engine = new Engine(api(config), bridge!, new ChromeJournal());
    await engine.recover();
    state(runnerState, '正在等待发布任务', 'ok');
    while (running) {
      const result = await engine.runOne(config.accountUid!);
      if (result) {
        state(runnerState, `任务状态：${result}`, result === 'submitted' ? 'ok' : 'warn');
        break;
      }
      await wait(2000);
    }
  });
}

function stop(updateState = true): void {
  running = false;
  bridge?.cancel();
  stopButton.disabled = true;
  startButton.disabled = false;
  if (updateState) state(runnerState, '已停止', 'idle');
}

pairButton.addEventListener('click', () => void pair());
refreshButton.addEventListener('click', () => {
  void refreshTabs(Number(tabs.value)).catch(error =>
    state(accountState, error instanceof Error ? error.message : '刷新标签页失败', 'warn'));
});
bindButton.addEventListener('click', () => {
  bindButton.disabled = true;
  void bind().catch(error => state(accountState, error instanceof Error ? error.message : '绑定失败', 'warn'))
    .finally(() => { bindButton.disabled = false; });
});
startButton.addEventListener('click', () => {
  void loop().catch(error => state(runnerState, error instanceof Error ? error.message : '执行失败', 'warn'))
    .finally(() => stop(false));
});
stopButton.addEventListener('click', () => stop());

void settings().then(async config => {
  port.value = String(config.port);
  state(pairingState, config.token ? '已配对本地工作台' : '尚未配对', config.token ? 'ok' : 'idle');
  if (config.accountUid) state(accountState, `${config.accountName || '抖音账号'} · UID ${config.accountUid}`, 'ok');
  await refreshTabs(config.tabId);
  startButton.disabled = !(config.token && config.tabId !== undefined && config.accountUid);
}).catch(error => {
  startButton.disabled = true;
  state(runnerState, error instanceof Error ? error.message : 'runner 初始化失败', 'warn');
});
