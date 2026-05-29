import { test, expect } from "@playwright/test";

test.describe("Authentication pages", () => {
  test("should display login form fields", async ({ page }) => {
    await page.goto("/login");
    await page.waitForLoadState("networkidle");

    // Verify the login form has username input, password input, and submit button
    await expect(page.locator('input[placeholder="用户名"]')).toBeVisible();
    await expect(page.locator('input[placeholder="密码"]')).toBeVisible();
    await expect(page.locator('button:has-text("登录")')).toBeVisible();
  });

  test('should have "立即注册" link pointing to /register', async ({ page }) => {
    await page.goto("/login");
    await page.waitForLoadState("networkidle");

    const registerLink = page.locator('a:has-text("立即注册")');
    await expect(registerLink).toBeVisible();
    await expect(registerLink).toHaveAttribute("href", "/register");

    await registerLink.click();
    await page.waitForURL(/.*register.*/);
    await expect(page).toHaveURL(/.*register.*/);
  });

  test("should display register form fields", async ({ page }) => {
    await page.goto("/register");
    await page.waitForLoadState("networkidle");

    // Verify the register form has username, email, password, confirm password, and submit button
    await expect(page.locator('input[placeholder="用户名"]')).toBeVisible();
    await expect(page.locator('input[placeholder="邮箱（选填）"]')).toBeVisible();
    await expect(page.locator('input[placeholder="密码"]')).toBeVisible();
    await expect(page.locator('input[placeholder="确认密码"]')).toBeVisible();
    await expect(page.locator('button:has-text("注册")')).toBeVisible();
  });

  test('should have "返回登录" link pointing back to /login', async ({ page }) => {
    await page.goto("/register");
    await page.waitForLoadState("networkidle");

    const loginLink = page.locator('a:has-text("返回登录")');
    await expect(loginLink).toBeVisible();
    await expect(loginLink).toHaveAttribute("href", "/login");

    await loginLink.click();
    await page.waitForURL(/.*login.*/);
    await expect(page).toHaveURL(/.*login.*/);
  });

  test("should show validation on empty form submission", async ({ page }) => {
    await page.goto("/login");
    await page.waitForLoadState("networkidle");

    // Click the login button without filling any fields
    await page.locator('button:has-text("登录")').click();

    // Ant Design form validation should show error messages
    // The username field has rule: { required: true, message: '请输入用户名' }
    await expect(page.locator("text=请输入用户名")).toBeVisible();
  });
});
