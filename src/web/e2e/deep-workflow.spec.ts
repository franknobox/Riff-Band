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

async function reopenWorkbench(page: Page) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await page.goto("/", { waitUntil: "load" });
    if (await page.locator(".project-switcher").isVisible()) return;
    await page.waitForTimeout(300);
  }
  await expect(page.locator(".project-switcher")).toBeVisible();
}

async function openG0(page: Page) {
  await page.locator(".topnav button").filter({ hasText: "Approvals" }).click();
  await page.locator(".gate-card").filter({ hasText: "G0" }).click();
  await expect(page.getByRole("heading", { name: "选题与已有研究" })).toBeVisible();
}

async function seedEvidenceCandidate(page: Page, title: string, suffix: string) {
  const createdResponse = await page.request.post("/api/v1/projects", {
    data: {
      title,
      initial_idea: "人工智能采用如何影响企业创新质量？",
    },
  });
  expect(createdResponse.status()).toBe(201);
  let project = await createdResponse.json();
  const projectId = project.project_id as string;
  const problemContent = {
    initial_idea: project.initial_idea,
    research_object: "采用人工智能的企业",
    problem_boundary: "企业人工智能采用与创新质量的关系，不预设因果成立。",
    objective: "explain",
    units: ["企业"],
    geography: ["中国"],
    time_window: "2018—2025",
    concepts: [
      {
        label: "人工智能采用",
        terms: ["AI adoption"],
        exclude_terms: [],
      },
    ],
    questions: ["人工智能采用如何影响企业创新质量？"],
    candidate_gaps: [],
    counter_searches: ["AI adoption firm innovation prior evidence"],
    unknowns: ["处理变量测量误差"],
  };
  const preparedResponse = await page.request.put(
    `/api/v1/projects/${projectId}/stages/problem`,
    {
      data: {
        content: problemContent,
        change_reason: "E2E 准备可审批的选题资产",
        author_type: "human",
      },
    },
  );
  expect(preparedResponse.ok()).toBeTruthy();
  project = await preparedResponse.json();
  let problem = project.stages.find(
    (stage: { key: string }) => stage.key === "problem",
  );
  const confirmedResponse = await page.request.patch(
    `/api/v1/projects/${projectId}/stages/problem/workspace`,
    {
      data: {
        workspace: { human_confirmed: true },
        expected_revision: problem.revision,
        change_reason: "E2E 人工确认选题资产",
      },
    },
  );
  expect(confirmedResponse.ok()).toBeTruthy();
  project = await confirmedResponse.json();
  problem = project.stages.find(
    (stage: { key: string }) => stage.key === "problem",
  );
  expect(problem.content._workspace.human_confirmed).toBeTruthy();
  const approvedResponse = await page.request.post(
    `/api/v1/projects/${projectId}/stages/problem/decisions`,
    {
      data: {
        decision: "approve",
        reason: "E2E 研究者批准选题并解锁 S1。",
        actor_type: "human",
      },
    },
  );
  expect(approvedResponse.ok()).toBeTruthy();
  project = await approvedResponse.json();
  const literature = project.stages.find(
    (stage: { key: string }) => stage.key === "literature",
  );
  const candidateId = `EC_E2E_${suffix}`;
  const paperId = `paper_e2e_${suffix}`;
  const seededResponse = await page.request.put(
    `/api/v1/projects/${projectId}/stages/literature`,
    {
      data: {
        content: {
          ...literature.content,
          evidence_candidates: [
            {
              candidate_id: candidateId,
              candidate_type: "literature",
              status: "pending",
              revision: 1,
              title: `待审核管理科学文献 ${suffix}`,
              authors: ["E2E Researcher"],
              year: 2025,
              venue: "Management Science Test",
              doi: "",
              url: `https://example.org/evidence-${suffix}`,
              abstract: "这是一条必须经人工核验后才能进入论文引用的候选证据。",
              summary: "浏览器端到端治理测试候选。",
              paper_id: paperId,
              provider: "e2e-fixture",
              source_type: "academic",
              search_id: `search_e2e_${suffix}`,
              source_snapshot: "",
              source_hash: suffix.padEnd(64, "0"),
              created_by: "agent",
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
              review: null,
            },
          ],
          evidence_library: [],
        },
        change_reason: "E2E 注入待人工审核证据候选",
        author_type: "agent",
      },
    },
  );
  expect(seededResponse.ok()).toBeTruthy();
  return { projectId, candidateId, paperId };
}

test("deep research workflow persists creation, remediation, agent sync, asset patch and approval", async ({
  page,
}) => {
  test.setTimeout(90_000);
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
  await page.route(
    /\/api\/v1\/projects\/[^/]+\/stages\/problem\/chat$/,
    async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      const request = route.request().postDataJSON() as { message: string };
      const createdAt = new Date().toISOString();
      const messageBase = {
        project_id: "e2e",
        stage_key: "problem",
        created_at: createdAt,
        model: "",
        usage: {},
        citations: [],
        search: null,
        ai_report: null,
      };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          user_message: {
            ...messageBase,
            message_id: `msg_user_${suffix}`,
            role: "user",
            content: request.message,
          },
          assistant_message: {
            ...messageBase,
            message_id: `msg_assistant_${suffix}`,
            role: "assistant",
            content: "研究边界限定为企业层面的可追溯 AI 采用；若处理变量不能形成稳定时间变化，则停止因果解释并返回 G1。",
            model: "e2e-deterministic-agent",
          },
        }),
      });
    },
  );
  await page.getByRole("button", { name: /与 Topic Agent 讨论并同步/ }).click();
  await page.getByLabel("智能体聊天输入").fill("请形成一段研究边界和失败条件说明。");
  await page.getByRole("button", { name: "发送" }).click();
  const assistantReply = page.locator(".chat-message.is-assistant").filter({
    hasText: "研究边界限定为企业层面的可追溯 AI 采用",
  });
  await expect(assistantReply).toBeVisible();
  const replyTypography = await assistantReply.locator(".message-content").evaluate((element) => {
    const style = window.getComputedStyle(element);
    return {
      fontFamily: style.fontFamily,
      fontSize: style.fontSize,
      lineHeight: style.lineHeight,
    };
  });
  expect(replyTypography.fontFamily).toContain("SF Pro Text");
  expect(replyTypography.fontSize).toBe("15px");
  expect(Number.parseFloat(replyTypography.lineHeight)).toBeGreaterThan(26);
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

  await reopenWorkbench(page);
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

  await reopenWorkbench(page);
  await activateProject(page, title);
  await openG0(page);
  const manualConfirm = page.getByRole("button", { name: "人工确认" });
  if (await manualConfirm.count()) await manualConfirm.click();
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

test("evidence and formula governance require human authority and persist revisions", async ({
  page,
}) => {
  test.setTimeout(90_000);
  const suffix = Date.now().toString().slice(-8);
  const title = `E2E 证据治理 ${suffix}`;
  const { projectId, candidateId } = await seedEvidenceCandidate(page, title, suffix);

  await page.goto("/");
  await activateProject(page, title);
  await page.locator(".topnav button").filter({ hasText: "Evidence Library" }).click();
  await expect(page.getByRole("heading", { name: "证据库", level: 1 })).toBeVisible();
  await expect(page.locator(".evidence-candidate-card").filter({ hasText: candidateId })).toBeVisible();
  await expect(page.getByText("权威证据库为空。候选必须先经过人工批准，才会出现在这里并允许进入参考文献。")).toBeVisible();

  const candidateCard = page.locator(".evidence-candidate-card").filter({ hasText: candidateId });
  await candidateCard.getByRole("button", { name: "批准进入证据库" }).click();
  await expect(page.getByText("候选已由研究者批准并生成 EVLIB 权威记录")).toBeVisible();
  const authorityRow = page.locator(".library-table tbody tr").filter({
    hasText: `待审核管理科学文献 ${suffix}`,
  });
  await expect(authorityRow).toContainText("EVLIB_");
  await authorityRow.getByRole("button", { name: "打开并编辑" }).click();
  await expect(page.getByText("L3 · 权威证据卡")).toBeVisible();
  await page.getByLabel("用于当前课题的证据概括").fill("人工核验后保存的管理科学证据概括。");
  await page.getByLabel("原文定位 / 数据表定位").fill("Section 3, Table 2");
  await page.getByRole("button", { name: "保存为新 Revision" }).click();
  await expect(page.getByText(/已保存为新的权威证据 revision/)).toBeVisible();

  const evidenceResponse = await page.request.get(
    `/api/v1/projects/${projectId}/evidence-library`,
  );
  expect(evidenceResponse.ok()).toBeTruthy();
  const evidenceRecords = (await evidenceResponse.json()).items;
  expect(evidenceRecords).toHaveLength(1);
  expect(evidenceRecords[0].revision).toBe(2);
  expect(evidenceRecords[0].summary).toContain("人工核验后保存");

  await page.locator(".topnav button").filter({ hasText: "Methods" }).click();
  await page.getByRole("button", { name: /联网与审核/ }).click();
  await page.locator(".knowledge-discovery-bar select").selectOption("formula");
  await page.getByRole("button", { name: "＋ 人工新建" }).click();
  const manual = page.locator(".manual-knowledge-record");
  await manual.getByLabel("公式名称").fill(`人工核验固定效应公式 ${suffix}`);
  await manual.getByLabel("公式类别").fill("面板模型");
  await manual.getByLabel("LaTeX / 纯文本公式").fill("Y_it = beta D_it + alpha_i + lambda_t + epsilon_it");
  await manual.getByLabel("适用条件").fill("企业年度面板且需要控制双向固定效应");
  await manual.getByLabel("符号定义").fill("i 表示企业，t 表示年份");
  await manual.getByLabel("关键假设").fill("条件外生与正确的聚类层级");
  await manual.getByLabel("关联诊断").fill("组内变异、聚类层级与残差诊断");
  await manual.getByLabel("实现命令 / 软件包").fill("Stata reghdfe");
  await manual.getByLabel("误用警告").fill("固定效应不能自动消除随时间变化的遗漏混杂");
  await manual.getByLabel("原始来源链接").fill(`https://example.org/formula-${suffix}`);
  await manual.getByRole("button", { name: "创建权威记录" }).click();
  await expect(page.getByText(/已由研究者创建并写入权威知识库/)).toBeVisible();
  await page.getByRole("button", { name: "关闭人工新建" }).click();

  const authorityEditor = page.locator(".knowledge-record-editor");
  await expect(authorityEditor).toContainText(`人工核验固定效应公式 ${suffix}`);
  await authorityEditor.getByLabel("关联诊断").fill("组内变异、聚类、安慰剂与敏感性检查");
  await authorityEditor.getByRole("button", { name: "保存新 Revision" }).click();
  await expect(authorityEditor).toContainText("Revision 2");
});
