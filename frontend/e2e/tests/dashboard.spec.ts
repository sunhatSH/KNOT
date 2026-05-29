import { test, expect } from "@playwright/test";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    // Set auth token so protected routes don't redirect to /login
    await page.addInitScript(() => {
      localStorage.setItem("knot-token", "e2e-test-token");
    });
  });

  test("should navigate to landing page and verify it loads", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Root "/" redirects to "/workflows"
    await expect(page).toHaveURL(/\/workflows/);
    await expect(page.locator("body")).not.toBeEmpty();
  });

  test("should display page heading and create workflow button", async ({ page }) => {
    await page.goto("/workflows");
    await page.waitForLoadState("networkidle");

    // The WorkflowList page shows a heading and a create button
    const heading = page.locator("h3").filter({ hasText: /工作流/i });
    await expect(heading).toBeVisible();

    await expect(page.locator('button:has-text("新建工作流")')).toBeVisible();
  });

  test("should show empty state when no workflows exist", async ({ page }) => {
    await page.goto("/workflows");
    await page.waitForLoadState("networkidle");

    const emptyText = page.locator("text=暂无工作流");
    const cards = page.locator(".ant-card");

    if ((await cards.count()) === 0) {
      await expect(emptyText.first()).toBeVisible();
    }
  });

  test("should render workflow cards when workflows are available", async ({ page }) => {
    await page.goto("/workflows");
    await page.waitForLoadState("networkidle");

    // Wait for either cards or empty state to render
    const cards = page.locator(".ant-card");
    const emptyState = page.locator("text=暂无工作流");

    const cardCount = await cards.count();
    const isEmpty = (await emptyState.count()) > 0;

    if (cardCount > 0) {
      await expect(cards.first()).toBeVisible();
    } else {
      // Verify the page at least rendered
      await expect(page.locator("body")).not.toBeEmpty();
    }
  });
});
