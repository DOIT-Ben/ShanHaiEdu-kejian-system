import { http, HttpResponse } from "msw";
import { getDb, minutesAgo } from "../db";
import { api, fail, guard, ok, paginate, simulateLatency } from "./http";

export const assetHandlers = [
  http.get(api("/projects/:projectId/assets"), async ({ params, request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const projectId = String(params.projectId);
    if (!db.projects.has(projectId)) return fail(404, "NOT_FOUND", "项目不存在或不可访问。");
    const url = new URL(request.url);
    const type = url.searchParams.get("type");
    const status = url.searchParams.get("status");
    const sourceNodeKey = url.searchParams.get("source_node_key");
    const lessonId = url.searchParams.get("lesson_id");
    const keyword = url.searchParams.get("keyword")?.trim();
    const pageSize = Number.parseInt(url.searchParams.get("page_size") ?? "30", 10);

    let items = [...db.assets.values()].filter((record) => record.projectId === projectId).map((r) => r.asset);
    if (type) items = items.filter((a) => a.asset_type === type);
    if (status) items = items.filter((a) => a.status === status);
    if (sourceNodeKey) items = items.filter((a) => a.source_node_key === sourceNodeKey);
    if (lessonId) items = items.filter((a) => a.lesson_id === lessonId);
    if (keyword) items = items.filter((a) => a.name.includes(keyword));
    items.sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));
    const { page, nextCursor } = paginate(items, url.searchParams.get("cursor"), pageSize);
    return ok(page, { meta: { next_cursor: nextCursor } });
  }),

  http.get(api("/assets/:assetId"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const record = getDb().assets.get(String(params.assetId));
    if (!record) return fail(404, "NOT_FOUND", "资产不存在。");
    return ok({ asset: record.asset, versions: record.versions, usage_references: record.usage });
  }),

  http.post(api("/file-objects/:fileObjectId/download-authorizations"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const fileObjectId = String(params.fileObjectId);
    const fileName = db.fileNames.get(fileObjectId);
    if (!fileName) return fail(404, "NOT_FOUND", "文件不存在或已过期。");
    return ok(
      {
        url: `/api/v2/__mock-files/${fileObjectId}`,
        expires_at: minutesAgo(-10),
        file_name: fileName,
      },
      { status: 201 },
    );
  }),

  // Mock 文件下载端点（短期授权 URL 指向这里）
  http.get(api("/__mock-files/:fileObjectId"), ({ params }) => {
    const db = getDb();
    const fileObjectId = String(params.fileObjectId);
    const fileName = db.fileNames.get(fileObjectId);
    if (!fileName) return new HttpResponse(null, { status: 404 });
    const body = `ShanHaiEdu Mock 文件\n文件名：${fileName}\n文件ID：${fileObjectId}\n（Mock 模式下的示意文件，真实环境将返回正式产物。）`;
    return new HttpResponse(body, {
      status: 200,
      headers: {
        "Content-Type": "application/octet-stream",
        "Content-Disposition": `attachment; filename*=UTF-8''${encodeURIComponent(fileName)}`,
      },
    });
  }),
];
