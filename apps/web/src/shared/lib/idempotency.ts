/**
 * 幂等键生成：用于创建模型运行、上传会话、交付打包与重试等
 * 非安全方法，满足 Idempotency-Key 头 16–128 字符要求。
 */
export function createIdempotencyKey(prefix = "web"): string {
  const cryptoApi = globalThis.crypto;
  if (cryptoApi?.randomUUID) {
    return `${prefix}-${cryptoApi.randomUUID()}`;
  }
  const bytes = new Uint8Array(16);
  cryptoApi.getRandomValues(bytes);
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${prefix}-${hex}`;
}
