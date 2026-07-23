export function validateTextbookFile(file: File) {
  const hasPdfExtension = file.name.toLowerCase().endsWith(".pdf");
  const hasSupportedMime = file.type === "application/pdf" || file.type === "";
  if (!hasPdfExtension || !hasSupportedMime) return "目前只支持 PDF 教材";
  if (file.size < 1) return "教材文件不能为空";
  return null;
}
