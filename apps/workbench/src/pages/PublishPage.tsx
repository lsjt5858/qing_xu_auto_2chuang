import { useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useSnapshot } from '../app/workspace-context';
import { Dialog } from '../components/Dialog';
import { Icon } from '../components/Icon';
import { MaterialVisual } from '../components/MaterialCard';
import { PublishReceiptCard } from '../components/PublishReceiptCard';
import { LivePublishForm } from '../features/LivePublishForm';
import { Badge, Button, EmptyState, Notice, PageHeader } from '../components/ui';
import type { Output, PublishMode, PublishReceipt, PublishRequest } from '../domain/types';
import {
  demoAccount,
  formatBytes,
  formatDate,
  formatDuration,
  outputLabels,
} from '../domain/workspace';

function Receipt({ receipt }: { receipt: PublishReceipt }) {
  return (
    <div className="receipt">
      <h3>
        <Icon name="check" />
        {receipt.status === 'awaiting_confirmation' ? '预填完成 · 等待人工确认' : '已模拟提交发布'}
      </h3>
      <p>标题：{receipt.title}</p>
      <p>账号：抖音 · {demoAccount.name}（演示）</p>
      <div className="receipt-row">
        <span className="mono">{receipt.id}</span>
        <Badge status={receipt.status === 'awaiting_confirmation' ? 'waiting' : 'completed'}>
          {receipt.status === 'awaiting_confirmation' ? '待人工确认' : '已提交（模拟）'}
        </Badge>
      </div>
      <p>
        {formatDate(receipt.createdAt)} ·{' '}
        {receipt.mode === 'prefill' ? '实际接入后会停在电脑创作者发布页。' : '未操作真实账号。'}
      </p>
    </div>
  );
}

function PublishForm({ output }: { output: Output }) {
  const { snapshot, busy, execute } = useSnapshot();
  const [title, setTitle] = useState(output.title);
  const [caption, setCaption] = useState(output.caption);
  const [mode, setMode] = useState<PublishMode>('prefill');
  const [confirmed, setConfirmed] = useState(false);
  const [pending, setPending] = useState<PublishRequest | null>(null);
  const [showCover, setShowCover] = useState(false);
  const [completedId, setCompletedId] = useState<string | null>(null);
  const canSubmit = confirmed && !!title.trim() && !busy && output.kind !== 'draft';
  const receipt = snapshot.receipts.find((item) => item.id === completedId);

  function invalidate() {
    setConfirmed(false);
    setCompletedId(null);
  }
  async function submit(request: PublishRequest) {
    const updated = await execute(
      (repository) => repository.publish(request),
      request.mode === 'prefill' ? '已生成模拟预填回执' : '已生成模拟提交回执',
    );
    if (updated) {
      setPending(null);
      setConfirmed(false);
      setCompletedId(updated.receipts[0]!.id);
    }
  }
  function start() {
    if (!canSubmit) return;
    const request = {
      outputId: output.id,
      accountId: demoAccount.id,
      title,
      caption,
      mode,
      confirmed,
    };
    if (mode === 'direct') setPending(request);
    else void submit(request);
  }
  if (output.kind === 'draft')
    return (
      <div className="panel">
        <h2>这是剪映草稿</h2>
        <p className="setting-note">在剪映中完成画面、标题与关键帧检查，导出最终 MP4 后再发布。</p>
        <Notice>请从左侧选择“已确认成片”体验发布流程。当前没有打开实际剪映工程。</Notice>
      </div>
    );
  return (
    <>
      <form
        className="panel"
        onSubmit={(event) => {
          event.preventDefault();
          start();
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
              invalidate();
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
              invalidate();
            }}
          />
        </div>
        <div className="form-two-col">
          <div className="form-field">
            <span className="field-label">发布封面</span>
            <button type="button" className="radio-option" onClick={() => setShowCover(true)}>
              <Icon name="image" />
              <span>
                使用成片首帧<small>查看封面设置说明</small>
              </span>
            </button>
          </div>
          <div className="form-field">
            <span className="field-label">文件规格</span>
            <div className="radio-option">
              <Icon name="film" />
              <span>
                1080 × 1920 · MP4
                <small>
                  {formatDuration(output.durationSeconds)} ·{' '}
                  {output.sizeBytes === null ? '待实际生成' : formatBytes(output.sizeBytes)} ·
                  示例元数据
                </small>
              </span>
            </div>
          </div>
        </div>
        <h2 className="panel-title">
          <span className="step-marker">02</span>平台与账号
        </h2>
        <div className="publish-target">
          <span className="douyin-logo" aria-hidden="true">
            ♪
          </span>
          <div>
            <h3>抖音 · {demoAccount.name}</h3>
            <small>演示账号 {demoAccount.handle} · Chrome 插件</small>
          </div>
          <Badge>未连接</Badge>
        </div>
        <p className="field-help platform-help">首版优先接入抖音，小红书与视频号后续接入。</p>
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
                  invalidate();
                }}
              />
              <span>
                预填后，我来确认 <Badge>推荐</Badge>
                <small>在电脑发布页上传并填写信息，停在最终发布前。</small>
              </span>
            </label>
            <label className="radio-option">
              <input
                type="radio"
                name="publish-mode"
                checked={mode === 'direct'}
                onChange={() => {
                  setMode('direct');
                  invalidate();
                }}
              />
              <span>
                直接发布<small>确认本条成片、账号和文案后，再提交发布。</small>
              </span>
            </label>
          </div>
        </fieldset>
        {output.kind === 'preview' && (
          <Notice warm>
            这是预览 MP4，可能不含剪映后加的标题与特效。请确认它就是要发布的版本。
          </Notice>
        )}
        <label className="confirm-row">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(event) => setConfirmed(event.target.checked)}
          />
          <span>
            我已核对成片、封面、文案和目标账号
            {output.kind === 'preview' ? '，确认使用这份预览文件' : ''}。
          </span>
        </label>
        <Button type="submit" variant="primary" className="full" icon="send" disabled={!canSubmit}>
          {busy ? '正在生成回执…' : mode === 'prefill' ? '模拟预填发布页' : '模拟直接发布'}
        </Button>
        <p className="field-help centered">仅演示交互，不上传文件，也不操作真实账号。</p>
        {receipt && (
          <div aria-live="polite">
            <Receipt receipt={receipt} />
          </div>
        )}
      </form>
      {showCover && (
        <Dialog
          title="封面设置"
          subtitle="使用所选成片的首帧"
          onClose={() => setShowCover(false)}
          footer={
            <Button variant="primary" onClick={() => setShowCover(false)}>
              保留此设置
            </Button>
          }
        >
          <dl className="summary-list">
            <dt>成片</dt>
            <dd>{output.name}</dd>
            <dt>封面来源</dt>
            <dd>成片首帧</dd>
            <dt>画面比例</dt>
            <dd>9:16</dd>
          </dl>
          <Notice>接入视频文件后，这里会显示提取到的首帧，供你检查。</Notice>
        </Dialog>
      )}
      {pending && (
        <Dialog
          title="确认模拟直接发布"
          subtitle="请核对本条内容与目标账号。"
          onClose={() => setPending(null)}
          busy={busy}
          footer={
            <>
              <span>本次仅演示 1 条成片</span>
              <div>
                <Button disabled={busy} onClick={() => setPending(null)}>
                  返回检查
                </Button>
                <Button
                  variant="primary"
                  icon="send"
                  disabled={busy}
                  onClick={() => void submit(pending)}
                >
                  确认模拟提交
                </Button>
              </div>
            </>
          }
        >
          <dl className="summary-list">
            <dt>成片</dt>
            <dd>{output.name}</dd>
            <dt>标题</dt>
            <dd>{pending.title}</dd>
            <dt>文案</dt>
            <dd className="preserve-lines">{pending.caption || '无'}</dd>
            <dt>目标账号</dt>
            <dd>抖音 · {demoAccount.name}（演示）</dd>
            <dt>执行方式</dt>
            <dd>直接发布</dd>
          </dl>
          <Notice warm>仅生成模拟回执，不连接平台或发布真实内容。</Notice>
        </Dialog>
      )}
    </>
  );
}

export function PublishPage() {
  const { snapshot, mode, execute, busy, notify } = useSnapshot();
  const live = mode === 'live';
  const fileInput = useRef<HTMLInputElement>(null);
  const [params, setParams] = useSearchParams();
  const [history, setHistory] = useState(false);
  const selected =
    snapshot.outputs.find((output) => output.id === params.get('output')) ?? snapshot.outputs[0];
  return (
    <>
      <PageHeader title="成片与发布" subtitle="挑选确认好的成片，完成最后一次检查。">
        {live && (
          <>
            <Button icon="upload" disabled={busy} onClick={() => fileInput.current?.click()}>
              导入成片
            </Button>
            <input
              ref={fileInput}
              type="file"
              className="sr-only"
              aria-label="导入最终 MP4"
              accept=".mp4"
              onChange={async (event) => {
                const input = event.currentTarget;
                const file = input.files?.[0];
                if (!file) return;
                if (!/\.mp4$/i.test(file.name) || file.size <= 0 || file.size > 512 * 1024 * 1024) {
                  notify('请选择非空且不超过 512 MiB 的单个 MP4。');
                  input.value = '';
                  return;
                }
                const previous = new Set(snapshot.outputs.map((output) => output.id));
                const updated = await execute((repository) => {
                  if (!repository.importOutputs) throw new Error('当前仓库不支持导入成片。');
                  return repository.importOutputs([file]);
                }, '实际成片已导入，请播放核对后再发布');
                input.value = '';
                const imported = updated?.outputs.find((item) => !previous.has(item.id));
                if (imported) setParams({ output: imported.id });
              }}
            />
          </>
        )}
        <Button icon="clock" onClick={() => setHistory(true)}>
          发布记录
        </Button>
      </PageHeader>
      {selected ? (
        <div className="publish-layout">
          <aside className="publish-list" aria-label="选择产物">
            <div className="section-head">
              <h2>
                选择产物<small>{snapshot.outputs.length} 个</small>
              </h2>
            </div>
            {snapshot.outputs.map((output) => (
              <button
                key={output.id}
                className={`publish-item ${selected.id === output.id ? 'active' : ''}`}
                aria-pressed={selected.id === output.id}
                onClick={() => setParams({ output: output.id })}
              >
                <MaterialVisual
                  material={snapshot.materials.find(
                    (material) => material.id === output.materialId,
                  )}
                />
                <h3>{output.name}</h3>
                <small>
                  {formatDuration(output.durationSeconds)} ·{' '}
                  {output.sizeBytes === null && output.kind !== 'draft'
                    ? '待实际生成'
                    : formatBytes(output.sizeBytes)}
                </small>
                <div className="output-badge">
                  <Badge status={output.kind === 'final' ? 'completed' : ''}>
                    {outputLabels[output.kind]}
                  </Badge>
                </div>
              </button>
            ))}
          </aside>
          <section className="publish-form">
            {live ? (
              <LivePublishForm
                key={`${selected.id}:${selected.kind}:${selected.fileUrl ?? ''}:${selected.sizeBytes}:${selected.durationSeconds}`}
                output={selected}
              />
            ) : (
              <PublishForm key={selected.id} output={selected} />
            )}
          </section>
        </div>
      ) : (
        <EmptyState
          icon="send"
          title="暂无可选产物"
          description={
            live
              ? '导入实际 MP4 成片，或等待混剪任务生成预览后确认。发布仅支持单个 MP4，最大 512 MiB。'
              : '完成混剪后，再来核对成片和发布信息。'
          }
        />
      )}
      {live && (
        <section className="publish-queue" aria-label="真实发布队列">
          <h2 className="panel-title">
            真实发布队列 <small>{snapshot.receipts.length} 条</small>
          </h2>
          {snapshot.receipts.length ? (
            snapshot.receipts.map((receipt) => (
              <PublishReceiptCard key={receipt.id} receipt={receipt} />
            ))
          ) : (
            <p className="setting-note">
              尚未提交任务。队列状态每 3 秒刷新；入队不代表平台已发布。
            </p>
          )}
        </section>
      )}
      {history && (
        <Dialog
          title="发布记录"
          subtitle={live ? '服务端持久化队列与平台回执' : '本次页面会话的模拟回执'}
          onClose={() => setHistory(false)}
        >
          {snapshot.receipts.length ? (
            snapshot.receipts.map((receipt) =>
              live ? (
                <PublishReceiptCard key={receipt.id} receipt={receipt} />
              ) : (
                <Receipt key={receipt.id} receipt={receipt} />
              ),
            )
          ) : (
            <EmptyState
              icon="send"
              title="还没有发布记录"
              description={
                live
                  ? '逐条核对提交后，这里会显示真实队列状态。'
                  : '完成一次模拟预填或提交后，这里会显示回执。'
              }
            />
          )}
        </Dialog>
      )}
    </>
  );
}
