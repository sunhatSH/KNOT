import { test, expect } from "@playwright/test";

test.describe("Workflow List page", () => {
  test("should render the page header", async ({ page }) => {
    await page.goto("/workflows");
    // The page should have a visible heading containing "Workflows" or "工作流"
    const heading = page.locator("h1, h2, h3").filter({
      hasText: /Workflows|工作流|流程/i,
    });
    await expect(heading.first()).toBeVisible();
  });

  test("should display workflow cards area", async ({ page }) => {
    await page.goto("/workflows");
    // Look for a container that holds workflow cards / items
    // Adjust selectors to match the actual frontend implementation
    const cardArea = page.locator(
      '[data-testid="workflow-list"], [class*="workflow"], [class*="card"], main, section'
    );
    await expect(cardArea.first()).toBeVisible();
  });

  test("page loads without console errors", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto("/workflows", { waitUntil: "networkidle" });
    expect(consoleErrors.length).toBe(0);
  });
});
