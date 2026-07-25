import { useMutation } from "@tanstack/react-query";
import { useRef } from "react";
import {
  reviewArtifactVersion,
  startArtifactVersionQualityValidation,
} from "@/features/artifacts/api/artifactsApi";

type ApprovalMutationOptions = {
  artifactVersionId?: string;
  comment: string;
  missingVersionError: string;
  refetchArtifact: () => Promise<unknown>;
};

export function useArtifactApprovalMutation({
  artifactVersionId,
  comment,
  missingVersionError,
  refetchArtifact,
}: ApprovalMutationOptions) {
  const intentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: () => {
      if (!artifactVersionId) throw new Error(missingVersionError);
      intentRef.current ??= crypto.randomUUID();
      return reviewArtifactVersion({
        artifactVersionId,
        idempotencyKey: intentRef.current,
        input: { action: "approve", comment },
      });
    },
    onSuccess: async () => {
      intentRef.current = undefined;
      await refetchArtifact();
    },
  });
}

type QualityMutationOptions = {
  artifactVersionId?: string;
  missingVersionError: string;
  onRequested?: (versionId: string) => void;
};

export function useArtifactQualityMutation({
  artifactVersionId,
  missingVersionError,
  onRequested,
}: QualityMutationOptions) {
  const intentRef = useRef<string | undefined>(undefined);
  const requestedVersionRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: () => {
      if (!artifactVersionId) throw new Error(missingVersionError);
      intentRef.current ??= crypto.randomUUID();
      requestedVersionRef.current = artifactVersionId;
      return startArtifactVersionQualityValidation({
        artifactVersionId,
        idempotencyKey: intentRef.current,
      });
    },
    onSuccess: () => {
      const versionId = requestedVersionRef.current;
      intentRef.current = undefined;
      requestedVersionRef.current = undefined;
      if (versionId) onRequested?.(versionId);
    },
  });
}
