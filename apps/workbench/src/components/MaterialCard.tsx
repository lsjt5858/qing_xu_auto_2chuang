import { Link } from 'react-router-dom';
import type { Material } from '../domain/types';
import {
  formatBytes,
  formatDate,
  formatDuration,
  materialLabels,
  materialStatusLabels,
} from '../domain/workspace';
import { Icon } from './Icon';

export function MaterialVisual({ material }: { material?: Material }) {
  if (material?.fileUrl && material.kind !== 'image')
    return (
      <video
        className="material-thumbnail"
        src={material.fileUrl}
        preload="metadata"
        muted
        playsInline
        aria-label={`${material.name}缩略预览`}
      />
    );
  return (
    <div className={`asset-data asset-tone-${material?.tone ?? 0}`}>
      <div className="asset-data-top">
        <Icon name={material?.kind === 'image' ? 'image' : 'film'} />
        <span>{material?.source === 'local' ? 'LOCAL FILE' : 'JINGFLOW / ASSET'}</span>
      </div>
      <div className="asset-data-title">{material?.category ?? '素材信息'}</div>
      <div className="asset-data-bottom">
        <span>
          {material?.source === 'local' ? materialStatusLabels[material.status] : '青序内容工作室'}
        </span>
        <span>素材信息视图</span>
      </div>
    </div>
  );
}

export function MaterialCard({
  material,
  selected,
  onSelect,
}: {
  material: Material;
  selected?: boolean;
  onSelect?: (id: string, checked: boolean) => void;
}) {
  return (
    <article className={`media-card ${onSelect ? 'has-select' : ''} ${selected ? 'selected' : ''}`}>
      <div className="media-image">
        <MaterialVisual material={material} />
        <Link
          className="media-open"
          aria-label={`查看${material.name}`}
          to={`/library?material=${material.id}`}
        />
        {onSelect && (
          <input
            className="select-check"
            type="checkbox"
            aria-label={`选择${material.name}`}
            checked={selected ?? false}
            onChange={(event) => onSelect(material.id, event.target.checked)}
          />
        )}
        <span className="media-kind">{materialLabels[material.kind]}</span>
        <span className="duration">
          {material.kind === 'image' ? '照片' : formatDuration(material.durationSeconds)}
        </span>
      </div>
      <h3 className="media-title" title={material.name}>
        {material.name}
      </h3>
      <div className="media-meta">
        <span>
          {formatDate(material.createdAt)} · {formatBytes(material.sizeBytes)}
        </span>
        <span>
          {material.status === 'analyzed' && <Icon name="check" />}
          {materialStatusLabels[material.status]}
        </span>
      </div>
    </article>
  );
}
