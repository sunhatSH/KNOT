import { test, expect } from "@playwright/test";

test.describe("Settings page", () => {
  test.beforeEach(async ({ page }) => {
    // Set auth token so protected routes don't redirect to /login
    await page.addInitScript(() => {
      localStorage.setItem("knot-token", "e2e-test-token");
    });
  });

  test("should navigate to settings page and verify it loads", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Verify the page loaded with a heading
    await expect(page.locator("h3")).toBeVisible();
    await expect(page.locator("body")).not.toBeEmpty();
  });

  test("should display form elements for LLM configuration", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // The settings form contains provider select, API URL input, API key input, and debug switch
    const form = page.locator("form");
    await expect(form).toBeVisible();

    // Provider dropdown (Ant Design Select)
    const providerSelect = page.locator(".ant-select").first();
    await expect(providerSelect).toBeVisible();

    // API Base URL input
    const apiUrlInput = page.locator('input[placeholder*="api"]');
    await expect(apiUrlInput).toBeVisible();

    // API Key input (Password field)
    const apiKeyInput = page.locator('input[type="password"]').first();
    await expect(apiKeyInput).toBeVisible();

    // Debug mode switch
    const debugSwitch = page.locator(".ant-switch");
    await expect(debugSwitch).toBeVisible();
  });

  test("should have save button in settings form", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // The form has a submit button for saving settings
    const saveButton = page.locator('button[type="submit"]');
    await expect(saveButton).toBeVisible();
  });

  test("should have language switcher section", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // The language settings card contains a Select for language switching
    // There should be at least two Select components: one in the form, one for language
    const selects = page.locator(".ant-select");
    const selectCount = await selects.count();
    expect(selectCount).toBeGreaterThanOrEqual(2);

    // The language switcher shows current language (简体中文 or English)
    const langText = page.locator("text=简体中文, text=English");
    // Just verify the settings page rendered with language-related text
    const secondCard = page.locator(".ant-card").nth(1);
    await expect(secondCard).toBeVisible();
  });
});
