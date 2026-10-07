import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useSnapshot } from '../app/workspace-context';
import { Icon } from '../components/Icon';
import { MaterialCard, MaterialVisual } from '../components/MaterialCard';
import { Badge, Button, EmptyState, PageHeader, SearchField } from '../components/ui';
import type { MaterialKind } from '../domain/types';
import {
  formatBytes,
  formatDate,
  formatDuration,
  materialLabels,
  materialStatusLabels,
} from '../domain/workspace';

const filters: { key: MaterialKind | 'all'; title: string }[] = [
  { key: 'all', title: '全部素材' },
  { key: 'video', title: '原始视频' },
  { key: 'shot', title: '镜头片段' },
  { key: 'image', title: '作品照片' },
];

export function LibraryPage() {
  const { snapshot, notify } = useSnapshot();
  const [params, setParams] = useSearchParams();
  const filter = params.get('type') ?? 'all';
  const query = params.get('q') ?? '';
  const listView = params.get('view') === 'list';
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const selectAll = useRef<HTMLInputElement>(null);
  const filtered = snapshot.materials.filter(
    (material) =>
      (filter === 'all' || material.kind === filter) &&
      material.name.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
  );
  const selectedInView = filtered.filter((material) => selected.has(material.id)).length;
  useEffect(() => {
    if (selectAll.current)
      selectAll.current.indeterminate = selectedInView > 0 && selectedInView < filtered.length;
  }, [selectedInView, filtered.length]);
  function updateParam(key: string, value: string) {
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      },
      { replace: true },
    );
  }
  function select(id: string, checked: boolean) {
    setSelected((previous) => {
      const next = new Set(previous);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }
  function createTask() {
    const ids = snapshot.materials
      .filter((material) => selected.has(material.id) && material.kind !== 'image')
      .map((material) => material.id);
    if (!ids.length) {
      notify('请选择视频或镜头片段创建处理任务。');
      return;
    }
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      next.set('create', '1');
      next.set('materials', ids.join(','));
      return next;
    });
  }
  return (
    <>
      <PageHeader title="素材库" subtitle="把原片、镜头和作品放在一起，随时开始下一次创作。">
        <Link className="button primary" to="?import=1">
          <Icon name="upload" />
          导入素材
        </Link>
      </PageHeader>
      <div className="filter-bar">
        <div className="tabs" aria-label="素材类型">
          {filters.map((item) => (
            <button
              className={`tab ${filter === item.key ? 'active' : ''}`}
              key={item.key}
              aria-pressed={filter === item.key}
              onClick={() => updateParam('type', item.key)}
            >
              {item.title}
              <small>
                {
                  snapshot.materials.filter(
                    (material) => item.key === 'all' || material.kind === item.key,
                  ).length
                }
              </small>
            </button>
          ))}
        </div>
        <div className="toolbar">
          <SearchField
            label="搜索素材名称"
            value={query}
            onChange={(value) => updateParam('q', value)}
          />
          <div className="view-switch">
            <button
              title="网格视图"
              aria-label="网格视图"
              aria-pressed={!listView}
              className={!listView ? 'active' : ''}
              onClick={() => updateParam('view', 'grid')}
            >
              <Icon name="home" />
            </button>
            <button
              title="列表视图"
              aria-label="列表视图"
              aria-pressed={listView}
              className={listView ? 'active' : ''}
              onClick={() => updateParam('view', 'list')}
            >
              <Icon name="list" />
            </button>
          </div>
        </div>
      </div>
      <div className="sub-toolbar">
        <label className="check-label">
          <input
            ref={selectAll}
            type="checkbox"
            className="select-check"
            disabled={!filtered.length}
            checked={filtered.length > 0 && selectedInView === filtered.length}
            onChange={(event) => {
              const checked = event.target.checked;
              setSelected((previous) => {
                const next = new Set(previous);
                filtered.forEach((material) =>
                  checked ? next.add(material.id) : next.delete(material.id),
                );
                return next;
              });
            }}
          />
          全选当前结果 · {filtered.length} 份素材
        </label>
        <span>导入时间 · 最新优先</span>
      </div>
      {!filtered.length ? (
        <EmptyState
          icon="search"
          title="没有找到匹配的素材"
          description="换个关键词，或切换素材分类。"
        >
          <Button onClick={() => setParams({})}>清除筛选</Button>
        </EmptyState>
      ) : listView ? (
        <div className="table-wrap" tabIndex={0} role="region" aria-label="素材列表">
          <table>
            <thead>
              <tr>
                <th>
                  <span className="sr-only">选择</span>
                </th>
                <th scope="col">素材名称</th>
                <th scope="col">类型</th>
                <th scope="col">时长 / 大小</th>
                <th scope="col">状态</th>
                <th scope="col">操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((material) => (
                <tr key={material.id}>
                  <td>
                    <input
                      className="select-check"
                      type="checkbox"
                      checked={selected.has(material.id)}
                      onChange={(event) => select(material.id, event.target.checked)}
                      aria-label={`选择${material.name}`}
                    />
                  </td>
                  <td>
                    <div className="table-name">
                      <MaterialVisual material={material} />
                      <Link to={`?material=${material.id}`}>
                        {material.name}
                        <small>{formatDate(material.createdAt)}</small>
                      </Link>
                    </div>
                  </td>
                  <td>{materialLabels[material.kind]}</td>
                  <td className="muted">
                    {material.kind === 'image' ? '照片' : formatDuration(material.durationSeconds)}{' '}
                    / {formatBytes(material.sizeBytes)}
                  </td>
                  <td>
                    <Badge status={material.status === 'pending' ? 'queued' : 'completed'}>
                      {materialStatusLabels[material.status]}
                    </Badge>
                  </td>
                  <td>
                    <Link className="button small" to={`?material=${material.id}`}>
                      详情
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="media-grid library-grid">
          {filtered.map((material) => (
            <MaterialCard
              key={material.id}
              material={material}
              selected={selected.has(material.id)}
              onSelect={select}
            />
          ))}
        </div>
      )}
      {selected.size > 0 && (
        <div className="selection-bar">
          <Icon name="check" />
          <span>已选择 {selected.size} 份素材</span>
          <Button variant="ghost" className="small" onClick={() => setSelected(new Set())}>
            取消选择
          </Button>
          <Button variant="primary" className="small" icon="plus" onClick={createTask}>
            创建处理任务
          </Button>
        </div>
      )}
    </>
  );
}
