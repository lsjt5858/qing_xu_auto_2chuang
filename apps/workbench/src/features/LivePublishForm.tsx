import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useSnapshot } from '../app/workspace-context';
import { Dialog } from '../components/Dialog';
import { MediaPreview } from '../components/MediaPreview';
import { Badge, Button, Notice } from '../components/ui';
import type { Output, PublishMode, PublishRequest } from '../domain/types';
import { formatBytes, formatDuration } from '../domain/workspace';

export function LivePublishForm({ output }: { output: Output }) {
  const { snapshot, busy, execute, refresh } = useSnapshot();
  const [title, setTitle] = useState(output.title);
  const [caption, setCaption] = useState(output.caption);
  const [accountId, setAccountId] = useState('');
  const [mode, setMode] = useState<PublishMode>('prefill');
  const [ready, setReady] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  const [confirmation, setConfirmation] = useState('');
  const [pending, setPending] = useState<{ request: PublishRequest; key: string } | null>(null);
  const account = snapshot.accounts?.find((item) => item.id === accountId);
  const paired =
    !!account && !!snapshot.service?.extensions.some((item) => item.id === account.extensionId);
  const key = JSON.stringify({
    output: [
      output.id,
      output.kind,
      output.fileUrl,
      output.sizeBytes,
      output.durationSeconds,
      output.width,
      output.height,
    ],
    account: account && [account.id, account.uid, account.extensionId, account.name, paired],
    title,
    caption,
    mode,
  });
  const confirmed = confirmation === key;
  const duplicate = snapshot.receipts.some(
    (item) =>
      item.outputId === output.id &&
      item.accountId === accountId &&
      item.status !== 'cancelled' &&
      ([
        'queued',
        'uploading',
        'filling',
        'submitting',
        'unknown',
        'awaiting_confirmation',
        'blocked',
      ].includes(item.status) ||
        (item.title.trim() === title.trim() &&
          item.caption.trim() === caption.trim() &&
          item.mode === mode)),
  );
  const validFile =
    output.sizeBytes !== null && output.sizeBytes > 0 && output.sizeBytes <= 512 * 1024 * 1024;
  const canSubmit =
    output.kind === 'final' &&
    ready &&
    validFile &&
    paired &&
    confirmed &&
    !!title.trim() &&
    title.length <= 55 &&
    !busy &&
    !duplicate;

  async function submit(request: PublishRequest) {
    if (!canSubmit) return;
    const updated = await execute(
      (repository) => repository.publish(request),
      '已加入真实发布队列，等待插件执行',
    );
    setPending(null);
    setConfirmation('');
    if (!updated) refresh();
  }

  if (output.kind === 'draft')
    return (
      <div className="panel">
        <h2>这是剪映草稿</h2>
        <p className="setting-note">
          请在剪映打开草稿，检查标题、画面与关键帧，导出 MP4
          后使用“导入成片”。草稿没有视频预览或下载地址。
        </p>
        <p className="field-help">草稿目录：{snapshot.settings.draftDirectory || '尚未配置'}</p>
      </div>
    );

  return (
    <>
      <section className="panel">
        <h2 className="panel-title">检查实际视频</h2>
        <MediaPreview
          src={output.fileUrl ?? `/api/outputs/${encodeURIComponent(output.id)}/file`}
          name={output.name}
          onReadyChange={(value) => {
            setReady(value);
            if (!value) {
              setReviewed(false);
              setConfirmation('');
            }
          }}
        />
        <p className="setting-note">
          {output.width && output.height
            ? `${output.width} × ${output.height} · `
            : '分辨率未提供 · '}
          {formatDuration(output.durationSeconds)} ·{' '}
          {output.sizeBytes === null ? '大小未知' : formatBytes(output.sizeBytes)}
        </p>
        {!validFile && (
          <Notice warm>
            发布只支持非空、最大 512 MiB 的 MP4。请重新导出并导入符合要求的成片。
          </Notice>
        )}
        {output.kind === 'preview' && (
          <>
            <Notice warm>
              这是实际合成的预览。剪映后加的标题与特效不一定包含在内；请播放检查后，明确将此版本确认为最终成片，或导入剪映导出的
              MP4。
            </Notice>
            <label className="confirm-row">
              <input
                id="confirm-final"
                type="checkbox"
                disabled={!ready || busy}
                checked={reviewed}
                onChange={(event) => setReviewed(event.target.checked)}
              />
              我已预览此文件，确认这就是最终版本。
            </label>
            <Button
              variant="primary"
              disabled={!ready || !reviewed || busy || !validFile}
              onClick={() =>
                void execute((repository) => {
                  if (!repository.confirmOutput) throw new Error('当前仓库不支持成片确认。');
                  return repository.confirmOutput(output.id);
                }, '已确认为最终成片')
              }
            >
              确认为最终成片
            </Button>
          </>
        )}
      </section>
      {output.kind === 'final' && (
        <form
          className="panel"
          onSubmit={(event) => {
            event.preventDefault();
            if (!canSubmit) return;
            const request: PublishRequest = {
              outputId: output.id,
              accountId,
              title: title.trim(),
              caption,
              mode,
              confirmed: true,
            };
            if (mode === 'direct') setPending({ request, key });
            else void submit(request);
          }}
        >
          <h2 className="panel-title">
            <span className="step-marker">01</span>发布信息
          </h2>
          <div className="form-field">
            <label htmlFor="publish-title">标题</label>
            <input
              id="publish-title"
              value={title}
              required
              maxLength={55}
              onChange={(event) => {
                setTitle(event.target.value);
                setConfirmation('');
              }}
            />
            <span className="field-help">{title.length} / 55</span>
          </div>
          <div className="form-field">
            <label htmlFor="publish-caption">文案与话题</label>
            <textarea
              id="publish-caption"
              value={caption}
              maxLength={1000}
              onChange={(event) => {
                setCaption(event.target.value);
                setConfirmation('');
              }}
            />
          </div>
          <Notice>
            当前协议不设置自定义封面。封面使用平台默认结果；需要在平台检查或调整时，请选择预填模式。
          </Notice>
          <h2 className="panel-title">
            <span className="step-marker">02</span>平台与账号
          </h2>
          <div className="form-field">
            <label htmlFor="publish-account">发布账号</label>
            <select
              id="publish-account"
              value={accountId}
              onChange={(event) => {
                setAccountId(event.target.value);
                setConfirmation('');
              }}
            >
              <option value="">请选择已配对的抖音账号</option>
              {snapshot.accounts?.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} · {item.handle || item.uid} · {item.connected ? '在线' : '离线'}
                </option>
              ))}
            </select>
          </div>
          {account && (
            <div className="publish-target">
              <span className="douyin-logo" aria-hidden="true">
                ♪
              </span>
              <div>
                <h3>抖音 · {account.name}</h3>
                <small>
                  UID {account.uid} · {account.handle}
                </small>
              </div>
              <Badge status={paired ? (account.connected ? 'completed' : 'waiting') : 'failed'}>
                {paired ? (account.connected ? '已配对 · 在线' : '已配对 · 离线') : '配对已失效'}
              </Badge>
            </div>
          )}
          {!paired ? (
            <Notice warm>
              请先在 <Link to="/settings">设置</Link> 配对插件，并在 runner 中选择已登录账号。
            </Notice>
          ) : (
            !account?.connected && (
              <Notice>
                账号当前离线，仍可加入队列；只有绑定插件上线并核验同一 UID 后才会执行。
              </Notice>
            )
          )}
          <fieldset className="publish-mode">
            <legend className="panel-title">
              <span className="step-marker">03</span>执行方式
            </legend>
            <div className="radio-stack">
              <label className="radio-option">
                <input
                  type="radio"
                  name="publish-mode"
                  checked={mode === 'prefill'}
                  onChange={() => {
                    setMode('prefill');
                    setConfirmation('');
                  }}
                />
                <span>
                  预填后，我来确认 <Badge>推荐</Badge>
                  <small>真实上传并填写文案，停在平台最终提交前。</small>
                </span>
              </label>
              <label className="radio-option">
                <input
                  type="radio"
                  name="publish-mode"
                  checked={mode === 'direct'}
                  onChange={() => {
                    setMode('direct');
                    setConfirmation('');
                  }}
                />
                <span>
                  直接发布<small>再次确认冻结内容后，授权插件单次提交平台。</small>
                </span>
              </label>
            </div>
          </fieldset>
          {duplicate && (
            <Notice warm>
              此成片与账号已有发布记录。请先核查下方队列与平台页面，勿重复发布；可取消的任务取消后才能重新确认。
            </Notice>
          )}
          <label className="confirm-row">
            <input
              id="publish-confirm"
              type="checkbox"
              checked={confirmed}
              disabled={!ready || !paired || busy || duplicate}
              onChange={(event) => setConfirmation(event.target.checked ? key : '')}
            />
            <span>
              我已播放核对成片、平台默认封面、文案和目标账号，授权本条
              {mode === 'direct' ? '直接发布' : '预填任务'}。
            </span>
          </label>
          <Button
            type="submit"
            className="full"
            variant="primary"
            icon="send"
            disabled={!canSubmit}
          >
            {busy ? '正在提交队列…' : mode === 'prefill' ? '提交预填任务' : '提交直接发布'}
          </Button>
          <p className="field-help centered">
            创建队列不代表已发布。以插件回报及平台成功证据为准。
          </p>
        </form>
      )}
      {pending && (
        <Dialog
          title="确认真实直接发布"
          subtitle="将按以下冻结内容操作真实平台，请逐条核对。"
          busy={busy}
          onClose={() => setPending(null)}
          footer={
            <>
              <span>本次仅提交 1 条成片</span>
              <div>
                <Button disabled={busy} onClick={() => setPending(null)}>
                  返回检查
                </Button>
                <Button
                  variant="primary"
                  disabled={!canSubmit || pending.key !== key}
                  onClick={() => void submit(pending.request)}
                >
                  确认提交队列
                </Button>
              </div>
            </>
          }
        >
          <dl className="summary-list">
            <dt>成片</dt>
            <dd>{output.name}</dd>
            <dt>标题</dt>
            <dd>{pending.request.title}</dd>
            <dt>文案</dt>
            <dd className="preserve-lines">{pending.request.caption || '无'}</dd>
            <dt>目标账号</dt>
            <dd>
              抖音 · {account?.name} · UID {account?.uid}
            </dd>
            <dt>执行方式</dt>
            <dd>直接发布</dd>
          </dl>
          <Notice warm>
            插件会实际上传并提交。提交中断线或结果未知时必须人工核查，不会自动重试；开始执行后不能通过工作台撤回平台内容。
          </Notice>
          {pending.key !== key && (
            <p className="form-error" role="alert">
              成片或账号状态已变化，请返回重新核对。
            </p>
          )}
        </Dialog>
      )}
    </>
  );
}
