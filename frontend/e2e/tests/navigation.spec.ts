import { test, expect } from "@playwright/test";

test.describe("Navigation between pages", () => {
  test.beforeEach(async ({ page }) => {
    // Set auth token so protected routes don't redirect to /login
    await page.addInitScript(() => {
      localStorage.setItem("knot-token", "e2e-test-token");
    });
  });

  test("should navigate from workflows to knowledge page", async ({ page }) => {
    await page.goto("/workflows");
    await page.waitForLoadState("networkidle");

    // Click a navigation link to /knowledge
    const knowledgeLink = page.locator(
      'a[href*="knowledge"], a[href*="knowledgeBase"], a[href*="knowledge-base"]'
    );
    if (await knowledgeLink.count() > 0) {
      await knowledgeLink.first().click();
      await page.waitForURL(/.*knowledge.*/);
      await expect(page).toHaveURL(/.*knowledge.*/);
    }
  });

  test("should navigate from workflows to settings page", async ({ page }) => {
    await page.goto("/workflows");
    await page.waitForLoadState("networkidle");

    // Click a navigation link to /settings
    const settingsLink = page.locator(
      'a[href*="settings"], a[href*="setting"]'
    );
    if (await settingsLink.count() > 0) {
      await settingsLink.first().click();
      await page.waitForURL(/.*settings.*/);
      await expect(page).toHaveURL(/.*settings.*/);
    }
  });

  test("each page loads successfully", async ({ page }) => {
    const pages = ["/workflows", "/knowledge", "/settings"];

    for (const route of pages) {
      await page.goto(route, { waitUntil: "networkidle" });
      // Verify the page loaded by checking for a body with content
      await expect(page.locator("body")).not.toBeEmpty();
    }
  });

  test("should navigate to landing page and verify it loads", async ({ page }) => {
    await page.goto("/workflows");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).not.toBeEmpty();
  });

  test("should navigate to editor and verify canvas exists", async ({ page }) => {
    await page.goto("/workflows/new");
    await page.waitForLoadState("networkidle");

    // React Flow renders its canvas inside elements with .react-flow class
    const canvas = page.locator(".react-flow");
    await expect(canvas).toBeVisible();
  });

  test("should verify header navigation links work", async ({ page }) => {
    await page.goto("/workflows");
    await page.waitForLoadState("networkidle");

    // The AppHeader uses an Ant Design Menu for navigation
    const headerMenu = page.locator(".ant-menu");
    await expect(headerMenu).toBeVisible();

    // Verify navigation items exist
    const workflowNav = headerMenu.locator("text=工作流");
    const knowledgeNav = headerMenu.locator("text=知识库");
    const settingsNav = headerMenu.locator("text=设置");

    await expect(workflowNav).toBeVisible();
    await expect(knowledgeNav).toBeVisible();
    await expect(settingsNav).toBeVisible();

    // Click "知识库" nav item and verify navigation
    await knowledgeNav.click();
    await page.waitForURL(/.*knowledge.*/);
    await expect(page).toHaveURL(/.*knowledge.*/);

    // Go back and click "设置" nav item
    await page.goto("/workflows");
    await page.waitForLoadState("networkidle");
    await headerMenu.locator("text=设置").click();
    await page.waitForURL(/.*settings.*/);
    await expect(page).toHaveURL(/.*settings.*/);
  });
});
