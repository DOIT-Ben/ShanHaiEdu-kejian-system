import { expect, test } from "@playwright/test";

const viewports = [
  { height: 900, name: "1440", width: 1440 },
  { height: 768, name: "1024", width: 1024 },
  { height: 844, name: "390", width: 390 },
] as const;

for (const viewport of viewports) {
  test(`${viewport.name} 登录入口保持完整且无横向溢出`, async ({ page }, testInfo) => {
    await page.setViewportSize({ height: viewport.height, width: viewport.width });
    await page.goto("/login");

    await expect(page.getByRole("heading", { name: "登录山海教育" })).toBeVisible();
    await expect(page.getByRole("button", { name: "登录" })).toBeVisible();

    const brandVisual = page.getByRole("img", {
      name: "老师带领两名学生观察数学材料的温暖课堂",
    });
    if (viewport.width >= 1024) {
      await expect(brandVisual).toBeVisible();
      await expect
        .poll(() =>
          page.locator("img").evaluateAll((images) =>
            images.every((element) => {
              const image = element as HTMLImageElement;
              return image.complete && image.naturalWidth > 0;
            }),
          ),
        )
        .toBe(true);
      await page.locator("img").evaluateAll((images) =>
        Promise.all(
          images.map((element) => {
            const image = element as HTMLImageElement;
            return image.decode();
          }),
        ),
      );
    } else {
      await expect(brandVisual).toBeHidden();
    }

    const dimensions = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }));
    expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1);

    await page.screenshot({
      animations: "disabled",
      fullPage: true,
      path: testInfo.outputPath(`login-${viewport.name}.png`),
    });
  });
}
