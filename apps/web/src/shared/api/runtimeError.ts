import { ApiError } from "@/shared/api/client";

export function runtimeErrorMessage(reason: unknown, fallback: string) {
  return reason instanceof ApiError ? reason.message : fallback;
}

export function isRuntimeConflict(reason: unknown) {
  return (
    reason instanceof ApiError &&
    (reason.code === "EDIT_CONFLICT" ||
      reason.code === "ARTIFACT_STATE_CONFLICT" ||
      reason.code === "IDEMPOTENCY_CONFLICT" ||
      reason.code === "HTTP_409")
  );
}
