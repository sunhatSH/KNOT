import { test, expect } from "@playwright/test";

test.describe("Workflow List page", () => {
  test.beforeEach(async ({ page }) => {
    // Set auth token so protected routes don't redirect to /login
    await page.addInitScript(() => {
      localStorage.setItem("knot-token", "e2e-test-token");
    });
  });

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

  test("should navigate to editor when clicking new workflow button", async ({ page }) => {
    await page.goto("/workflows");
    await page.waitForSelector("button:has-text('新建工作流')");

    await page.click("button:has-text('新建工作流')");

    await page.waitForURL(/\/workflows\/new/);
    await expect(page).toHaveURL(/\/workflows\/new/);
  });

  test("should navigate to editor when clicking a workflow card", async ({ page }) => {
    await page.goto("/workflows");
    await page.waitForLoadState("networkidle");

    const card = page.locator(".ant-card").first();
    const cardCount = await card.count();

    if (cardCount > 0) {
      await card.click();
      await page.waitForURL(/\/workflows\/(?!new$)/);
      await expect(page).toHaveURL(/\/workflows\/(?!new$)/);
    }
    // If there are no cards (empty state), skip — tested separately
  });

  test("should show empty state message when no workflows", async ({ page }) => {
    await page.goto("/workflows");
    await page.waitForLoadState("networkidle");

    const emptyText = page.locator("text=暂无工作流");
    const cards = page.locator(".ant-card");

    if ((await cards.count()) === 0) {
      await expect(emptyText.first()).toBeVisible();
    }
  });

  test("should show loading spinner while fetching workflows", async ({ page }) => {
    // Delay the API response so the spinner remains visible
    await page.route("**/*workflow*", async (route) => {
      await new Promise((r) => setTimeout(r, 2000));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "[]",
      });
    });

    await page.goto("/workflows");
    await expect(page.locator(".ant-spin-spinning")).toBeVisible();
  });
});
