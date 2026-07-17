import { test, expect, type Page } from "@playwright/test";

/**
 * 关键教师流程（docs/frontend/08 验收清单）。
 * mock 世界通过 ?login=demo 预登录教师，每个测试独立页面上下文。
 */

const PROJECT = "00000000-0000-4000-8000-000000000101";
const LESSON = "00000000-0000-4000-8000-000000000202";

async function gotoDemo(page: Page, path: string) {
  const joiner = path.includes("?") ? "&" : "?";
  await page.goto(`${path}${joiner}login=demo`);
}

test("登录页 → 首页：账号密码登录", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "教师 林晓雨" }).click();
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page.getByRole("heading", { name: "把一份教材，变成完整的课堂作品" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "主导航" })).toContainText("创作中心");
});

test("项目总览：课时进度与分支状态使用教师语言", async ({ page }) => {
  await gotoDemo(page, `/app/projects/${PROJECT}`);
  await expect(page.getByRole("heading", { name: "认识几分之几", level: 1 })).toBeVisible();
  const lesson2 = page.getByRole("link", { name: /认识几分之几.*理解几分之几的含义/ });
  await expect(lesson2).toContainText("等待确认");
  await expect(lesson2).not.toContainText("review_required");
});

test("教案确认：警告需逐条确认，批准后只读", async ({ page }) => {
  await gotoDemo(page, `/app/projects/${PROJECT}/lessons/${LESSON}/work/lesson-plan-confirm`);
  // 十二部分由内容定义驱动渲染
  await expect(page.getByRole("heading", { name: "一、教学内容" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "十二、教学反思" })).toBeVisible();

  await page.getByRole("button", { name: "确认教案" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("确认校验提醒");
  await expect(dialog.getByRole("button", { name: "确认并批准" })).toBeDisabled();
  await dialog.getByRole("checkbox").first().check();
  await dialog.getByRole("textbox").fill("练习环节可压缩，保留安排。");
  await dialog.getByRole("button", { name: "确认并批准" }).click();

  await expect(page.getByText("已批准（批准后内容只读")).toBeVisible();
  await expect(page.getByRole("button", { name: "确认教案" })).toHaveCount(0);
});

test("三类九套：九套方案展示完整提示词，可选择并解锁视频", async ({ page }) => {
  await gotoDemo(page, `/app/projects/${PROJECT}/lessons/${LESSON}/work/intro-options`);
  // 3 类 × 3 套
  for (const category of ["科普", "应用", "故事"]) {
    await expect(page.getByRole("heading", { name: category, exact: true })).toBeVisible();
  }
  await expect(page.getByRole("button", { name: "修改这套" })).toHaveCount(9);

  await gotoDemo(page, `/app/projects/${PROJECT}/lessons/${LESSON}/work/intro-selection`);
  await page.getByRole("button", { name: "改用这套" }).first().click();
  await page.getByRole("dialog").getByRole("button", { name: "确定使用" }).click();
  await expect(page.getByText(/已选择「/)).toBeVisible();
});

test("PPT：封面未定则正文被门禁；采用封面后正文解锁并可编辑保存", async ({ page }) => {
  await gotoDemo(page, `/app/projects/${PROJECT}/lessons/${LESSON}/work/ppt-body`);
  await expect(page.getByText("请先确定封面风格")).toBeVisible();

  await page.getByRole("link", { name: "去设计封面" }).click();
  await page.getByRole("button", { name: "采用这个封面" }).first().click();
  await page.getByRole("dialog").getByRole("button", { name: "保存到项目" }).click();
  await expect(page.getByText("封面已确定，画面风格已生效")).toBeVisible();

  await page.getByRole("link", { name: "去制作正文" }).click();
  await expect(page.getByText("正文页 · 纯白底色（不可更改）")).toBeVisible();
  const title = page.locator("textarea").first();
  await title.fill("剩下的披萨怎么表示？（修订）");
  await page.getByRole("button", { name: "保存修改" }).click();
  await expect(page.getByRole("button", { name: "保存修改" })).toBeDisabled();
});

test("视频片段：失败镜头就地重试，互不影响", async ({ page }) => {
  await gotoDemo(page, `/app/projects/${PROJECT}/lessons/${LESSON}/work/video-clips`);
  await expect(page.getByText("1/3 已采用")).toBeVisible();
  // 自动定位到失败镜头
  await expect(page.getByText("模型服务返回画面缺陷")).toBeVisible();
  await expect(page.getByRole("button", { name: "重试本镜头" })).toBeVisible();
  // 提示词完整可见
  await expect(page.getByText(/参考\[图1\]/)).toBeVisible();
});

test("项目交付：就绪检查与打包入口", async ({ page }) => {
  await gotoDemo(page, `/app/projects/${PROJECT}/delivery`);
  await expect(page.getByRole("heading", { name: "交付检查" })).toBeVisible();
  await expect(page.getByText("待完成").first()).toBeVisible();
  // 有未完成分支时不能打包
  await expect(page.getByRole("button", { name: "打包全部成果" })).toBeDisabled();
});

test("创作中心：独立图片创作 生成→采用→保存 全链", async ({ page }) => {
  await gotoDemo(page, "/app/creation");
  await page.getByRole("link", { name: /制作图片/ }).click();
  await expect(page).toHaveURL(/batch=/);

  await page.getByRole("textbox").fill("分数墙示意图：把 1 平均分成 2、3、4、6 份的彩色条形对比。");
  await page.getByRole("button", { name: "开始生成" }).click();
  await expect(page.getByRole("button", { name: "采用并保存到项目" }).first()).toBeVisible({ timeout: 20_000 });

  await page.getByRole("button", { name: "采用并保存到项目" }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("保存到项目");
  await dialog.getByLabel("选择项目").click();
  await page.getByRole("option", { name: "认识几分之几" }).click();
  await dialog.getByRole("button", { name: "保存到项目" }).click();
  await expect(page.getByText(/已保存/).first()).toBeVisible({ timeout: 10_000 });
});

test("任务中心：空态与生成后自动出现任务", async ({ page }) => {
  await gotoDemo(page, "/app/tasks");
  await expect(page.getByRole("heading", { name: "任务中心" })).toBeVisible();
  await expect(page.getByText("没有任务", { exact: true })).toBeVisible();

  // 从创作中心发起一次生成，任务中心应自动出现该任务（SSE/轮询驱动）。
  // mock 世界仅存活于单页上下文，必须用应用内导航。
  await page.getByRole("navigation", { name: "主导航" }).getByRole("link", { name: "创作中心" }).click();
  await page.getByRole("link", { name: /制作图片/ }).click();
  await page.getByRole("textbox").fill("空态验证：简单示意图。");
  await page.getByRole("button", { name: "开始生成" }).click();
  await page.getByRole("navigation", { name: "主导航" }).getByRole("link", { name: "任务中心" }).click();
  await expect(page.getByText(/生成中|排队中|已完成|部分完成/).first()).toBeVisible({ timeout: 20_000 });
});

test("刷新恢复：工作台步骤 URL 直达且状态还原", async ({ page }) => {
  await gotoDemo(page, `/app/projects/${PROJECT}/lessons/${LESSON}/work/intro-options`);
  await expect(page.getByRole("heading", { name: /查看三类九套/ })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: /查看三类九套/ })).toBeVisible();
  await expect(page).toHaveURL(/work\/intro-options/);
});
