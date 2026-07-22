export const MAX_TEXTBOOK_PDF_BYTES = 100 * 1024 * 1024;

export function validateTextbookFile(file: File) {
  const hasPdfExtension = file.name.toLowerCase().endsWith(".pdf");
  const hasSupportedMime = file.type === "application/pdf" || file.type === "";
  if (!hasPdfExtension || !hasSupportedMime) return "目前只支持 PDF 教材";
  if (file.size > MAX_TEXTBOOK_PDF_BYTES) return "教材文件不能超过 100 MB";
  return null;
}
