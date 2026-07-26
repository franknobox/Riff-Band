import { expect, test, type Page } from "@playwright/test";

async function openNewProjectWizard(page: Page) {
  if (await page.getByRole("heading", { name: "创建新的科研项目" }).isVisible()) return;
  await page.locator(".project-switcher").click();
  await page.getByRole("button", { name: "＋ 创建新课题" }).click();
}

async function activateProject(page: Page, title: string) {
  await page.locator(".project-switcher").click();
  await page.locator(".project-menu button").filter({ hasText: title }).click();
  await expect(page.locator(".project-switcher")).toContainText(title);
}

async function openG0(page: Page) {
  await page.locator(".topnav button").filter({ hasText: "Approvals" }).click();
  await page.locator(".gate-card").filter({ hasText: "G0" }).click();
  await expect(page.getByRole("heading", { name: "选题与已有研究" })).toBeVisible();
}

test("deep research workflow persists creation, remediation, agent sync, asset patch and approval", async ({
  page,
}) => {
  const suffix = Date.now().toString().slice(-8);
  const title = `E2E 管理科学课题 ${suffix}`;
  await page.goto("/");
  await openNewProjectWizard(page);

  await page.getByLabel("项目名称").fill(title);
  await page.getByLabel("项目简称").fill(`E2E-${suffix}`);
  await page.getByRole("button", { name: "下一步" }).click();

  await page.getByLabel("初始研究问题").fill(
    "生成式人工智能采用如何通过组织信息处理能力影响企业创新质量？",
  );
  await page.getByLabel("研究目标").fill(
    "识别可检验的关系、机制、竞争解释和适用边界。",
  );
  await page.getByLabel("关键词").fill("人工智能采用, 企业创新, 信息处理");
  await page.getByRole("button", { name: "下一步" }).click();

  await page.getByLabel("研究边界").fill(
    "聚焦中国企业层面研究，排除无法追溯采用口径和来源的观察。",
  );
  await page.getByLabel("计划样本窗口").fill("2018—2025");
  await page.getByText("上市公司年报", { exact: true }).click();
  await page.getByRole("button", { name: "下一步" }).click();
  await page.getByRole("button", { name: "下一步" }).click();
  await page.getByRole("button", { name: "确认创建并加入项目" }).click();

  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await page.getByRole("button", { name: /进入 S0 工作区/ }).click();
  await expect(page.getByRole("heading", { name: "问题识别", level: 1 })).toBeVisible();

  await page.getByRole("button", { name: "打开当前草稿", exact: true }).click();
  await page.getByRole("button", { name: "运行一致性检查" }).click();
  await expect(page.getByRole("heading", { name: "问题识别一致性检查" })).toBeVisible();
  await page.getByRole("button", { name: /打开整改/ }).first().click();
  await page.locator(".remediation-editor").fill(
    "研究者确认采用建议后人工改写：补充可追溯证据、明确失败条件，并说明该决定对 G0 与下游资产的影响。",
  );
  await page.getByRole("button", { name: "保存并标记已整改" }).click();
  await expect(page.locator(".check-issue").filter({ hasText: "已通过" }).first()).toBeVisible();

  await page.getByRole("button", { name: "打开草稿" }).click();
  await page.getByRole("button", { name: "交付正文" }).click();
  await page.getByRole("button", { name: /与 Topic Agent 讨论并同步/ }).click();
  await page.getByLabel("智能体聊天输入").fill("请形成一段研究边界和失败条件说明。");
  await page.getByRole("button", { name: "发送" }).click();
  await page.getByRole("button", { name: "同步到交付正文" }).click();
  await page.getByRole("button", { name: "人工确认并同步" }).click();
  await expect(page.getByText("已生成同步记录，可到“当前草稿”继续修改。")).toBeVisible();
  await page.getByRole("button", { name: "关闭智能体对话" }).click();
  await page.getByRole("button", { name: "交付正文" }).click();
  await expect(page.locator(".document-editor")).toHaveValue(/Topic Agent 协作建议/);

  const summariesResponse = await page.request.get("/api/v1/projects");
  expect(summariesResponse.ok()).toBeTruthy();
  const summaries = await summariesResponse.json();
  const summary = summaries.items.find((item: { title: string }) => item.title === title);
  expect(summary).toBeTruthy();
  const projectId = summary.project_id as string;
  const currentResponse = await page.request.get(`/api/v1/projects/${projectId}`);
  const current = await currentResponse.json();
  const validProblemContent = {
    initial_idea: current.initial_idea,
    research_object: "采用生成式人工智能的企业",
    problem_boundary: "研究企业采用生成式人工智能与创新质量的关系，不预设因果成立。",
    objective: "explain",
    units: ["企业"],
    geography: ["中国"],
    time_window: "2018—2025",
    concepts: [
      {
        label: "生成式人工智能采用",
        terms: ["generative AI adoption"],
        exclude_terms: [],
      },
    ],
    questions: ["生成式人工智能采用如何影响企业创新质量？"],
    candidate_gaps: [],
    counter_searches: ["generative AI adoption firm innovation prior evidence"],
    unknowns: ["处理变量测量误差"],
  };
  const preparedResponse = await page.request.put(
    `/api/v1/projects/${projectId}/stages/problem`,
    {
      data: {
        content: validProblemContent,
        change_reason: "E2E prepare valid G0 asset",
        author_type: "human",
      },
    },
  );
  expect(preparedResponse.ok()).toBeTruthy();
  const prepared = await preparedResponse.json();
  const preparedProblem = prepared.stages.find(
    (stage: { key: string }) => stage.key === "problem",
  );
  const confirmedResponse = await page.request.patch(
    `/api/v1/projects/${projectId}/stages/problem/workspace`,
    {
      data: {
        workspace: { human_confirmed: true },
        expected_revision: preparedProblem.revision,
        change_reason: "E2E human confirmation",
      },
    },
  );
  expect(confirmedResponse.ok()).toBeTruthy();

  await page.reload();
  await activateProject(page, title);
  await openG0(page);
  await page.getByRole("button", { name: /打开审批资产与版本/ }).click();
  await page.getByTestId("asset-section-toggle-1").click();
  await page.getByTestId("asset-section-editor").fill(
    "E2E 人工修改后的研究边界。该章节通过 revision/patch API 保存，并保留内容哈希和变更理由。",
  );
  await page.getByTestId("asset-section-save").click();
  await expect(page.getByText(/已保存为新的 FastAPI revision/)).toBeVisible();

  const assetResponse = await page.request.get(`/api/v1/projects/${projectId}`);
  const assetProject = await assetResponse.json();
  const assetProblem = assetProject.stages.find(
    (stage: { key: string }) => stage.key === "problem",
  );
  expect(
    assetProblem.content._asset_version.sections["section-1"].content,
  ).toContain("revision/patch API");
  const reconfirmed = await page.request.patch(
    `/api/v1/projects/${projectId}/stages/problem/workspace`,
    {
      data: {
        workspace: { human_confirmed: true },
        expected_revision: assetProblem.revision,
        change_reason: "E2E reconfirm after asset patch",
      },
    },
  );
  expect(reconfirmed.ok()).toBeTruthy();

  await page.reload();
  await activateProject(page, title);
  await openG0(page);
  await page.getByRole("button", { name: "人工确认" }).click();
  await page.getByRole("button", { name: "提交人工审批" }).click();
  const approvalDialog = page.getByRole("dialog", { name: /人工批准“问题识别”/ });
  await approvalDialog.getByRole("checkbox").nth(2).check();
  await approvalDialog.getByRole("button", { name: "确认批准当前 Revision" }).click();
  await expect(page.getByText("已批准", { exact: true }).first()).toBeVisible();

  const approvedResponse = await page.request.get(`/api/v1/projects/${projectId}`);
  const approved = await approvedResponse.json();
  expect(approved.current_stage).toBe("literature");
  expect(approved.approvals.at(0).decision).toBe("approve");
});
