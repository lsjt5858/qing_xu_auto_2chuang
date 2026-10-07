import { useEffect, useState } from 'react';
import { useSnapshot } from '../app/workspace-context';
import { Badge, Button, Notice, PageHeader } from '../components/ui';
import type { PairingCode, Settings } from '../domain/types';
import { formatDate } from '../domain/workspace';

export function SettingsPage() {
  const { snapshot, execute, busy, run, mode } = useSnapshot();
  const live = mode === 'live';
  const [edited, setDraft] = useState<Settings | null>(null);
  const draft = edited ?? snapshot.settings;
  const [pairing, setPairing] = useState<PairingCode | null>(null);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!pairing) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [pairing]);
  const changed = JSON.stringify(draft) !== JSON.stringify(snapshot.settings);
  const fields = [
    ['sourceDirectory', '素材目录'],
    ['outputDirectory', '处理结果目录'],
    ['draftDirectory', '剪映草稿目录'],
  ] as const;
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void execute(
          (repository) => repository.saveSettings(draft),
          live ? '设置已保存到本地服务' : '设置已保留在本次页面会话中',
        ).then((updated) => {
          if (updated) setDraft(null);
        });
      }}
    >
      <PageHeader title="设置" subtitle="管理本地目录、处理偏好与浏览器连接。">
        <Button type="submit" variant="primary" icon="check" disabled={busy || !changed}>
          {busy ? '保存中…' : '保存设置'}
        </Button>
      </PageHeader>
      <div className="settings-layout">
        <div className="panel">
          <section className="settings-group">
            <h2>本地目录</h2>
            {fields.map(([key, label]) => (
              <div className="form-field" key={key}>
                <label htmlFor={key}>{label}</label>
                <input
                  id={key}
                  required={!live || key === 'outputDirectory'}
                  pattern={live ? '/.*' : undefined}
                  title={live ? '请填写本机绝对路径，以 / 开头' : undefined}
                  placeholder={
                    live
                      ? key === 'draftDirectory'
                        ? '可留空；生成草稿前需配置'
                        : '/本机/目录'
                      : undefined
                  }
                  value={draft[key]}
                  spellCheck={false}
                  onChange={(event) => setDraft({ ...draft, [key]: event.target.value })}
                />
              </div>
            ))}
            <p className="field-help">
              {live
                ? '目录使用绝对路径。结果目录必填；草稿目录可留空，但生成草稿前必须配置。素材目录不会自动扫描。'
                : '目录配置暂存于当前页面会话，不会读取或修改实际目录。'}
            </p>
          </section>
          <section className="settings-group">
            <h2>处理偏好</h2>
            <div className="form-field">
              <label htmlFor="transcription-model">转录模型</label>
              <select
                id="transcription-model"
                value={draft.transcriptionModel}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    transcriptionModel: event.target.value as Settings['transcriptionModel'],
                  })
                }
              >
                {['tiny', 'base', 'small', 'medium'].map((model) => (
                  <option key={model}>{model}</option>
                ))}
              </select>
            </div>
            <label className="switch-label">
              <span>
                复用已有分析结果<small>已有结果时不重复运行相同处理。</small>
              </span>
              <input
                className="toggle"
                type="checkbox"
                checked={draft.reuseAnalysis}
                onChange={(event) => setDraft({ ...draft, reuseAnalysis: event.target.checked })}
              />
            </label>
            <label className="switch-label">
              <span>
                {live ? '始终完整使用片段' : '优先保留原始长镜头'}
                <small>
                  {live
                    ? '当前真实混剪不裁切片段；preserveLongShots 仅为兼容字段，关闭也不会裁切。'
                    : '在原始切镜基础上进行后续处理。'}
                </small>
              </span>
              <input
                className="toggle"
                type="checkbox"
                checked={live || draft.preserveLongShots}
                disabled={live}
                onChange={(event) =>
                  setDraft({ ...draft, preserveLongShots: event.target.checked })
                }
              />
            </label>
          </section>
          {changed && (
            <p className="field-help" role="status">
              有未保存的修改。
            </p>
          )}
        </div>
        <aside>
          <div className="panel">
            <h2 className="panel-title">连接与依赖</h2>
            {live ? (
              <>
                <div className="dependency-row">
                  <span>本地处理引擎 · {snapshot.service?.version ?? '未知版本'}</span>
                  <Badge status="completed">已连接</Badge>
                </div>
                {snapshot.service?.dependencies.map((dependency) => (
                  <div key={dependency.name}>
                    <div className="dependency-row">
                      <span>{dependency.name}</span>
                      <Badge status={dependency.available ? 'completed' : 'failed'}>
                        {dependency.available ? '可用' : '不可用'}
                      </Badge>
                    </div>
                    <p className="field-help">{dependency.detail}</p>
                  </div>
                ))}
              </>
            ) : (
              ['本地处理引擎', 'FFmpeg', 'Whisper', 'Chrome 发布插件'].map((name) => (
                <div className="dependency-row" key={name}>
                  <span>{name}</span>
                  <Badge>未连接</Badge>
                </div>
              ))
            )}
            <p className="setting-note">
              {live
                ? '依赖信息由本地服务返回。缺失依赖可能导致对应处理步骤失败。'
                : '接入本地服务后显示实际连接与依赖状态。'}
            </p>
          </div>
          {live && (
            <div className="panel pairing-panel">
              <h2 className="panel-title">Chrome 插件配对</h2>
              <p className="setting-note">
                主动生成配对码后，在插件 runner 中输入。登录状态留在浏览器，工作台不读取平台
                Cookie。
              </p>
              <Button
                disabled={busy}
                onClick={async () => {
                  const code = await run((repository) => {
                    if (!repository.createPairing) throw new Error('当前仓库不支持配对。');
                    return repository.createPairing();
                  });
                  if (code) {
                    setPairing(code);
                    setNow(Date.now());
                  }
                }}
              >
                生成配对码
              </Button>
              {pairing && (
                <div className="pairing-code" role="status">
                  {now < Date.parse(pairing.expiresAt) ? (
                    <>
                      <strong className="mono">{pairing.code}</strong>
                      <p>有效至 {formatDate(pairing.expiresAt)}，请勿分享给他人。</p>
                    </>
                  ) : (
                    <p>配对码已过期，请主动重新生成。</p>
                  )}
                </div>
              )}
              {snapshot.service?.extensions.map((extension) => (
                <div className="paired-extension" key={extension.id}>
                  <div className="dependency-row">
                    <strong>{extension.name}</strong>
                    <Badge status={extension.connected ? 'completed' : 'waiting'}>
                      {extension.connected ? '在线' : '离线'}
                    </Badge>
                  </div>
                  <p className="field-help mono">{extension.id}</p>
                  <p className="field-help">最近连接 {formatDate(extension.lastSeenAt)}</p>
                  <Button
                    className="small"
                    variant="danger"
                    disabled={busy}
                    onClick={() =>
                      void execute((repository) => {
                        if (!repository.revokePairing) throw new Error('当前仓库不支持撤销配对。');
                        return repository.revokePairing(extension.id);
                      }, '已撤销插件配对')
                    }
                  >
                    撤销配对
                  </Button>
                </div>
              ))}
              {!snapshot.service?.extensions.length && (
                <p className="setting-note">暂无已配对插件。</p>
              )}
            </div>
          )}
          <Notice>
            {live
              ? '配对令牌由插件保管，工作台仅展示配对码及连接状态。撤销后插件需重新配对。'
              : '此版本不保存凭据。设置仅在当前页面会话中保留，刷新后恢复示例值。'}
          </Notice>
        </aside>
      </div>
    </form>
  );
}
