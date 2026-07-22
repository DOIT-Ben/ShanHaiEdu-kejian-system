import { describe, expect, it } from "vitest";
import {
  MAX_TEXTBOOK_PDF_BYTES,
  validateTextbookFile,
} from "@/features/projects/lib/validateTextbookFile";

describe("validateTextbookFile", () => {
  it("accepts PDF files when the browser omits the MIME type", () => {
    expect(validateTextbookFile(new File(["pdf"], "教材.PDF", { type: "" }))).toBeNull();
  });

  it("rejects mismatched extensions and files over 100 MB", () => {
    expect(validateTextbookFile(new File(["pdf"], "教材.txt", { type: "application/pdf" }))).toBe(
      "目前只支持 PDF 教材",
    );
    const oversized = new File(["pdf"], "教材.pdf", {
      type: "application/pdf",
    });
    Object.defineProperty(oversized, "size", { value: MAX_TEXTBOOK_PDF_BYTES + 1 });
    expect(validateTextbookFile(oversized)).toBe("教材文件不能超过 100 MB");
  });

  it("accepts a PDF at the exact 100 MB boundary", () => {
    const boundaryFile = new File(["pdf"], "教材.pdf", { type: "application/pdf" });
    Object.defineProperty(boundaryFile, "size", { value: MAX_TEXTBOOK_PDF_BYTES });
    expect(validateTextbookFile(boundaryFile)).toBeNull();
  });
});
