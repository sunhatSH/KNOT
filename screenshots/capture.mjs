import { createRequire } from "module";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(__dirname, "../frontend/e2e/package.json"));
const { chromium } = require("@playwright/test");

const OUT_DIR = __dirname;
const BASE_URL = process.env.KNOT_BASE_URL || "http://localhost:3000";
const USERNAME = process.env.KNOT_USER || "sunhao";
const PASSWORD = process.env.KNOT_PASSWORD || "991008sunhao";
const VIEWPORT = { width: 1440, height: 900 };

const MOCK_EXEC_ID = "exec_screenshot_demo";
const MOCK_DOCS = [
  {
    id: "doc_demo001",
    filename: "knot-doc1.txt",
    type: "txt",
    size: 2048,
    chunks: 3,
    collection: "default",
    uploaded_at: "2026-05-30T10:00:00.000Z",
  },
  {
    id: "doc_demo002",
    filename: "knot-doc2.md",
    type: "md",
    size: 1536,
    chunks: 2,
    collection: "default",
    uploaded_at: "2026-05-30T11:30:00.000Z",
  },
];

const MOCK_METRICS = {
  total_executions: 12,
  execution_counts: { success: 9, failed: 2, running: 1 },
  success_rate: 82,
  avg_duration_ms: 2450,
  top_slow_nodes: [
    { node_id: "n2", node_label: "数据采集", avg_duration_ms: 1800, total_ms: 5400, count: 3 },
    { node_id: "n3", node_label: "分析报告", avg_duration_ms: 1200, total_ms: 3600, count: 3 },
  ],
  recent_executions: [
    {
      id: MOCK_EXEC_ID,
      workflow_id: "wf_demo",
      status: "success",
      started_at: "2026-05-30T09:00:00.000Z",
      completed_at: "2026-05-30T09:00:05.000Z",
      duration_ms: 5120,
      error: null,
    },
  ],
  executions_by_day: [
    { date: "2026-05-24", count: 1 },
    { date: "2026-05-25", count: 2 },
    { date: "2026-05-26", count: 0 },
    { date: "2026-05-27", count: 3 },
    { date: "2026-05-28", count: 2 },
    { date: "2026-05-29", count: 3 },
    { date: "2026-05-30", count: 1 },
  ],
};

const MOCK_EXECUTION_DETAIL = {
  id: MOCK_EXEC_ID,
  workflow_id: "wf_demo",
  status: "success",
  started_at: "2026-05-30T09:00:00.000Z",
  completed_at: "2026-05-30T09:00:05.120Z",
  duration_ms: 5120,
  error: null,
  global_context: { input: "demo data", result: "analysis complete" },
  node_results: {
    n1: { status: "success", label: "输入" },
    n2: { status: "success", label: "数据采集" },
    n3: { status: "success", label: "分析报告" },
    n4: { status: "success", label: "输出" },
  },
  trace: [
    { event: "node_start", node_id: "n1", timestamp: "2026-05-30T09:00:00.100Z", duration_ms: null },
    { event: "node_complete", node_id: "n1", timestamp: "2026-05-30T09:00:00.450Z", duration_ms: 350 },
    { event: "node_start", node_id: "n2", timestamp: "2026-05-30T09:00:00.500Z", duration_ms: null },
    { event: "node_complete", node_id: "n2", timestamp: "2026-05-30T09:00:02.800Z", duration_ms: 2300 },
    { event: "node_start", node_id: "n3", timestamp: "2026-05-30T09:00:02.850Z", duration_ms: null },
    { event: "node_complete", node_id: "n3", timestamp: "2026-05-30T09:00:04.900Z", duration_ms: 2050 },
    { event: "node_start", node_id: "n4", timestamp: "2026-05-30T09:00:04.950Z", duration_ms: null },
    { event: "node_complete", node_id: "n4", timestamp: "2026-05-30T09:00:05.120Z", duration_ms: 170 },
  ],
};

async function waitForPageReady(page) {
  await page.waitForSelector("main, .ant-layout-content, body", { timeout: 15000 }).catch(() => {});
  await page.waitForSelector(".ant-spin-spinning", { state: "detached", timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2000);
}

async function screenshot(page, name) {
  const filePath = path.join(OUT_DIR, name);
  await page.screenshot({ path: filePath, fullPage: true });
  console.log(`Saved ${name}`);
}

async function login(page, username, password) {
  await page.goto(`${BASE_URL}/login`);
  await waitForPageReady(page);
  await page.evaluate(() => localStorage.removeItem("knot-token"));
  await page.getByPlaceholder("用户名").fill(username);
  await page.getByPlaceholder("密码").fill(password);
  await page.locator("form button.ant-btn-primary").click();
  await page.waitForURL(/\/(dashboard|workflows)/, { timeout: 15000 });
  await waitForPageReady(page);
}

function setupMocks(context) {
  context.route("**/api/v1/metrics/dashboard", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_METRICS) })
  );
  context.route("**/api/v1/knowledge/collections", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { name: "default", description: "默认知识库", chunk_count: 5, dimension: 384, created_at: "2026-05-30T08:00:00.000Z" },
        ]),
      });
    }
    return route.continue();
  });
  context.route(/\/api\/v1\/knowledge\/collections\/[^/]+\/documents(\?.*)?$/, (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ documents: MOCK_DOCS, total: MOCK_DOCS.length, page: 1, page_size: 10 }),
      });
    }
    return route.continue();
  });
  context.route(/\/api\/v1\/knowledge\/collections\/[^/]+\/documents\/doc_demo001$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...MOCK_DOCS[0],
        content: "KNOT 知识库测试文档\n\n这是一份用于截图演示的示例文档。",
      }),
    })
  );
  context.route(`**/api/v1/workflows/executions/${MOCK_EXEC_ID}`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_EXECUTION_DETAIL) })
  );
  context.route("**/api/v1/workflows/executions?*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([MOCK_EXECUTION_DETAIL]) })
  );
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: VIEWPORT });
  setupMocks(context);
  const page = await context.newPage();

  await page.goto(`${BASE_URL}/register`);
  await waitForPageReady(page);
  await screenshot(page, "01-register.png");

  await page.goto(`${BASE_URL}/login`);
  await waitForPageReady(page);
  await screenshot(page, "02-login.png");

  await login(page, USERNAME, PASSWORD);

  await page.goto(`${BASE_URL}/dashboard`);
  await waitForPageReady(page);
  await screenshot(page, "03-dashboard.png");

  await page.goto(`${BASE_URL}/workflows`);
  await waitForPageReady(page);
  await screenshot(page, "04-workflows-with-data.png");

  await context.route("**/api/v1/workflows", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    }
    return route.continue();
  });
  await page.goto(`${BASE_URL}/workflows`);
  await waitForPageReady(page);
  await screenshot(page, "05-workflows-empty.png");
  await context.unroute("**/api/v1/workflows");

  await page.goto(`${BASE_URL}/workflows`);
  await waitForPageReady(page);
  await page.locator('button:has-text("从模板创建")').click();
  await page.waitForSelector(".ant-modal", { state: "visible", timeout: 10000 });
  await page.waitForTimeout(1500);
  await screenshot(page, "06-template-selector.png");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(500);

  await page.locator(".ant-card").filter({ hasText: "数据分析流水线" }).first().click();
  await page.waitForURL(/\/workflows\//, { timeout: 15000 });
  await page.waitForSelector(".react-flow", { timeout: 15000 });
  await waitForPageReady(page);
  await screenshot(page, "07-workflow-editor.png");

  await page.locator('button').filter({ hasText: /^保存$/ }).first().click();
  await page.waitForSelector(".ant-modal", { state: "visible", timeout: 5000 });
  await page.locator('.ant-modal button').filter({ hasText: /^保\s*存$/ }).last().click();
  await page.waitForSelector(".ant-modal-wrap", { state: "hidden", timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(1000);

  let execPollCount = 0;
  await context.route("**/api/v1/workflows/*/execute", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...MOCK_EXECUTION_DETAIL, status: "running", completed_at: null }),
    })
  );
  await context.route(`**/api/v1/workflows/executions/${MOCK_EXEC_ID}`, (route) => {
    execPollCount += 1;
    const running = execPollCount < 8;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...MOCK_EXECUTION_DETAIL,
        status: running ? "running" : "success",
        completed_at: running ? null : MOCK_EXECUTION_DETAIL.completed_at,
      }),
    });
  });

  await page.locator('button').filter({ hasText: /^执行$/ }).click();
  await page.waitForSelector('text=工作流执行中', { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(1200);
  await screenshot(page, "08-workflow-executing.png");
  await page.locator(".ant-drawer-mask").click({ force: true }).catch(() => {});
  await page.waitForTimeout(500);
  await context.unroute("**/api/v1/workflows/*/execute");
  await context.unroute(`**/api/v1/workflows/executions/${MOCK_EXEC_ID}`);
  setupMocks(context);

  await page.locator('button').filter({ hasText: /^版本历史$/ }).click({ force: true });
  await page.locator('.ant-modal').filter({ hasText: "版本历史" }).waitFor({ state: "visible", timeout: 10000 });
  await page.waitForTimeout(1500);
  await screenshot(page, "09-version-history.png");
  await page.keyboard.press("Escape");

  await page.locator('.react-flow__node').filter({ hasText: "数据采集" }).first().click();
  await page.waitForTimeout(1000);
  await screenshot(page, "10-agent-config-panel.png");

  await page.goto(`${BASE_URL}/executions/${MOCK_EXEC_ID}`);
  await waitForPageReady(page);
  await screenshot(page, "11-execution-detail.png");

  await page.goto(`${BASE_URL}/knowledge`);
  await waitForPageReady(page);
  await page.locator('.ant-tabs-tab').filter({ hasText: "文档管理" }).click();
  await page.locator(".ant-select").first().click();
  await page.locator('.ant-select-item-option').filter({ hasText: "default" }).click();
  await waitForPageReady(page);
  await screenshot(page, "12-knowledge-with-data.png");

  await page.locator('button').filter({ hasText: "预览" }).first().click();
  await page.locator('.ant-modal').filter({ hasText: /文档预览|knot-doc/ }).waitFor({ state: "visible", timeout: 10000 });
  await page.waitForTimeout(1000);
  await screenshot(page, "13-document-preview.png");
  await page.keyboard.press("Escape");

  await page.goto(`${BASE_URL}/monitoring`);
  await waitForPageReady(page);
  await screenshot(page, "14-monitoring.png");

  await page.evaluate(() => {
    localStorage.setItem("knot-theme", "light");
    document.documentElement.dataset.theme = "light";
  });
  await page.goto(`${BASE_URL}/settings`);
  await waitForPageReady(page);
  await screenshot(page, "15-settings-light.png");

  await page.evaluate(() => {
    localStorage.setItem("knot-theme", "dark");
    document.documentElement.dataset.theme = "dark";
  });
  await page.goto(`${BASE_URL}/workflows`);
  await waitForPageReady(page);
  await screenshot(page, "16-workflows-dark.png");

  await page.evaluate(() => localStorage.setItem("knot-lang", "en"));
  await page.goto(`${BASE_URL}/dashboard`);
  await waitForPageReady(page);
  const enBtn = page.locator('button').filter({ hasText: "EN" });
  if (await enBtn.count()) await enBtn.click();
  await waitForPageReady(page);
  await screenshot(page, "17-dashboard-english.png");

  await page.evaluate(() => {
    localStorage.setItem("knot-lang", "zh");
    localStorage.setItem("knot-theme", "light");
    document.documentElement.dataset.theme = "light";
  });
  await page.goto(`${BASE_URL}/knowledge`);
  await waitForPageReady(page);
  await page.locator('.ant-tabs-tab').filter({ hasText: "搜索" }).click();
  await context.setOffline(true);
  await page.locator('button:has-text("搜索")').first().click().catch(() => {});
  await page.waitForSelector(".ant-alert-error, .ant-alert", { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(1000);
  await screenshot(page, "18-error-alert.png");

  await context.setOffline(false);
  await browser.close();
  console.log("All screenshots captured.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
