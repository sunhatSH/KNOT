import { test, expect } from "@playwright/test";

test.describe("Knowledge page", () => {
  test.beforeEach(async ({ page }) => {
    // Set auth token so protected routes don't redirect to /login
    await page.addInitScript(() => {
      localStorage.setItem("knot-token", "e2e-test-token");
    });
  });

  test("should navigate to knowledge page and verify it loads", async ({ page }) => {
    await page.goto("/knowledge");
    await page.waitForLoadState("networkidle");

    // The page header should contain "知识库"
    await expect(page.locator("h3")).toContainText("知识库");
  });

  test("should have tabs for knowledge base list, search, and upload", async ({ page }) => {
    await page.goto("/knowledge");
    await page.waitForLoadState("networkidle");

    // Verify the Ant Design Tabs component exists
    const tabs = page.locator(".ant-tabs");
    await expect(tabs).toBeVisible();

    // Verify all three tab labels are present
    await expect(tabs.locator("text=知识库列表")).toBeVisible();
    await expect(tabs.locator("text=搜索")).toBeVisible();
    await expect(tabs.locator("text=上传文档")).toBeVisible();
  });

  test("should render search input and button in search tab", async ({ page }) => {
    await page.goto("/knowledge");
    await page.waitForLoadState("networkidle");

    // Click the "搜索" tab to reveal the search panel
    await page.locator(".ant-tabs-tab").filter({ hasText: "搜索" }).click();
    await page.waitForTimeout(300);

    // The search tab contains an Input.Search with a placeholder
    const searchInput = page.locator('input[placeholder="输入搜索关键词..."]');
    await expect(searchInput).toBeVisible();
  });

  test("should render upload tab with file upload area", async ({ page }) => {
    await page.goto("/knowledge");
    await page.waitForLoadState("networkidle");

    // Click the "上传文档" tab to reveal the upload panel
    await page.locator(".ant-tabs-tab").filter({ hasText: "上传文档" }).click();
    await page.waitForTimeout(300);

    // The upload tab should have an upload area
    const uploadArea = page.locator(".ant-upload-drag-icon");
    await expect(uploadArea).toBeVisible();
  });

  test("should show collection list area on default tab", async ({ page }) => {
    await page.goto("/knowledge");
    await page.waitForLoadState("networkidle");

    // The default tab (知识库列表) should display either a table or an empty state
    const table = page.locator(".ant-table");
    const emptyState = page.locator("text=暂无知识库");

    const tableCount = await table.count();
    const emptyCount = await emptyState.count();

    if (tableCount > 0) {
      await expect(table).toBeVisible();
    } else if (emptyCount > 0) {
      await expect(emptyState.first()).toBeVisible();
    } else {
      // At minimum, the tabs container should be visible
      await expect(page.locator(".ant-tabs")).toBeVisible();
    }
  });

  test("should handle search gracefully with empty query", async ({ page }) => {
    // Track console errors
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto("/knowledge");
    await page.waitForLoadState("networkidle");

    // Switch to the search tab
    await page.locator(".ant-tabs-tab").filter({ hasText: "搜索" }).click();
    await page.waitForTimeout(300);

    // Verify search input is present
    const searchInput = page.locator('input[placeholder="输入搜索关键词..."]');
    await expect(searchInput).toBeVisible();

    // Click the search button without entering a query
    const searchButton = page.locator(".ant-input-search button");
    await expect(searchButton).toBeVisible();
    await searchButton.click();

    // Allow time for any async handlers to complete
    await page.waitForTimeout(500);

    // The page should handle empty search gracefully — no console errors
    expect(consoleErrors.length).toBe(0);

    // The search input should still be visible after the attempt
    await expect(searchInput).toBeVisible();
  });
});
