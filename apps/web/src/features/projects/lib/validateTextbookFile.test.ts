import { describe, expect, it } from "vitest";
import { validateTextbookFile } from "@/features/projects/lib/validateTextbookFile";

describe("validateTextbookFile", () => {
  it("accepts PDF files when the browser omits the MIME type", () => {
    expect(validateTextbookFile(new File(["pdf"], "教材.PDF", { type: "" }))).toBeNull();
  });

  it("rejects mismatched extensions and empty PDFs", () => {
    expect(validateTextbookFile(new File(["pdf"], "教材.txt", { type: "application/pdf" }))).toBe(
      "目前只支持 PDF 教材",
    );
    expect(validateTextbookFile(new File([], "教材.pdf", { type: "application/pdf" }))).toBe(
      "教材文件不能为空",
    );
  });

  it("leaves deployment-specific upload limits to the server", () => {
    const largeFile = new File(["pdf"], "教材.pdf", { type: "application/pdf" });
    Object.defineProperty(largeFile, "size", { value: 100 * 1024 * 1024 + 1 });
    expect(validateTextbookFile(largeFile)).toBeNull();
  });
});
