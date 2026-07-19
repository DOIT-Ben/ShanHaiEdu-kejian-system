export function requiredItem<T>(items: readonly T[], index: number, label: string): T {
  const item = items[index];
  if (item === undefined) {
    throw new Error(`${label}不存在`);
  }
  return item;
}
