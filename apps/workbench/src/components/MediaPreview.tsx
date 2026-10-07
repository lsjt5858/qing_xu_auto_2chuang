import { useState } from 'react';
import { Notice } from './ui';

export function MediaPreview({
  src,
  name,
  onReadyChange,
}: {
  src: string;
  name: string;
  onReadyChange?: (ready: boolean) => void;
}) {
  const [failed, setFailed] = useState(false);
  return (
    <div className="media-preview">
      <video
        className="actual-video"
        src={src}
        controls
        preload="auto"
        playsInline
        aria-label={`视频预览：${name}`}
        onLoadedData={() => {
          setFailed(false);
          onReadyChange?.(true);
        }}
        onError={() => {
          setFailed(true);
          onReadyChange?.(false);
        }}
      />
      {failed && (
        <Notice warm>
          无法播放此文件。请检查本地服务、文件是否存在及浏览器编码支持；可下载后检查。
        </Notice>
      )}
      <a className="button small" href={src} download={name}>
        下载原文件
      </a>
    </div>
  );
}
