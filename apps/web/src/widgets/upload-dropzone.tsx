import { useRef, useState, type DragEvent } from "react";
import { FileUp, Loader2 } from "lucide-react";
import { formatFileSize } from "@/shared/lib/format";
import { cn } from "@/shared/lib/cn";

/**
 * 上传拖放区：点击或拖拽上传，前端先做大小/类型校验。
 */
export function UploadDropzone({
  accept,
  maxSizeBytes = 200 * 1024 * 1024,
  hint,
  uploading,
  onFile,
  className,
}: {
  accept: string;
  maxSizeBytes?: number;
  hint?: string;
  uploading?: boolean;
  onFile: (file: File) => void;
  className?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const acceptList = accept.split(",").map((item) => item.trim().toLowerCase());

  const validate = (file: File): string | null => {
    const extension = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
    const typeOk = acceptList.some((item) => (item.startsWith(".") ? item === extension : file.type === item));
    if (!typeOk) return `不支持的文件类型，仅支持 ${accept}`;
    if (file.size > maxSizeBytes) return `文件超过 ${formatFileSize(maxSizeBytes)} 的大小限制`;
    return null;
  };

  const handleFile = (file: File | undefined) => {
    if (!file) return;
    const error = validate(file);
    setLocalError(error);
    if (!error) onFile(file);
  };

  const handleDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragOver(false);
    handleFile(event.dataTransfer.files[0]);
  };

  return (
    <div className={className}>
      <button
        type="button"
        disabled={uploading}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={cn(
          "flex w-full flex-col items-center justify-center gap-2 rounded-panel border-2 border-dashed px-6 py-10 transition-colors",
          dragOver ? "border-brand bg-brand-selected" : "border-line bg-surface-2 hover:border-ink-muted",
          uploading ? "cursor-wait opacity-70" : "",
        )}
      >
        {uploading ? (
          <Loader2 className="size-7 animate-spin text-brand" aria-hidden />
        ) : (
          <FileUp className="size-7 text-ink-muted" aria-hidden />
        )}
        <span className="text-sm font-medium text-ink-1">{uploading ? "正在上传…" : "点击选择文件，或拖拽到这里"}</span>
        <span className="text-xs text-ink-muted">{hint ?? `支持 ${accept}，单个文件不超过 ${formatFileSize(maxSizeBytes)}`}</span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(event) => {
          handleFile(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
      {localError ? (
        <p role="alert" className="mt-2 text-sm text-danger">
          {localError}
        </p>
      ) : null}
    </div>
  );
}
