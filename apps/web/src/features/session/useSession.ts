import { useCallback, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import {
  client,
  AppError,
  qk,
  SESSION_EXPIRED_EVENT,
  setCsrfToken,
  unwrap,
} from "@/shared/api";
import type { User } from "@/shared/api/types";

/** 会话查询：应用启动时恢复会话；401 视为未登录而非错误。 */
export function useSession() {
  return useQuery({
    queryKey: qk.session,
    queryFn: async (): Promise<{ user: User; csrfToken: string } | null> => {
      try {
        const result = await client.GET("/auth/me");
        const { data } = unwrap(result);
        setCsrfToken(data.csrf_token);
        return { user: data.user, csrfToken: data.csrf_token };
      } catch (error) {
        if (error instanceof AppError && error.isSessionExpired) {
          setCsrfToken(null);
          return null;
        }
        throw error;
      }
    },
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { identifier: string; password: string }) => {
      const result = await client.POST("/auth/login", { body: input });
      const { data } = unwrap(result);
      setCsrfToken(data.csrf_token);
      return { user: data.user, csrfToken: data.csrf_token };
    },
    onSuccess: (session) => {
      queryClient.setQueryData(qk.session, session);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: async () => {
      await client.POST("/auth/logout");
    },
    onSettled: () => {
      setCsrfToken(null);
      queryClient.setQueryData(qk.session, null);
      queryClient.removeQueries({ predicate: (query) => query.queryKey !== qk.session });
      void navigate("/login", { replace: true });
    },
  });
}

/** 监听 401 会话过期事件：清空会话并跳转登录（带回跳地址）。 */
export function useSessionExpiryRedirect() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const handler = useCallback(() => {
    setCsrfToken(null);
    queryClient.setQueryData(qk.session, null);
    const current = `${window.location.pathname}${window.location.search}`;
    if (!current.startsWith("/login")) {
      void navigate(`/login?redirect=${encodeURIComponent(current)}`, { replace: true });
    }
  }, [navigate, queryClient]);

  useEffect(() => {
    window.addEventListener(SESSION_EXPIRED_EVENT, handler);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handler);
  }, [handler]);
}
