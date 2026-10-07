import { useRef, useState } from 'react';
import { useSnapshot } from '../app/workspace-context';
import { Icon } from '../components/Icon';
import { Button } from '../components/ui';

export function ImportFiles({ onImported }: { onImported: (ids: string[]) => void }) {
  const { snapshot, busy, execute, mode } = useSnapshot();
  const live = mode === 'live';
  const ref = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [path, setPath] = useState('');
  async function importFiles(files: File[]) {
    const previous = new Set(snapshot.materials.map((material) => material.id));
    const updated = await execute(
      (repository) => repository.importFiles(files),
      live ? '视频已复制并导入本地素材库' : `已登记 ${files.length} 个本地视频（示例模式）`,
    );
    if (updated)
      onImported(
        updated.materials
          .filter((material) => !previous.has(material.id))
          .map((material) => material.id),
      );
    if (ref.current) ref.current.value = '';
  }
  return (
    <>
      <div
        className={`import-zone ${dragging ? 'dragging' : ''}`}
        onDragOver={(event) => {
          event.preventDefault();
          if (!busy) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          if (!busy) void importFiles([...event.dataTransfer.files]);
        }}
      >
        <Icon name="upload" />
        <h3>拖入视频，或从电脑选择</h3>
        <p>
          {live
            ? 'MP4、MOV、M4V、AVI、MKV、WebM · 复制到本地工作台并探测实际视频信息。'
            : 'MP4、MOV、MKV、WebM · 当前仅登记文件名和大小，不上传文件。'}
        </p>
        <Button icon="plus" className="small" disabled={busy} onClick={() => ref.current?.click()}>
          {busy ? '正在导入…' : '选择本地视频'}
        </Button>
        <input
          ref={ref}
          className="sr-only"
          tabIndex={-1}
          type="file"
          aria-label="选择本地视频文件"
          accept={live ? '.mp4,.mov,.m4v,.avi,.mkv,.webm' : '.mp4,.mov,.mkv,.webm'}
          multiple
          onChange={(event) => {
            if (event.target.files?.length) void importFiles([...event.target.files]);
          }}
        />
      </div>
      {live && (
        <div className="form-field directory-import">
          <label htmlFor="import-directory">从本地目录导入</label>
          <input
            id="import-directory"
            value={path}
            placeholder="/本机/视频目录"
            onChange={(event) => setPath(event.target.value)}
            disabled={busy}
          />
          <p className="field-help">
            扫描本层视频；选择单个分析结果目录时，同时导入 report.json 与 scenes
            中的镜头。不递归扫描整个根目录，也不会自动扫描设置中的目录。
          </p>
          <Button
            disabled={busy || !path.trim()}
            onClick={async () => {
              const previous = new Set(snapshot.materials.map((material) => material.id));
              const updated = await execute((repository) => {
                if (!repository.importDirectory) throw new Error('当前仓库不支持目录导入。');
                return repository.importDirectory(path.trim());
              }, '目录素材与已有分析已导入');
              if (updated)
                onImported(
                  updated.materials.filter((item) => !previous.has(item.id)).map((item) => item.id),
                );
            }}
          >
            扫描并导入
          </Button>
        </div>
      )}
    </>
  );
}
