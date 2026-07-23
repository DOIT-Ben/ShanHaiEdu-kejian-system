export type DownloadRemoteFileOptions = {
  acceptedMimeTypes: readonly string[];
  filename: string;
  url: string;
};

export type RemoteFileDownloadFailure =
  "empty_file" | "network" | "unavailable" | "unsupported_type";

export class RemoteFileDownloadError extends Error {
  readonly reason: RemoteFileDownloadFailure;

  constructor(reason: RemoteFileDownloadFailure) {
    super(reason);
    this.name = "RemoteFileDownloadError";
    this.reason = reason;
  }
}

function normalizedMimeType(value: string) {
  return value.split(";", 1)[0]?.trim().toLowerCase() ?? "";
}

function matchesMimeType(actual: string, accepted: string) {
  const normalizedAccepted = normalizedMimeType(accepted);
  if (normalizedAccepted.endsWith("/*")) {
    return actual.startsWith(normalizedAccepted.slice(0, -1));
  }
  return actual === normalizedAccepted;
}

function safeFilename(filename: string) {
  return Array.from(filename, (character) =>
    character.charCodeAt(0) < 32 || '<>:"/\\|?*'.includes(character) ? "-" : character,
  ).join("");
}

export async function downloadRemoteFile({
  acceptedMimeTypes,
  filename,
  url,
}: DownloadRemoteFileOptions) {
  let response: Response;
  try {
    response = await fetch(url, {
      headers: { Accept: acceptedMimeTypes.join(", ") },
    });
  } catch {
    throw new RemoteFileDownloadError("network");
  }

  if (!response.ok) {
    throw new RemoteFileDownloadError("unavailable");
  }

  const blob = await response.blob();
  if (blob.size === 0) {
    throw new RemoteFileDownloadError("empty_file");
  }

  const mimeType = normalizedMimeType(response.headers.get("content-type") ?? blob.type);
  if (!mimeType || !acceptedMimeTypes.some((accepted) => matchesMimeType(mimeType, accepted))) {
    throw new RemoteFileDownloadError("unsupported_type");
  }

  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.download = safeFilename(filename);
  anchor.href = objectUrl;
  anchor.hidden = true;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
}
