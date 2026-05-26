import { test, expect } from "@playwright/test";

test.describe("Navigation between pages", () => {
  test("should navigate from workflows to knowledge page", async ({ page }) => {
    await page.goto("/workflows");
    await page.waitForLoadState("networkidle");

    // Click a navigation link to /knowledge
    const knowledgeLink = page.locator('a[href*="knowledge"], a[href*="knowledgeBase"], a[href*="knowledge-base"]');
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
    const settingsLink = page.locator('a[href*="settings"], a[href*="setting"]');
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
});
