// @vitest-environment node
import { describe, expect, it } from 'vitest';
import { ChunkReceiver, encodedChunks } from '../src/transfer';
import { CHUNK_BYTES, MAX_FILE_BYTES } from '../src/protocol';

describe('256 KiB JSON 文件传输', () => {
  it('顺序分块重组 File，字节、名字、类型保持一致', async () => {
    const bytes = new Uint8Array(CHUNK_BYTES + 17).map((_, i) => i % 251);
    const receiver = new ChunkReceiver('clip.mp4', bytes.length);
    let count = 0;
    for await (const chunk of encodedChunks(new Blob([bytes]))) {
      receiver.add(chunk.index, chunk.data);
      count++;
    }
    const file = receiver.finish();
    expect(count).toBe(2);
    expect(file.name).toBe('clip.mp4');
    expect(file.type).toBe('video/mp4');
    expect(new Uint8Array(await file.arrayBuffer())).toEqual(bytes);
    expect(() => receiver.finish()).toThrow(/重复/);
  });
  it('乱序、重复、缺块、越界和非法编码不能上传', () => {
    expect(() => new ChunkReceiver('x.mp4', MAX_FILE_BYTES + 1)).toThrow(/512/);
    const receiver = new ChunkReceiver('x.mp4', 4);
    expect(() => receiver.add(1, 'dGVzdA==')).toThrow(/顺序/);
    expect(() => receiver.add(0, '@')).toThrow(/编码/);
    expect(() => receiver.finish()).toThrow(/不完整/);
    receiver.add(0, 'dGVzdA==');
    expect(() => receiver.add(0, 'dGVzdA==')).toThrow(/顺序/);
    expect(() => receiver.add(1, 'YQ==')).toThrow(/大小/);
  });
});
