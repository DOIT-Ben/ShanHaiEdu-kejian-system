export type PptOutlinePage = {
  id: string;
  pageType: "content" | "cover" | "summary";
  source: string;
  task: string;
  title: string;
};

function isPptOutlinePage(value: unknown): value is Omit<PptOutlinePage, "pageType"> & {
  pageType?: PptOutlinePage["pageType"];
} {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const page = value as Record<string, unknown>;
  return (
    typeof page.id === "string" &&
    typeof page.title === "string" &&
    typeof page.task === "string" &&
    typeof page.source === "string" &&
    (page.pageType === undefined ||
      page.pageType === "content" ||
      page.pageType === "cover" ||
      page.pageType === "summary")
  );
}

export function readPptOutlinePages(value: unknown): PptOutlinePage[] | null {
  if (!Array.isArray(value) || value.length === 0 || !value.every(isPptOutlinePage)) return null;
  return value.map((page, index) => ({
    ...page,
    pageType:
      page.pageType ??
      (page.id === "cover"
        ? "cover"
        : page.id === "summary"
          ? "summary"
          : index === 0
            ? "cover"
            : index === value.length - 1
              ? "summary"
              : "content"),
  }));
}
