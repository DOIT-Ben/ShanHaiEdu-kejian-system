import { useEffect, useMemo, useRef } from "react";

/** 防抖回调：等待 delay 毫秒无新调用后执行最后一次。 */
export function useDebouncedCallback<Args extends unknown[]>(
  callback: (...args: Args) => void,
  delay: number,
): { run: (...args: Args) => void; flush: () => void; cancel: () => void } {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastArgsRef = useRef<Args | null>(null);

  const api = useMemo(() => {
    const cancel = () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
    const flush = () => {
      if (timerRef.current && lastArgsRef.current) {
        cancel();
        callbackRef.current(...lastArgsRef.current);
        lastArgsRef.current = null;
      }
    };
    const run = (...args: Args) => {
      lastArgsRef.current = args;
      cancel();
      timerRef.current = setTimeout(() => {
        timerRef.current = null;
        if (lastArgsRef.current) {
          callbackRef.current(...lastArgsRef.current);
          lastArgsRef.current = null;
        }
      }, delay);
    };
    return { run, flush, cancel };
  }, [delay]);

  useEffect(() => api.cancel, [api]);
  return api;
}
