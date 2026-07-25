import { Upload } from "lucide-react";
import { useRef, useState } from "react";
import {
  confirmMaterialUpload,
  createMaterialUploadSession,
  sha256File,
  uploadMaterialFile,
  type UploadSessionDto,
} from "@/features/materials/api/materialsApi";
import { validateTextbookFile } from "@/features/projects/lib/validateTextbookFile";
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { runtimeErrorMessage } from "@/shared/api/runtimeError";
import { Button } from "@/shared/ui/Button";

type UploadAttempt = {
  confirmIntent: string;
  etag?: string;
  fileKey: string;
  session?: UploadSessionDto;
  sha256?: string;
  uploadIntent: string;
};

function fileKey(file: File) {
  return [file.name, file.size, file.lastModified].join(":");
}

export function ProjectMaterialUploadPanel({
  onAccepted,
  projectId,
}: {
  onAccepted: (result: { jobId: string; materialId: string }) => void;
  projectId: string;
}) {
  const [file, setFile] = useState<File>();
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const attemptRef = useRef<UploadAttempt | undefined>(undefined);

  const selectFile = (next?: File) => {
    setFile(next);
    setMessage("");
    attemptRef.current = undefined;
  };

  const upload = async () => {
    if (!file) {
      setMessage("请选择一份 PDF 教材");
      return;
    }
    const validationError = validateTextbookFile(file);
    if (validationError) {
      setMessage(validationError);
      return;
    }
    const key = fileKey(file);
    const attempt =
      attemptRef.current?.fileKey === key
        ? attemptRef.current
        : {
            confirmIntent: crypto.randomUUID(),
            fileKey: key,
            uploadIntent: crypto.randomUUID(),
          };
    attemptRef.current = attempt;
    setMessage("正在核对教材");
    setPending(true);
    try {
      attempt.sha256 ??= await sha256File(file);
      attempt.session ??= await createMaterialUploadSession({
        idempotencyKey: attempt.uploadIntent,
        input: {
          filename: file.name,
          media_type: file.type || "application/pdf",
          sha256: attempt.sha256,
          size_bytes: file.size,
        },
        projectId,
      });
      setMessage("正在上传教材");
      attempt.etag ??= await uploadMaterialFile(attempt.session, file);
      setMessage("正在启动解析");
      const job = await confirmMaterialUpload({
        etag: attempt.etag,
        file,
        idempotencyKey: attempt.confirmIntent,
        materialId: attempt.session.material_id,
        projectId,
        sha256: attempt.sha256,
        uploadSessionId: attempt.session.upload_session_id,
      });
      onAccepted({ jobId: job.job_id, materialId: attempt.session.material_id });
    } catch (error) {
      setMessage(runtimeErrorMessage(error, "教材没有上传完成，请检查网络后重试。"));
      setPending(false);
    }
  };

  const writeReady = isCsrfTokenAvailable();
  return (
    <section
      aria-labelledby="project-material-upload-title"
      className="border-b border-[var(--sh-line-subtle)] pb-6"
    >
      <div className="flex items-center gap-2">
        <Upload aria-hidden="true" className="size-5 text-[var(--sh-brand-600)]" />
        <h2
          className="text-lg font-semibold text-[var(--sh-ink-strong)]"
          id="project-material-upload-title"
        >
          上传教材
        </h2>
      </div>
      <div className="mt-3 flex flex-wrap items-end gap-3">
        <label className="min-w-0 flex-1 text-sm font-medium text-[var(--sh-ink-default)]">
          选择教材 PDF
          <input
            accept="application/pdf,.pdf"
            className="mt-1 block h-10 w-full min-w-56 rounded-[var(--sh-radius-control)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] px-3 py-2 text-sm file:mr-3 file:border-0 file:bg-transparent file:font-medium"
            disabled={pending}
            onChange={(event) => selectFile(event.currentTarget.files?.[0])}
            type="file"
          />
        </label>
        <Button
          disabled={!writeReady || !file || pending}
          loading={pending}
          loadingText="正在上传教材"
          onClick={() => void upload()}
        >
          <Upload aria-hidden="true" />
          上传并解析教材
        </Button>
      </div>
      {message ? (
        <p
          className={`mt-3 text-sm ${pending ? "text-[var(--sh-ink-muted)]" : "text-[var(--sh-danger)]"}`}
          role={pending ? "status" : "alert"}
        >
          {message}
        </p>
      ) : null}
    </section>
  );
}
