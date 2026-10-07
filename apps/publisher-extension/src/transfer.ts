import { CHUNK_BYTES, fileSize, requireThat } from './protocol';

export interface EncodedChunk {
  index: number;
  data: string;
}

function base64(bytes: Uint8Array): string {
  let binary = '';
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return btoa(binary);
}

function decode(value: string): Uint8Array {
  requireThat(value.length > 0 && /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value),
    'encoding', '分块编码无效');
  let binary: string;
  try {
    binary = atob(value);
  } catch {
    throw new Error('分块编码无效');
  }
  return Uint8Array.from(binary, character => character.charCodeAt(0));
}

function mime(name: string): string {
  const extension = name.split('.').pop()?.toLowerCase();
  const values: Record<string, string> = {
    mp4: 'video/mp4',
    mov: 'video/quicktime',
    webm: 'video/webm',
    m4v: 'video/x-m4v',
  };
  requireThat(Boolean(extension && values[extension]), 'format', '不支持的视频文件格式');
  return values[extension!];
}

export async function* encodedChunks(blob: Blob): AsyncGenerator<EncodedChunk> {
  fileSize(blob.size);
  for (let offset = 0, index = 0; offset < blob.size; offset += CHUNK_BYTES, index++) {
    const bytes = new Uint8Array(await blob.slice(offset, offset + CHUNK_BYTES).arrayBuffer());
    yield { index, data: base64(bytes) };
  }
}

export class ChunkReceiver {
  private readonly parts: ArrayBuffer[] = [];
  private received = 0;
  private complete = false;

  constructor(private readonly name: string, private readonly expectedSize: number) {
    fileSize(expectedSize);
    requireThat(Boolean(name) && !/[/\\\x00-\x1f]/.test(name), 'filename', '文件名无效');
    mime(name);
  }

  add(index: number, data: string): void {
    requireThat(!this.complete, 'duplicate', '文件已完成，拒绝重复分块');
    requireThat(Number.isSafeInteger(index) && index === this.parts.length, 'order', '分块必须按顺序且不能重复');
    const bytes = decode(data);
    requireThat(this.received + bytes.length <= this.expectedSize, 'size', '分块总大小超过声明大小');
    const part = new Uint8Array(bytes.length);
    part.set(bytes);
    this.parts.push(part.buffer);
    this.received += bytes.length;
  }

  finish(): File {
    requireThat(!this.complete, 'duplicate', '文件已完成，拒绝重复结束');
    requireThat(this.received === this.expectedSize, 'incomplete', '文件分块不完整');
    this.complete = true;
    return new File(this.parts, this.name, { type: mime(this.name) });
  }
}
