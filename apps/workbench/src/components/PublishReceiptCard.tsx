import { useSnapshot } from '../app/workspace-context';
import type { PublishReceipt } from '../domain/types';
import { formatDate } from '../domain/workspace';
import { Badge, Button, Notice } from './ui';

const labels: Record<PublishReceipt['status'], string> = {
  queued: '排队中',
  uploading: '正在上传',
  filling: '正在填写',
  submitting: '正在提交，勿重复操作',
  awaiting_confirmation: '预填完成，待平台人工确认',
  submitted: '已提交（有平台证据）',
  blocked: '已阻塞，需人工处理',
  unknown: '结果未知，需人工核查',
  cancelled: '本地队列已取消',
};

export function PublishReceiptCard({ receipt }: { receipt: PublishReceipt }) {
  const { snapshot, execute, busy } = useSnapshot();
  const cancellable = ['queued', 'blocked', 'awaiting_confirmation'].includes(receipt.status);
  return (
    <article className="receipt">
      <h3>{labels[receipt.status]}</h3>
      <p>标题：{receipt.title}</p>
      <p>
        账号：抖音 ·{' '}
        {receipt.accountName ??
          snapshot.accounts?.find((account) => account.id === receipt.accountId)?.name ??
          receipt.accountId}
      </p>
      <div className="receipt-row">
        <span className="mono">{receipt.id}</span>
        <Badge
          status={
            receipt.status === 'submitted'
              ? 'completed'
              : receipt.status === 'unknown' || receipt.status === 'blocked'
                ? 'failed'
                : 'waiting'
          }
        >
          {receipt.mode === 'prefill' ? '预填' : '直接发布'}
          {receipt.simulated ? ' · 模拟' : ' · 真实队列'}
        </Badge>
      </div>
      <p>{formatDate(receipt.updatedAt ?? receipt.createdAt)}</p>
      {receipt.message && <p className="preserve-lines">{receipt.message}</p>}
      {receipt.evidence && <p className="receipt-evidence">平台证据：{receipt.evidence}</p>}
      {['unknown', 'submitting', 'blocked'].includes(receipt.status) && (
        <Notice warm>请核查插件 runner 和平台页面，不要重复提交；工作台不自动重试发布。</Notice>
      )}
      {receipt.status === 'awaiting_confirmation' && (
        <Notice>
          请到已选择的抖音发布页检查并手动确认。工作台不会代替你点击最终发布，也不会推断人工提交结果。
        </Notice>
      )}
      {cancellable && !receipt.simulated && (
        <Button
          className="small"
          disabled={busy}
          onClick={() =>
            void execute((repository) => {
              if (!repository.cancelPublish) throw new Error('当前仓库不支持取消发布。');
              return repository.cancelPublish(receipt.id);
            }, '本地发布任务已取消，请手动检查平台已有内容')
          }
        >
          取消本地发布任务
        </Button>
      )}
    </article>
  );
}
