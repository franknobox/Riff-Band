"use client";

import { useId, useMemo, useState } from "react";
import type { CSSProperties, ReactNode } from "react";

export type StageDescriptor = {
  id: string;
  name: string;
  agent: string;
  gate: string;
  output: string;
  decision: string;
  check: string;
};

export type DeepRoute =
  | { kind: "stage-draft"; stageIndex: number }
  | { kind: "stage-check"; stageIndex: number }
  | { kind: "stage-issue"; stageIndex: number; issueId: string }
  | { kind: "stage-decisions"; stageIndex: number }
  | { kind: "project-wizard"; projectId?: string }
  | { kind: "project-overview"; projectId: string }
  | { kind: "evidence-record"; title: string }
  | { kind: "method-record"; methodId: string }
  | { kind: "formula-record"; formulaId: string }
  | { kind: "approval-gate"; gateId: string }
  | { kind: "asset-version"; gateId: string };

export type ResearchProject = {
  id: string;
  name: string;
  code: string;
  icon: string;
  discipline: string;
  question: string;
  objective: string;
  boundary: string;
  sampleWindow: string;
  keywords: string;
  dataSources: string[];
  owner: string;
  reviewers: string;
  stageIndex: number;
  status: "active" | "draft" | "paused";
  createdAt: string;
};

export type StageDraft = {
  title: string;
  summary: string;
  objective: string;
  content: string;
  scope: string;
  evidenceNote: string;
  decision: string;
  risk: string;
  handoff: string;
  humanConfirmed: boolean;
  version: number;
  savedAt: string;
  syncHistory: string[];
};

export type CheckIssue = {
  id: string;
  category: string;
  title: string;
  description: string;
  severity: "pass" | "warning" | "error";
  field: keyof Pick<StageDraft, "content" | "decision" | "risk" | "handoff" | "evidenceNote">;
  currentValue: string;
  suggestedValue: string;
  downstream: string;
};

export type EvidenceRecord = {
  id: string;
  title: string;
  authors: string;
  year: number;
  stream: string;
  method: string;
  status: string;
  abstract?: string;
  venue?: string;
  doi?: string;
  sourceUrl?: string;
};

export type MethodRecord = {
  id: string;
  name: string;
  family: string;
  fit: number | null;
  fitRationale?: string;
  goal: string;
  assumptions: readonly string[];
  engine: string;
  dataShape: string;
  estimand: string;
  formula: string;
  diagnostics: readonly string[];
  failureRule: string;
  stata: string;
  python: string;
  tags: readonly string[];
  source: string;
};

export type FormulaRecord = {
  id: string;
  title: string;
  family: string;
  methodId: string;
  formula: string;
  purpose: string;
  symbols: readonly { symbol: string; meaning: string }[];
  assumptions: readonly string[];
  diagnostics: readonly string[];
  stata: string;
  source: string;
  fit?: number | null;
  fitRationale?: string;
};

export type GateRecord = {
  id: string;
  title: string;
  owner: string;
  status: string;
  time: string;
  asset: string;
  history?: readonly {
    revision: number;
    decision: string;
    reason: string;
    createdAt: string;
  }[];
};

export type AssetVersionSnapshot = {
  revision: number;
  contentHash: string | null;
  sections: Record<string, { title?: string; content?: string }>;
};

export type StageRevisionRecord = {
  revision: number;
  change_reason: string;
  author_type: string;
  content_hash: string;
  created_at: string;
};

export function createStageDraft(stage: StageDescriptor, project: ResearchProject): StageDraft {
  return {
    title: stage.output,
    summary: `围绕“${project.question}”形成 ${stage.name} 阶段的可审阅工作资产。`,
    objective: project.objective || `完成 ${stage.output}，并明确能够进入下一阶段的条件。`,
    content: `一、阶段目标\n${stage.name}阶段将围绕研究问题、证据与执行约束形成结构化成果。\n\n二、当前方案\n请在此补充主方案、备选方案及选择依据。\n\n三、待核查事项\n请记录仍需补证、复核或人工决定的事项。`,
    scope: project.boundary || "研究对象、时间范围和排除条件待研究者确认。",
    evidenceNote: "",
    decision: "请记录研究者最终选择、未采用方案和决定理由。",
    risk: "请明确一个可能导致当前方案失效的条件及处理方式。",
    handoff: `向下一阶段交付：${stage.output}、决定记录、证据限制与未解决问题。`,
    humanConfirmed: false,
    version: 1,
    savedAt: "尚未保存",
    syncHistory: [],
  };
}

export function calculateDraftCompleteness(draft: StageDraft): number {
  const rules = [
    { value: draft.title, target: 12 },
    {
      value: draft.summary,
      target: 80,
      placeholder: /^围绕“.*”形成 .*阶段的可审阅工作资产。$/,
    },
    {
      value: draft.objective,
      target: 80,
      placeholder: /^完成 .*，并明确能够进入下一阶段的条件。$/,
    },
    {
      value: draft.content,
      target: 500,
      placeholder: /请在此补充主方案|请记录仍需补证/,
    },
    {
      value: draft.scope,
      target: 100,
      placeholder: /待研究者确认/,
    },
    { value: draft.evidenceNote, target: 120 },
    {
      value: draft.decision,
      target: 120,
      placeholder: /^请记录研究者最终选择/,
    },
    {
      value: draft.risk,
      target: 120,
      placeholder: /^请明确一个可能导致当前方案失效/,
    },
    {
      value: draft.handoff,
      target: 100,
      placeholder: /^向下一阶段交付：/,
    },
  ];
  const score = rules.reduce((total, rule) => {
    const value = rule.value.trim();
    if (!value || rule.placeholder?.test(value)) return total;
    return total + Math.min(value.length / rule.target, 1);
  }, 0);
  return Math.round(score / rules.length * 100);
}

export function createCheckIssues(stage: StageDescriptor, draft: StageDraft): CheckIssue[] {
  return [
    {
      id: "structure",
      category: "结构",
      title: "交付正文结构完整",
      description: "阶段目标、当前方案和待核查事项均已出现，可以继续人工扩写。",
      severity: "pass",
      field: "content",
      currentValue: draft.content,
      suggestedValue: draft.content,
      downstream: "不会阻塞下游交接",
    },
    {
      id: "evidence",
      category: "证据",
      title: "核心判断的证据可追溯性",
      description: "检查是否已说明哪些证据支持或反驳关键判断，并能回溯到原始来源。",
      severity: "warning",
      field: "evidenceNote",
      currentValue: draft.evidenceNote,
      suggestedValue: "核心判断已连接 3 条支持性证据、1 条冲突证据；全文未核验的来源不得进入核心结论。",
      downstream: "影响审批包的证据覆盖说明",
    },
    {
      id: "decision",
      category: "人工决定",
      title: "决定理由与备选方案记录",
      description: `检查研究者是否说明为何接受当前 ${stage.name} 方案，以及为何不采用主要备选方案。`,
      severity: "error",
      field: "decision",
      currentValue: draft.decision,
      suggestedValue: "研究者采用当前主方案，因为它与研究问题、数据可得性和识别边界一致；备选方案因关键假设暂未满足而保留，不进入主分析。",
      downstream: `阻塞 ${stage.gate} 人工审批`,
    },
    {
      id: "risk",
      category: "风险",
      title: "失败条件与处理分支",
      description: "检查是否已说明何种证据或结果会推翻当前方案，以及出现后如何处理。",
      severity: "warning",
      field: "risk",
      currentValue: draft.risk,
      suggestedValue: "若关键识别假设未通过，则停止主结论表述，转为描述性结果并在限制部分完整披露；未经人工批准不得自动切换模型。",
      downstream: "影响分析计划与稳健性矩阵",
    },
    {
      id: "handoff",
      category: "交接",
      title: "下游交接字段已建立",
      description: "当前草稿已说明主要资产、决定记录和未解决事项的交接要求。",
      severity: "pass",
      field: "handoff",
      currentValue: draft.handoff,
      suggestedValue: draft.handoff,
      downstream: "可供下一阶段读取",
    },
  ];
}

function DeepHeader({
  level,
  eyebrow,
  title,
  description,
  trail,
  onBack,
  actions,
}: {
  level: string;
  eyebrow: string;
  title: string;
  description: string;
  trail: string[];
  onBack: () => void;
  actions?: ReactNode;
}) {
  return (
    <>
      <nav className="deep-breadcrumb" aria-label="页面层级">
        <button onClick={onBack}>← 返回上一级</button>
        {trail.map((item, index) => <span key={`${item}-${index}`}><i>/</i>{item}</span>)}
        <b>{level}</b>
      </nav>
      <header className="deep-page-header">
        <div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{description}</p></div>
        {actions && <div className="deep-header-actions">{actions}</div>}
      </header>
    </>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return <label className="deep-field"><span><strong>{label}</strong>{hint && <small>{hint}</small>}</span>{children}</label>;
}

export function StageDraftWorkspace({
  stage,
  project,
  draft,
  onBack,
  onSave,
  onOpenCheck,
  onOpenDecisions,
  onOpenChat,
  onOpenEvidence,
  evidenceRecords,
  revisions,
  restoringRevision,
  onRestore,
}: {
  stage: StageDescriptor;
  project: ResearchProject;
  draft: StageDraft;
  onBack: () => void;
  onSave: (draft: StageDraft, message: string) => void;
  onOpenCheck: () => void;
  onOpenDecisions: () => void;
  onOpenChat: () => void;
  onOpenEvidence: () => void;
  evidenceRecords: readonly EvidenceRecord[];
  revisions: readonly StageRevisionRecord[];
  restoringRevision: number | null;
  onRestore: (revision: number) => void;
}) {
  const tabs = ["工作摘要", "交付正文", "证据与引用", "决定记录", "版本历史"];
  const [tab, setTab] = useState(0);
  const [form, setForm] = useState(draft);
  const [dirty, setDirty] = useState(false);
  const update = <K extends keyof StageDraft>(key: K, value: StageDraft[K]) => {
    setForm((current) => ({
      ...current,
      [key]: value,
      ...(key === "humanConfirmed" ? {} : { humanConfirmed: false }),
    }));
    setDirty(true);
  };
  const completeness = useMemo(() => {
    return calculateDraftCompleteness(form);
  }, [form]);
  const save = () => {
    const next = { ...form, version: form.version + 1, savedAt: "刚刚由研究者保存" };
    setForm(next);
    setDirty(false);
    onSave(next, `已创建 Revision ${next.version}`);
  };
  const openChat = () => {
    if (dirty) save();
    onOpenChat();
  };
  return (
    <div className="deep-page draft-workspace">
      <DeepHeader
        level="L3 · 阶段资产"
        eyebrow={`${stage.id} · Editable stage asset`}
        title={form.title}
        description="这是阶段正式工作区，不是只读预览。研究者可修改正文、证据说明、决定理由与下游交接内容。"
        trail={[project.name, stage.name]}
        onBack={onBack}
        actions={<><span className={`save-state ${dirty ? "is-dirty" : ""}`}>{dirty ? "有未保存修改" : form.savedAt}</span><button className="primary-action" onClick={save}>保存新 Revision</button></>}
      />
      <div className="deep-workspace-grid">
        <section className="editor-shell">
          <nav className="editor-tabs" aria-label="草稿编辑分区">
            {tabs.map((item, index) => <button className={tab === index ? "is-active" : ""} onClick={() => setTab(index)} key={item}>{item}{index === 3 && !form.humanConfirmed && <i />}</button>)}
          </nav>
          <div className="editor-body">
            {tab === 0 && <div className="field-stack">
              <Field label="资产标题" hint="会显示在审批包和版本记录中"><input value={form.title} onChange={(event) => update("title", event.target.value)} /></Field>
              <Field label="阶段摘要" hint="用非技术语言说明本阶段做了什么"><textarea rows={4} value={form.summary} onChange={(event) => update("summary", event.target.value)} /></Field>
              <Field label="工作目标"><textarea rows={4} value={form.objective} onChange={(event) => update("objective", event.target.value)} /></Field>
              <Field label="研究边界"><textarea rows={5} value={form.scope} onChange={(event) => update("scope", event.target.value)} /></Field>
            </div>}
            {tab === 1 && <div className="field-stack"><Field label="交付正文" hint="支持人工增删、改写和粘贴结构化内容"><textarea className="document-editor" rows={22} value={form.content} onChange={(event) => update("content", event.target.value)} /></Field><div className="writing-assist"><span>AI 写作协助不会自动覆盖正文</span><button onClick={openChat}>与 {stage.agent} 讨论并同步</button></div></div>}
            {tab === 2 && <div className="field-stack">
              <div className="linked-evidence-summary"><div><strong>{evidenceRecords.length}</strong><span>项目证据</span></div><div><strong>{evidenceRecords.filter((item) => item.status === "已核验").length}</strong><span>全文已核验</span></div><div><strong>{evidenceRecords.filter((item) => item.status === "冲突").length}</strong><span>冲突证据</span></div><button onClick={onOpenEvidence}>打开证据库</button></div>
              <Field label="证据覆盖说明" hint="说明支持、冲突、未核验与不可外推的范围"><textarea rows={10} value={form.evidenceNote} onChange={(event) => update("evidenceNote", event.target.value)} /></Field>
              {evidenceRecords.length > 0 ? <div className="evidence-link-list">{evidenceRecords.slice(0, 2).map((record) => <article key={record.id}><span>{record.id.slice(-4).toUpperCase()}</span><div><strong>{record.title}</strong><small>{record.authors || "作者信息待补充"} · {record.status}</small></div><button onClick={onOpenEvidence}>查看来源</button></article>)}</div> : <div className="empty-state">当前项目还没有证据。请先在证据库执行检索，检索结果才会进入这里。</div>}
            </div>}
            {tab === 3 && <div className="field-stack">
              <div className="human-decision-banner"><span>人</span><div><strong>这一部分必须由研究者填写和确认</strong><p>智能体可以建议措辞，但不能代替你接受风险或作出关键选择。</p></div></div>
              <Field label="最终决定与理由"><textarea rows={7} value={form.decision} onChange={(event) => update("decision", event.target.value)} /></Field>
              <Field label="失败条件与风险处理"><textarea rows={6} value={form.risk} onChange={(event) => update("risk", event.target.value)} /></Field>
              <Field label="下游交接说明"><textarea rows={5} value={form.handoff} onChange={(event) => update("handoff", event.target.value)} /></Field>
              <label className="human-confirm-check"><input type="checkbox" checked={form.humanConfirmed} onChange={(event) => update("humanConfirmed", event.target.checked)} /><span><strong>我已人工检查本页内容</strong><small>勾选只代表完成检查，不等于通过审批门。</small></span></label>
            </div>}
            {tab === 4 && <div className="version-list">
              {revisions.map((revision, index) => <article key={revision.revision}><span>v{revision.revision}</span><div><strong>Revision {revision.revision}</strong><small>{new Date(revision.created_at).toLocaleString("zh-CN")} · {revision.author_type}</small></div><p>{index === 0 ? "当前工作版本" : revision.change_reason || "历史快照"}</p><button disabled={index === 0 || restoringRevision !== null} onClick={() => onRestore(revision.revision)}>{restoringRevision === revision.revision ? "正在恢复…" : "恢复为新草稿"}</button></article>)}
              {revisions.length === 0 && <div className="empty-state">当前阶段还没有已保存的 revision。</div>}
              <div className="version-policy"><strong>版本规则</strong><p>每次保存都会生成新的 revision；已批准版本不会被覆盖。审批只针对当时的确定 revision。</p></div>
            </div>}
          </div>
        </section>
        <aside className="draft-inspector">
          <div className="completion-card"><div className="completion-ring" style={{ "--progress": `${completeness * 3.6}deg` } as CSSProperties}><strong>{completeness}%</strong></div><div><span>草稿完整度</span><p>按必填字段与有效内容计算</p></div></div>
          <dl><div><dt>阶段</dt><dd>{stage.id} · {stage.name}</dd></div><div><dt>协作智能体</dt><dd>{stage.agent}</dd></div><div><dt>审批门</dt><dd>{stage.gate}</dd></div><div><dt>当前版本</dt><dd>Revision {form.version}</dd></div></dl>
          {form.syncHistory.length > 0 && <div className="sync-audit-card"><strong>智能体同步记录</strong>{form.syncHistory.slice(0, 3).map((item) => <p key={item}>{item}</p>)}</div>}
          <div className="inspector-actions"><button onClick={onOpenCheck}>运行一致性检查 <span>→</span></button><button onClick={onOpenDecisions}>查看人工决定项 <span>→</span></button><button onClick={openChat}>与阶段智能体协作 <span>→</span></button></div>
          <div className="inspector-note"><strong>离开前检查</strong><p>{dirty ? "还有未保存的修改。请先保存，避免丢失当前编辑内容。" : "当前编辑内容已保存，可以继续检查或返回阶段主页。"}</p></div>
        </aside>
      </div>
    </div>
  );
}

export function ConsistencyCheckWorkspace({
  stage,
  project,
  issues,
  resolved,
  onBack,
  onOpenIssue,
  onOpenDraft,
  onRunAgain,
}: {
  stage: StageDescriptor;
  project: ResearchProject;
  issues: CheckIssue[];
  resolved: Record<string, boolean>;
  onBack: () => void;
  onOpenIssue: (id: string) => void;
  onOpenDraft: () => void;
  onRunAgain: () => void;
}) {
  const [filter, setFilter] = useState<"all" | "open" | "pass">("all");
  const [lastRun, setLastRun] = useState("刚刚");
  const passed = issues.filter((issue) => issue.severity === "pass" || resolved[issue.id]).length;
  const score = Math.round((passed / issues.length) * 100);
  const visible = issues.filter((issue) => filter === "all" || (filter === "pass" ? issue.severity === "pass" || resolved[issue.id] : issue.severity !== "pass" && !resolved[issue.id]));
  const rerun = () => { setLastRun("刚刚重新检查"); onRunAgain(); };
  return (
    <div className="deep-page check-workspace">
      <DeepHeader level="L3 · 质量检查" eyebrow={`${stage.id} · Consistency check`} title={`${stage.name}一致性检查`} description="检查结构、证据、人工决定、风险与下游交接。问题不会自动修复，必须进入单项整改并由研究者保存。" trail={[project.name, stage.name]} onBack={onBack} actions={<><span className="last-check">上次检查：{lastRun}</span><button onClick={onOpenDraft}>打开草稿</button><button className="primary-action" onClick={rerun}>重新运行检查</button></>} />
      <section className="check-overview">
        <div className="check-score"><strong>{score}</strong><span>/ 100</span><p>{score === 100 ? "全部检查通过" : "尚未满足阶段退出条件"}</p></div>
        <div className="check-metrics"><div><strong>{passed}</strong><span>已通过</span></div><div><strong>{issues.filter((item) => item.severity === "warning" && !resolved[item.id]).length}</strong><span>待改进</span></div><div><strong>{issues.filter((item) => item.severity === "error" && !resolved[item.id]).length}</strong><span>阻塞项</span></div><div><strong>{issues.length}</strong><span>检查总数</span></div></div>
        <div className="check-gate-state"><span>{score === 100 ? "✓" : "!"}</span><div><strong>{score === 100 ? "可以进入人工审批" : `${stage.gate} 仍被阻塞`}</strong><p>{score === 100 ? "检查通过不等于审批通过，仍需人工提交。" : "先处理阻塞项，再复检并由研究者确认。"}</p></div></div>
      </section>
      <div className="check-layout">
        <section className="check-results">
          <div className="check-toolbar"><div><strong>检查结果</strong><span>{issues.length - passed} 项需要处理</span></div><nav>{[["all", "全部"], ["open", "待处理"], ["pass", "已通过"]].map(([key, label]) => <button className={filter === key ? "is-active" : ""} onClick={() => setFilter(key as typeof filter)} key={key}>{label}</button>)}</nav></div>
          <div className="issue-list">{visible.map((issue) => {
            const isPassed = issue.severity === "pass" || resolved[issue.id];
            return <article className={`check-issue is-${isPassed ? "pass" : issue.severity}`} key={issue.id}><span className="issue-icon">{isPassed ? "✓" : issue.severity === "error" ? "!" : "○"}</span><div><div className="issue-title"><span>{issue.category}</span><strong>{issue.title}</strong></div><p>{issue.description}</p><small>下游影响：{issue.downstream}</small></div><div className="issue-state"><b>{isPassed ? "已通过" : issue.severity === "error" ? "必须整改" : "建议整改"}</b><button onClick={() => onOpenIssue(issue.id)}>{isPassed ? "查看记录" : "打开整改"} →</button></div></article>;
          })}</div>
        </section>
        <aside className="check-side-panel"><p className="eyebrow">Exit criteria</p><h2>阶段退出条件</h2><ol><li className={passed >= 2 ? "is-done" : ""}><span>1</span>交付结构完整</li><li className={resolved.evidence ? "is-done" : ""}><span>2</span>核心证据可追溯</li><li className={resolved.decision ? "is-done" : ""}><span>3</span>人工决定有明确理由</li><li className={resolved.risk ? "is-done" : ""}><span>4</span>失败条件与处理分支完整</li></ol><div className="audit-note"><strong>检查审计记录</strong><p>规则集 v2.4 · 仅检查一致性，不替代方法审核与人工批准。</p></div></aside>
      </div>
    </div>
  );
}

export function IssueRemediationPage({
  stage,
  project,
  issue,
  resolved,
  onBack,
  onApply,
}: {
  stage: StageDescriptor;
  project: ResearchProject;
  issue: CheckIssue;
  resolved: boolean;
  onBack: () => void;
  onApply: (value: string, resolve: boolean) => void;
}) {
  const [choice, setChoice] = useState<"recommend" | "custom" | "defer">(resolved ? "custom" : "recommend");
  const [value, setValue] = useState(resolved ? issue.currentValue : issue.suggestedValue);
  const canResolve = choice !== "defer" && value.trim().length > 30;
  return (
    <div className="deep-page remediation-page">
      <DeepHeader level="L4 · 单项整改" eyebrow={`${stage.id} · ${issue.category}`} title={issue.title} description="比较当前内容与建议内容，研究者可采用建议、人工改写或保留未解决状态。所有选择都会进入决定记录。" trail={[project.name, stage.name, "一致性检查"]} onBack={onBack} actions={<span className={`remediation-status ${resolved ? "is-resolved" : ""}`}>{resolved ? "已整改" : issue.severity === "error" ? "阻塞项" : "待改进"}</span>} />
      <div className="remediation-layout">
        <section className="remediation-main">
          <div className="issue-context"><div><span>检查类别</span><strong>{issue.category}</strong></div><div><span>下游影响</span><strong>{issue.downstream}</strong></div><div><span>处理责任</span><strong>研究者本人</strong></div></div>
          <article className="current-value"><p className="eyebrow">Current value</p><h2>当前草稿内容</h2><p>{issue.currentValue}</p></article>
          <fieldset className="resolution-options"><legend>选择处理方式</legend><label className={choice === "recommend" ? "is-selected" : ""}><input type="radio" name="resolution" checked={choice === "recommend"} onChange={() => { setChoice("recommend"); setValue(issue.suggestedValue); }} /><span><strong>采用建议后人工校订</strong><small>先载入建议内容，再由你修改。</small></span></label><label className={choice === "custom" ? "is-selected" : ""}><input type="radio" name="resolution" checked={choice === "custom"} onChange={() => setChoice("custom")} /><span><strong>完全人工改写</strong><small>保留当前判断，由研究者自行填写。</small></span></label><label className={choice === "defer" ? "is-selected" : ""}><input type="radio" name="resolution" checked={choice === "defer"} onChange={() => setChoice("defer")} /><span><strong>暂不解决</strong><small>保留阻塞状态并记录原因。</small></span></label></fieldset>
          <Field label={choice === "defer" ? "暂缓原因" : "写入草稿的新内容"} hint="保存前可自由修改"><textarea className="remediation-editor" rows={10} value={value} onChange={(event) => setValue(event.target.value)} /></Field>
          <div className="remediation-actions"><button onClick={() => onApply(value, false)}>仅保存到草稿</button><button className="primary-action" disabled={!canResolve} onClick={() => onApply(value, true)}>保存并标记已整改</button></div>
        </section>
        <aside className="remediation-aside"><div className="ai-recommendation"><span>AI</span><div><strong>建议只是候选文本</strong><p>建议基于当前资产结构生成。研究者必须核对事实、证据与方法含义后再采用。</p></div></div><h3>完成标准</h3><ul><li>内容不再是占位描述</li><li>明确谁作出了决定</li><li>说明依据与失败条件</li><li>能被下游阶段直接读取</li></ul><h3>变更影响</h3><div className="impact-chain"><span>当前字段</span><i>→</i><span>{stage.gate}</span><i>→</i><span>下游资产</span></div></aside>
      </div>
    </div>
  );
}

export function StageDecisionsWorkspace({ stage, project, draft, onBack, onSave, onOpenChat, onOpenDraft }: { stage: StageDescriptor; project: ResearchProject; draft: StageDraft; onBack: () => void; onSave: (decision: string) => void; onOpenChat: () => void; onOpenDraft: () => void }) {
  const decisions = [
    { id: "primary", title: `确认 ${stage.name} 主方案`, description: "选择进入正式阶段资产的主方案，并保留未采用方案。", options: ["采用当前主方案", "人工修改后采用", "暂缓并补充证据"] },
    { id: "risk", title: "接受或处理关键风险", description: "说明哪些风险可以接受，哪些风险会阻止继续推进。", options: ["接受并完整披露", "增加检查后再决定", "风险不可接受，退回修改"] },
    { id: "handoff", title: "确认下游交接范围", description: "确定下一阶段可以读取的资产与仍需保留的限制。", options: ["按当前范围交接", "缩小结论范围后交接", "暂不交接"] },
  ];
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [reasons, setReasons] = useState<Record<string, string>>({ primary: draft.decision, risk: draft.risk, handoff: draft.handoff });
  const complete = decisions.filter((item) => choices[item.id] && (reasons[item.id] ?? "").trim().length > 20).length;
  return <div className="deep-page decisions-workspace"><DeepHeader level="L3 · 人工决定" eyebrow={`${stage.id} · Human decisions`} title={`${stage.name}待决定项`} description="每个关键选择必须包含选项、理由和影响。智能体可以解释，但不能代替研究者确认。" trail={[project.name, stage.name]} onBack={onBack} actions={<><button onClick={onOpenChat}>与 {stage.agent} 讨论</button><button onClick={onOpenDraft}>返回草稿</button></>} /><section className="decision-progress"><div><strong>{complete} / {decisions.length}</strong><span>已完成决定</span></div><div className="decision-progress-track"><span style={{ width: `${(complete / decisions.length) * 100}%` }} /></div><p>{complete === decisions.length ? "可以保存决定记录" : "还需要选择选项并补充决定理由"}</p></section><div className="decision-record-list">{decisions.map((item, index) => <article key={item.id}><header><span>0{index + 1}</span><div><h2>{item.title}</h2><p>{item.description}</p></div><b>{choices[item.id] && (reasons[item.id] ?? "").trim().length > 20 ? "已填写" : "待决定"}</b></header><div className="decision-options">{item.options.map((option) => <label className={choices[item.id] === option ? "is-selected" : ""} key={option}><input type="radio" name={item.id} checked={choices[item.id] === option} onChange={() => setChoices((current) => ({ ...current, [item.id]: option }))} /><span>{option}</span></label>)}</div><Field label="决定理由与依据"><textarea rows={4} value={reasons[item.id] ?? ""} onChange={(event) => setReasons((current) => ({ ...current, [item.id]: event.target.value }))} /></Field></article>)}</div><footer className="sticky-deep-actions"><span>保存后仍可修改；提交审批时才会冻结 revision。</span><button className="primary-action" disabled={complete !== decisions.length} onClick={() => onSave(decisions.map((item) => `${item.title}：${choices[item.id]}。${reasons[item.id]}`).join("\n\n"))}>保存人工决定记录</button></footer></div>;
}

const wizardSteps = ["基本信息", "研究问题", "范围与数据", "协作与审批", "确认创建"];

export function ProjectWizard({ initial, onBack, onComplete }: { initial?: ResearchProject; onBack: () => void; onComplete: (project: ResearchProject) => void }) {
  const generatedId = useId().replace(/:/g, "");
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<ResearchProject>(initial ?? { id: `project-${generatedId}`, name: "", code: "", icon: "研", discipline: "工商管理", question: "", objective: "", boundary: "", sampleWindow: "", keywords: "", dataSources: [], owner: "当前研究者", reviewers: "导师 + 方法审核者", stageIndex: 0, status: "draft", createdAt: "2026/7/21" });
  const update = <K extends keyof ResearchProject>(key: K, value: ResearchProject[K]) => setForm((current) => ({ ...current, [key]: value }));
  const toggleSource = (source: string) => update("dataSources", form.dataSources.includes(source) ? form.dataSources.filter((item) => item !== source) : [...form.dataSources, source]);
  const valid = [Boolean(form.name.trim() && form.discipline), Boolean(form.question.trim().length > 15 && form.objective.trim()), Boolean(form.boundary.trim() && form.sampleWindow.trim() && form.dataSources.length), Boolean(form.owner.trim() && form.reviewers.trim()), true][step];
  return <div className="deep-page project-wizard"><DeepHeader level="L2 · 项目设置" eyebrow={initial ? "Edit research project" : "New research project"} title={initial ? "编辑课题设置" : "创建新的科研项目"} description="创建过程会生成独立的 S0–S9 研究旅程、证据库、阶段资产和审批记录。所有内容创建后仍可人工修改。" trail={[initial ? initial.name : "项目中心"]} onBack={onBack} />
    <div className="wizard-shell"><aside className="wizard-steps">{wizardSteps.map((item, index) => <button className={`${index === step ? "is-active" : ""} ${index < step ? "is-done" : ""}`} onClick={() => index <= step && setStep(index)} key={item}><span>{index < step ? "✓" : index + 1}</span><div><strong>{item}</strong><small>{["命名与学科归属", "问题、目标与关键词", "边界、窗口和数据源", "角色与人工审批", "复核并加入项目列表"][index]}</small></div></button>)}</aside>
      <section className="wizard-content"><header><span>步骤 {step + 1} / {wizardSteps.length}</span><h2>{wizardSteps[step]}</h2></header>
        {step === 0 && <div className="field-stack"><div className="two-field-row"><Field label="项目名称" hint="必填"><input autoFocus value={form.name} onChange={(event) => update("name", event.target.value)} placeholder="例如：平台治理与中小企业数字化转型" /></Field><Field label="项目简称"><input value={form.code} onChange={(event) => update("code", event.target.value)} placeholder="例如：DGT-SME" /></Field></div><div className="two-field-row"><Field label="管理科学方向"><select value={form.discipline} onChange={(event) => update("discipline", event.target.value)}><option>工商管理</option><option>管理科学与工程</option><option>公共管理</option><option>信息系统</option><option>运营与供应链</option><option>创新与战略管理</option></select></Field><Field label="项目图标"><input maxLength={1} value={form.icon} onChange={(event) => update("icon", event.target.value || "研")} /></Field></div><div className="wizard-info"><strong>创建后会发生什么？</strong><p>平台为该项目建立独立阶段状态、文献检索记录、草稿版本、Stata 运行和 G0–G5 人工审批链。</p></div></div>}
        {step === 1 && <div className="field-stack"><Field label="初始研究问题" hint="至少 15 个字，可在 S0 继续修改"><textarea rows={5} value={form.question} onChange={(event) => update("question", event.target.value)} placeholder="研究对象、核心关系、机制或边界条件是什么？" /></Field><Field label="研究目标"><textarea rows={4} value={form.objective} onChange={(event) => update("objective", event.target.value)} placeholder="说明希望解释、预测、优化或评价什么。" /></Field><Field label="关键词" hint="用逗号分隔"><input value={form.keywords} onChange={(event) => update("keywords", event.target.value)} placeholder="数字化转型, 平台治理, 企业创新" /></Field><div className="question-quality"><span>AI</span><div><strong>问题质量预检</strong><ul><li className={form.question.length > 15 ? "is-pass" : ""}>研究问题足够具体</li><li className={/是否|如何|影响|机制|关系/.test(form.question) ? "is-pass" : ""}>包含可研究的关系或机制</li><li>创建后由 Topic Agent 搜寻已有研究并生成选题报告</li></ul></div></div></div>}
        {step === 2 && <div className="field-stack"><Field label="研究边界" hint="对象、地区、行业和排除范围"><textarea rows={5} value={form.boundary} onChange={(event) => update("boundary", event.target.value)} placeholder="例如：中国 A 股非金融上市公司，排除 ST 与数据严重缺失样本。" /></Field><Field label="计划样本窗口"><input value={form.sampleWindow} onChange={(event) => update("sampleWindow", event.target.value)} placeholder="例如：2016—2025" /></Field><fieldset className="source-picker"><legend>计划使用的数据来源 <small>至少选择 1 项</small></legend>{["CSMAR / Wind", "CNRDS", "国家统计局", "WIPO / 国家知识产权局", "上市公司年报", "企业调研或实验", "自建网络公开数据"].map((source) => <label className={form.dataSources.includes(source) ? "is-selected" : ""} key={source}><input type="checkbox" checked={form.dataSources.includes(source)} onChange={() => toggleSource(source)} /><span>{source}</span></label>)}</fieldset><div className="wizard-warning"><strong>许可提醒</strong><p>选择数据源不代表已获得许可。正式下载、上传或运行前仍需在 G2 由数据负责人核验。</p></div></div>}
        {step === 3 && <div className="field-stack"><div className="two-field-row"><Field label="项目负责人"><input value={form.owner} onChange={(event) => update("owner", event.target.value)} /></Field><Field label="默认会签角色"><input value={form.reviewers} onChange={(event) => update("reviewers", event.target.value)} /></Field></div><div className="role-grid"><article><span>研</span><div><strong>研究者</strong><p>编辑资产、接受风险并提交审批。</p></div></article><article><span>导</span><div><strong>导师 / PI</strong><p>确认研究价值、范围和核心结论。</p></div></article><article><span>法</span><div><strong>方法审核者</strong><p>检查设计、分析计划和结果解释。</p></div></article><article><span>AI</span><div><strong>阶段智能体</strong><p>提供建议和草稿，永远不能批准。</p></div></article></div><label className="human-confirm-check"><input type="checkbox" defaultChecked /><span><strong>启用关键步骤人工审批</strong><small>G0、G1、G2、G3、G4、G5 均需指定人工角色确认。</small></span></label></div>}
        {step === 4 && <div className="wizard-review"><div className="project-review-hero"><span>{form.icon || "研"}</span><div><p>{form.code || "NEW PROJECT"}</p><h2>{form.name}</h2><small>{form.discipline} · 负责人：{form.owner}</small></div></div><dl><div><dt>研究问题</dt><dd>{form.question}</dd></div><div><dt>研究目标</dt><dd>{form.objective}</dd></div><div><dt>研究边界</dt><dd>{form.boundary}</dd></div><div><dt>样本窗口</dt><dd>{form.sampleWindow}</dd></div><div><dt>数据来源</dt><dd>{form.dataSources.join("、")}</dd></div><div><dt>会签角色</dt><dd>{form.reviewers}</dd></div></dl><div className="creation-checklist"><strong>创建后首先完成</strong><ol><li>Topic Agent 检索已有相关研究</li><li>形成课题简报、研究空白与可行性报告</li><li>研究者人工修改候选问题</li><li>提交 G0，由研究者与导师批准选题</li></ol></div></div>}
        <footer className="wizard-actions"><button onClick={step === 0 ? onBack : () => setStep((current) => current - 1)}>{step === 0 ? "取消" : "上一步"}</button><span>{!valid && "请先完成本步骤必填内容"}</span>{step < wizardSteps.length - 1 ? <button className="primary-action" disabled={!valid} onClick={() => setStep((current) => current + 1)}>下一步</button> : <button className="primary-action" onClick={() => onComplete({ ...form, status: "active" })}>{initial ? "保存项目设置" : "确认创建并加入项目"}</button>}</footer>
      </section></div>
  </div>;
}

export function ProjectOverviewPage({ project, onBack, onStart, onEdit, onNew }: { project: ResearchProject; onBack: () => void; onStart: () => void; onEdit: () => void; onNew: () => void }) {
  return <div className="deep-page project-overview-page"><DeepHeader level="L2 · 项目中心" eyebrow="Research project overview" title={project.name} description="项目级信息、研究流程、阶段状态与协作角色的统一入口。" trail={["所有项目"]} onBack={onBack} actions={<><button onClick={onEdit}>编辑项目设置</button><button className="primary-action" onClick={onStart}>进入 {`S${project.stageIndex}`} 工作区</button></>} /><section className="project-overview-hero"><div className="project-big-icon">{project.icon}</div><div><span>{project.code || "RESEARCH PROJECT"}</span><h2>{project.question}</h2><p>{project.objective}</p></div><aside><strong>{project.stageIndex + 1}<small>/ 10</small></strong><span>当前阶段</span></aside></section><div className="project-overview-grid"><section className="project-flow-card"><div className="section-heading"><div><p className="eyebrow">Research journey</p><h2>S0–S9 研究流程</h2></div><button onClick={onStart}>继续当前阶段 →</button></div><div className="mini-stage-path">{Array.from({ length: 10 }, (_, index) => <div className={`${index < project.stageIndex ? "is-done" : ""} ${index === project.stageIndex ? "is-active" : ""}`} key={index}><span>{index < project.stageIndex ? "✓" : index}</span><small>S{index}</small></div>)}</div><div className="next-project-tasks"><article><span>01</span><div><strong>完善当前阶段草稿</strong><small>人工编辑并保存版本化资产</small></div></article><article><span>02</span><div><strong>运行一致性检查</strong><small>整改阻塞项并再次复检</small></div></article><article><span>03</span><div><strong>提交人工审批</strong><small>AI 无法代替指定角色批准</small></div></article></div></section><aside className="project-meta-card"><p className="eyebrow">Project profile</p><h2>项目资料</h2><dl><div><dt>学科方向</dt><dd>{project.discipline}</dd></div><div><dt>样本窗口</dt><dd>{project.sampleWindow || "待确认"}</dd></div><div><dt>负责人</dt><dd>{project.owner}</dd></div><div><dt>会签角色</dt><dd>{project.reviewers}</dd></div><div><dt>创建时间</dt><dd>{project.createdAt}</dd></div></dl><h3>计划数据来源</h3><div className="project-source-tags">{project.dataSources.length ? project.dataSources.map((item) => <span key={item}>{item}</span>) : <span>待 S0–S4 补充</span>}</div></aside></div><footer className="project-center-footer"><div><strong>需要启动另一个独立课题？</strong><p>新项目拥有独立的数据、草稿、审批和运行记录。</p></div><button onClick={onNew}>＋ 创建另一个项目</button></footer></div>;
}

export function EvidenceRecordPage({ record, onBack, onSave }: { record: EvidenceRecord; onBack: () => void; onSave: (message: string) => void }) {
  const [tab, setTab] = useState(0);
  const [claim, setClaim] = useState("");
  const [sample, setSample] = useState("");
  const [limits, setLimits] = useState("");
  const [selectedClaim, setSelectedClaim] = useState<number | null>(null);
  const [connectionTypes, setConnectionTypes] = useState<Record<number, string>>({});
  const [connectionNotes, setConnectionNotes] = useState<Record<number, string>>({});
  const claimLinks: readonly { id: string; title: string; strength: string; location: string; locator: string; excerpt: string }[] = [];
  const activeClaim = selectedClaim === null ? null : claimLinks[selectedClaim];

  return (
    <div className="deep-page evidence-record-page">
      <DeepHeader
        level="L3 · 论文证据卡"
        eyebrow={record.status + " · " + record.year}
        title={record.title}
        description={record.authors + " · " + record.stream + " · " + record.method}
        trail={["证据库"]}
        onBack={onBack}
        actions={<><span className="source-level verified">{record.status}</span><button className="primary-action" onClick={() => onSave("论文卡修改已保留在当前页面；请在 S1 阶段资产中保存正式 revision")}>暂存编辑</button></>}
      />
      <div className="record-layout">
        <section className="record-main">
          <nav className="editor-tabs">{["研究摘要", "证据提取", "主张连接", "核验记录"].map((item, index) => <button className={tab === index ? "is-active" : ""} onClick={() => { setTab(index); if (index !== 2) setSelectedClaim(null); }} key={item}>{item}</button>)}</nav>
          <div className="record-body">
            {tab === 0 && (
              <div className="field-stack">
                {record.abstract && <div className="claim-source-fragment"><span>检索接口返回的摘要</span><p>{record.abstract}</p></div>}
                <Field label="研究对象与样本"><textarea rows={5} value={sample} onChange={(event) => setSample(event.target.value)} /></Field>
                <Field label="可用于当前课题的核心发现"><textarea rows={7} value={claim} onChange={(event) => setClaim(event.target.value)} /></Field>
                <Field label="适用边界与限制"><textarea rows={6} value={limits} onChange={(event) => setLimits(event.target.value)} /></Field>
              </div>
            )}
            {tab === 1 && (
              <div className="extraction-grid">
                <article><span>研究问题</span><textarea defaultValue="" placeholder="从全文人工提取，不使用系统预置内容" /></article>
                <article><span>识别与方法</span><textarea defaultValue={record.method} /></article>
                <article><span>变量与测量</span><textarea defaultValue="" placeholder="从全文人工提取变量定义与测量方式" /></article>
                <article><span>主要结论</span><textarea defaultValue={claim} /></article>
              </div>
            )}
            {tab === 2 && (
              <>
                <div className="claim-edge-list">
                  {claimLinks.map((item, index) => (
                    <article className={selectedClaim === index ? "is-open" : ""} key={item.id}>
                      <span>{item.id}</span>
                      <div><strong>{item.title}</strong><p>连接类型：{connectionTypes[index]} · 强度：{item.strength} · 使用位置：{item.location}</p></div>
                      <button aria-expanded={selectedClaim === index} aria-controls="claim-link-detail" onClick={() => setSelectedClaim((current) => current === index ? null : index)}>{selectedClaim === index ? "收起详情" : index === 0 ? "查看证据片段" : "编辑连接"}</button>
                    </article>
                  ))}
                </div>
                {claimLinks.length === 0 && <div className="empty-state">尚未建立主张—证据连接。请先人工核验全文，再在 S8 连接具体主张。</div>}
                {activeClaim && selectedClaim !== null && (
                  <section className="claim-link-detail" id="claim-link-detail">
                    <header><div><p className="eyebrow">Claim-evidence edge · {activeClaim.id}</p><h3>{activeClaim.title}</h3></div><button className="modal-close" onClick={() => setSelectedClaim(null)} aria-label="关闭主张连接详情">×</button></header>
                    <dl>
                      <div><dt>原文定位</dt><dd>{activeClaim.locator}</dd></div>
                      <div><dt>证据强度</dt><dd>{activeClaim.strength} · 仍需全文人工核验</dd></div>
                      <div><dt>使用位置</dt><dd>{activeClaim.location}</dd></div>
                      <div><dt>引用边界</dt><dd>不能据此直接外推当前课题的因果效应大小。</dd></div>
                    </dl>
                    <div className="claim-source-fragment"><span>证据片段人工概括</span><p>{activeClaim.excerpt}</p></div>
                    <div className="two-field-row">
                      <Field label="连接类型"><select value={connectionTypes[selectedClaim]} onChange={(event) => setConnectionTypes((current) => ({ ...current, [selectedClaim]: event.target.value }))}><option>支持</option><option>反驳</option><option>机制启发</option><option>背景</option><option>冲突</option></select></Field>
                      <Field label="强度与使用备注"><textarea rows={5} value={connectionNotes[selectedClaim]} onChange={(event) => setConnectionNotes((current) => ({ ...current, [selectedClaim]: event.target.value }))} /></Field>
                    </div>
                    <footer><span>保存只更新工作草稿；核心主张仍需在 G4 由人工审核。</span><button className="primary-action" onClick={() => onSave(activeClaim.id + " 主张—证据连接已保存")}>保存连接</button></footer>
                  </section>
                )}
              </>
            )}
            {tab === 3 && <div className="verification-list">{["题名、作者与年份已核对", "研究问题已人工概括", "方法与样本已从全文核验", "核心发现可定位到原文", "限制与外推边界已记录"].map((item) => <label key={item}><input type="checkbox" defaultChecked={false} /><span>{item}</span></label>)}</div>}
          </div>
        </section>
        <aside className="record-aside">
          <p className="eyebrow">Provenance</p><h2>来源与使用记录</h2>
          <dl><div><dt>证据等级</dt><dd>{record.status}</dd></div><div><dt>进入课题</dt><dd>S1 文献检索</dd></div><div><dt>连接主张</dt><dd>0 条</dd></div><div><dt>DOI</dt><dd>{record.doi || "未返回"}</dd></div></dl>
          <div className="record-warning"><strong>引用边界</strong><p>摘要级或待全文来源不能直接支持核心结论；必须保留原始来源和人工概括记录。</p></div>
        </aside>
      </div>
    </div>
  );
}

export function MethodRecordPage({ method, onBack, onAdd, onSave }: { method: MethodRecord; onBack: () => void; onAdd: () => void; onSave: (message: string) => void }) {
  const [tab, setTab] = useState(0);
  const formula: Record<string, string> = { M01: "Y_it = βD_it + γX_it + α_i + λ_t + ε_it", M02: "Y_it = α + β(Treat_i × Post_t) + γ_i + λ_t + ε_it", M03: "D_it = πZ_it + γX_it + u_it\nY_it = βD̂_it + γX_it + ε_it", M04: "Y_it = α_i + λ_t + Σₖ≠₋₁ βₖ1[t-T_i=k] + ε_it" };
  return <div className="deep-page method-record-page"><DeepHeader level="L3 · 方法卡" eyebrow={`${method.id} · ${method.family}`} title={method.name} description={method.goal} trail={["方法库"]} onBack={onBack} actions={<><button onClick={() => onSave("方法卡备注已保存")}>保存备注</button><button className="primary-action" onClick={onAdd}>加入研究设计</button></>} /><section className="method-record-hero"><div className="method-fit-large"><strong>{method.fit ?? "待评估"}</strong><span>{method.fit === null ? "需要 AI 结合当前课题评估" : "AI 设计适配度"}</span></div><div><p className="eyebrow">Estimand & formula</p><pre>{formula[method.id]}</pre><small>{method.engine}</small></div></section><div className="record-layout"><section className="record-main"><nav className="editor-tabs">{["适用目标", "识别假设", "Stata 实现", "失败与诊断"].map((item, index) => <button className={tab === index ? "is-active" : ""} onClick={() => setTab(index)} key={item}>{item}</button>)}</nav><div className="record-body">{tab === 0 && <div className="field-stack"><Field label="当前课题中的估计目标"><textarea rows={5} defaultValue="" /></Field><Field label="为什么考虑该方法"><textarea rows={6} defaultValue={method.fitRationale || method.goal} /></Field></div>}{tab === 1 && <div className="assumption-audit">{method.assumptions.map((item, index) => <article key={item}><span>A{index + 1}</span><div><strong>{item}</strong><p>状态：需要在分析计划中检验</p></div><select defaultValue="pending"><option value="support">已有支持</option><option value="pending">待检查</option><option value="fail">不满足</option></select></article>)}</div>}{tab === 2 && <div className="stata-implementation"><pre><code>{method.stata}</code></pre><Field label="实现备注"><textarea rows={5} defaultValue="正式代码必须映射到 G3 已批准的 AnalysisPlan，并锁定数据签名、软件版本和输出路径。" /></Field></div>}{tab === 3 && <div className="diagnostic-matrix">{method.diagnostics.map((item, index) => <article key={item}><span>{index === 0 ? "阻塞" : "检查"}</span><div><strong>{item}</strong><p>写入诊断计划并保留完整结果。</p></div></article>)}</div>}</div></section><aside className="record-aside"><p className="eyebrow">Method boundary</p><h2>进入设计前</h2><ul>{method.assumptions.map((item) => <li key={item}>{item}</li>)}</ul><div className="record-warning"><strong>人工选择</strong><p>加入研究设计只会创建候选版本；主模型、备选模型和失败条件必须由研究者在 G1/G3 确认。</p></div></aside></div></div>;
}

export function MethodRecordWorkspace({ method, onBack, onAdd, onSave }: { method: MethodRecord; onBack: () => void; onAdd: () => void; onSave: (message: string) => void }) {
  const [tab, setTab] = useState(0);
  const [note, setNote] = useState(`将 ${method.name} 作为候选方法；进入主分析前核对数据结构、关键假设与失败规则。`);
  const tabs = ["适用与目标", "假设审计", "实现模板", "诊断与失败"];
  return <div className="deep-page method-record-page">
    <DeepHeader level="L3 · 完整方法卡" eyebrow={`${method.id} · ${method.family}`} title={method.name} description={method.goal} trail={["方法与公式库", "方法库"]} onBack={onBack} actions={<><button onClick={() => onSave("方法卡人工备注已保存")}>保存备注</button><button className="primary-action" onClick={onAdd}>加入研究设计</button></>} />
    <section className="method-record-hero enhanced-method-hero"><div className="method-fit-large"><strong>{method.fit ?? "待评估"}</strong><span>{method.fit === null ? "尚未运行 AI 评估" : "AI 当前课题适配度"}</span></div><div><p className="eyebrow">Estimand / decision objective</p><h2>{method.estimand}</h2><pre>{method.formula}</pre><small>{method.engine} · 来源：{method.source}</small></div></section>
    <div className="record-layout"><section className="record-main"><nav className="editor-tabs">{tabs.map((item, index) => <button className={tab === index ? "is-active" : ""} onClick={() => setTab(index)} key={item}>{item}</button>)}</nav><div className="record-body">
      {tab === 0 && <div className="field-stack"><div className="method-fact-grid"><article><span>数据结构</span><strong>{method.dataShape}</strong></article><article><span>方法家族</span><strong>{method.family}</strong></article><article><span>执行引擎</span><strong>{method.engine}</strong></article><article><span>失败处理</span><strong>阻塞核心表述</strong></article></div><Field label="当前课题采用说明" hint="仅保存候选说明，不会自动变更主模型"><textarea rows={7} value={note} onChange={(event) => setNote(event.target.value)} /></Field><div className="method-tag-row">{method.tags.map((tag) => <span key={tag}>{tag}</span>)}</div></div>}
      {tab === 1 && <div className="assumption-audit">{method.assumptions.map((item, index) => <article key={item}><span>A{index + 1}</span><div><strong>{item}</strong><p>需绑定证据、诊断或人工理由；不能由适配分数代替。</p></div><select defaultValue="pending"><option value="support">已有支持</option><option value="pending">待检查</option><option value="fail">不满足</option></select></article>)}</div>}
      {tab === 2 && <div className="implementation-split"><article><div><span>Stata</span><button onClick={() => onSave("Stata 模板已复制")}>复制</button></div><pre><code>{method.stata}</code></pre></article><article><div><span>Python / Solver</span><button onClick={() => onSave("Python / Solver 模板已复制")}>复制</button></div><pre><code>{method.python}</code></pre></article><div className="implementation-policy"><strong>运行规则</strong><p>模板只能写入 S5 分析计划草稿。正式运行需锁定代码、数据签名、环境与输出路径，并通过 G3 人工审批。</p></div></div>}
      {tab === 3 && <div className="diagnostic-matrix">{method.diagnostics.map((item, index) => <article key={item}><span>{index === 0 ? "必检" : "诊断"}</span><div><strong>{item}</strong><p>结果写入诊断资产并保留通过、失败与未运行状态。</p></div></article>)}<article className="is-blocking"><span>停止</span><div><strong>{method.failureRule}</strong><p>触发后不得静默切换方法；需由研究者决定降级、补证或修改设计。</p></div></article></div>}
    </div></section><aside className="record-aside"><p className="eyebrow">Decision guardrail</p><h2>方法选择边界</h2><ul>{method.assumptions.map((item) => <li key={item}>{item}</li>)}</ul><div className="record-warning"><strong>来源不是结论</strong><p>开源实现只用于能力和接口参考。方法适用性、公式口径与推断强度仍由研究者和方法审核者确认。</p></div></aside></div>
  </div>;
}

export function FormulaRecordPage({ formula, onBack, onAdd, onSave }: { formula: FormulaRecord; onBack: () => void; onAdd: () => void; onSave: (message: string) => void }) {
  const [tab, setTab] = useState(0);
  const [mapping, setMapping] = useState<Record<string, string>>(() => Object.fromEntries(formula.symbols.map((item) => [item.symbol, item.meaning])));
  const [note, setNote] = useState("公式定义与当前研究设计一致；仍需在 S5 冻结变量口径、样本和标准误/求解器设置。");
  return <div className="deep-page formula-record-page">
    <DeepHeader level="L3 · 公式卡" eyebrow={`${formula.id} · ${formula.family}`} title={formula.title} description={formula.purpose} trail={["方法与公式库", "公式库"]} onBack={onBack} actions={<><button onClick={() => onSave("公式结构检查已运行：符号均有定义")}>校验符号</button><button className="primary-action" onClick={onAdd}>加入分析计划</button></>} />
    <section className="formula-hero"><div><span>FORMULA</span><pre>{formula.formula}</pre></div><aside><small>关联方法</small><strong>{formula.methodId}</strong><small>来源</small><strong>{formula.source}</strong></aside></section>
    <div className="record-layout"><section className="record-main"><nav className="editor-tabs">{["符号映射", "假设与诊断", "Stata 实现", "采用说明"].map((item, index) => <button className={tab === index ? "is-active" : ""} onClick={() => setTab(index)} key={item}>{item}</button>)}</nav><div className="record-body">
      {tab === 0 && <div className="symbol-table"><header><span>符号</span><span>当前研究中的定义</span><span>状态</span></header>{formula.symbols.map((item) => <label key={item.symbol}><code>{item.symbol}</code><input value={mapping[item.symbol] ?? ""} onChange={(event) => setMapping((current) => ({ ...current, [item.symbol]: event.target.value }))} /><b>{(mapping[item.symbol] ?? "").trim() ? "已定义" : "缺失"}</b></label>)}</div>}
      {tab === 1 && <div className="formula-audit-grid"><article><p className="eyebrow">Assumptions</p><h2>成立条件</h2><ul>{formula.assumptions.map((item) => <li key={item}>{item}</li>)}</ul></article><article><p className="eyebrow">Diagnostics</p><h2>必须输出</h2><ul>{formula.diagnostics.map((item) => <li key={item}>{item}</li>)}</ul></article></div>}
      {tab === 2 && <div className="stata-implementation"><pre><code>{formula.stata}</code></pre><div className="implementation-policy"><strong>禁止隐式执行</strong><p>公式卡生成的代码先进入可编辑草稿；只有已审批 revision 能进入机构 Stata Runner。</p></div></div>}
      {tab === 3 && <div className="field-stack"><Field label="为什么采用这张公式卡"><textarea rows={8} value={note} onChange={(event) => setNote(event.target.value)} /></Field><button className="primary-action formula-save-note" onClick={() => onSave("公式采用说明已保存")}>保存人工说明</button></div>}
    </div></section><aside className="record-aside"><p className="eyebrow">Formula integrity</p><h2>完整性检查</h2><dl><div><dt>符号定义</dt><dd>{Object.values(mapping).filter((item) => item.trim()).length} / {formula.symbols.length}</dd></div><div><dt>成立条件</dt><dd>{formula.assumptions.length} 项</dd></div><div><dt>诊断输出</dt><dd>{formula.diagnostics.length} 项</dd></div><div><dt>版本状态</dt><dd>可人工修改</dd></div></dl><div className="record-warning"><strong>公式不是装饰</strong><p>每个符号必须连接变量字典，每个参数必须说明解释边界，每个结论必须能回到运行产物。</p></div></aside></div>
  </div>;
}

export function ApprovalGatePage({ gate, onBack, onOpenAsset, onSubmit }: { gate: GateRecord; onBack: () => void; onOpenAsset: () => void; onSubmit: () => void }) {
  const locked = gate.status === "locked" || gate.status === "blocked";
  const submitted = gate.status === "review";
  const [freezeConfirmed, setFreezeConfirmed] = useState(gate.status === "approved" || submitted);
  const completedCount = locked ? 1 : freezeConfirmed ? 4 : 3;
  const requirements = [
    "审批资产已形成可复核 revision",
    "证据限制和冲突已披露",
    "关键风险已有人工决定",
    locked ? `完成前置审批：${gate.time}` : "研究者确认版本冻结影响",
  ];
  const reviewerResponsibilities = gate.id === "G0"
    ? ["确认研究边界、已有研究与提交内容", "确认课题价值、贡献与可行性"]
    : gate.id === "G2"
      ? ["确认数据许可、伦理与访问边界"]
      : gate.id === "G5"
        ? ["确认正文、披露与复现发布包"]
        : ["确认研究价值与范围", "确认方法、风险与可复现性"];
  return <div className="deep-page approval-gate-page">
    <DeepHeader level="L3 · 审批门" eyebrow={`${gate.id} · Human approval gate`} title={gate.title} description="查看审批对象、冻结版本、前置条件、人工角色和完整审计记录。" trail={["人工审批中心"]} onBack={onBack} actions={<span className={`gate-deep-status status-${gate.status}`}>{locked ? gate.time : gate.status === "approved" ? "已批准" : submitted ? "人工会签中" : freezeConfirmed ? "可以提交" : "等待确认"}</span>} />
    <section className="gate-deep-hero"><div><span>{gate.id}</span><div><strong>{gate.asset}</strong><p>批准人：{gate.owner}</p></div></div><button onClick={onOpenAsset}>打开审批资产与版本 →</button></section>
    <div className="gate-deep-grid">
      <section className="gate-requirements">
        <div className="section-heading"><div><p className="eyebrow">Requirements</p><h2>提交前条件</h2></div><strong>{locked ? "前置阻塞" : `${completedCount} / 4 完成`}</strong></div>
        {requirements.map((item, index) => {
          const done = index < (locked ? 1 : 3) || (index === 3 && freezeConfirmed);
          return <article className={done ? "is-done" : ""} key={item}>
            <span>{done ? "✓" : index + 1}</span>
            <div><strong>{item}</strong><small>{done ? "已完成并记录" : "仍需人工处理"}</small></div>
            {index === 0 && <button onClick={onOpenAsset}>查看</button>}
            {(index === 1 || index === 2) && <b className="gate-requirement-state">已记录</b>}
            {index === 3 && locked && <b className="gate-requirement-state">未解锁</b>}
            {index === 3 && !locked && !submitted && gate.status !== "approved" && <button className="gate-confirm-button" onClick={() => setFreezeConfirmed((current) => !current)}>{freezeConfirmed ? "撤销确认" : "人工确认"}</button>}
            {index === 3 && submitted && <b className="gate-requirement-state">已提交</b>}
            {index === 3 && gate.status === "approved" && <b className="gate-requirement-state">已确认</b>}
          </article>;
        })}
      </section>
      <aside className="gate-reviewers"><p className="eyebrow">Reviewers</p><h2>人工角色</h2>{gate.owner.split("+").map((item, index) => <div key={item}><span>{item.trim().slice(0, 1)}</span><div><strong>{item.trim()}</strong><small>{reviewerResponsibilities[index] ?? reviewerResponsibilities[0]}</small></div><b>{gate.status === "approved" ? "已签署" : "待处理"}</b></div>)}<div className="agent-not-reviewer"><span>AI</span><p>智能体可以准备审批摘要，但不能成为批准人或代替签名。</p></div></aside>
    </div>
    <section className="approval-timeline"><p className="eyebrow">Audit timeline</p><h2>审批与变更记录</h2><div>{gate.history?.map((event) => <article key={`${event.revision}:${event.createdAt}`}><span /><strong>Revision {event.revision} · {event.decision}</strong><small>{new Date(event.createdAt).toLocaleString("zh-CN")} · human</small><p>{event.reason || "未填写理由"}</p></article>)}{!gate.history?.length && <div className="empty-state">当前阶段尚无审批事件。人工批准或退回后，记录会显示在这里。</div>}</div></section>
    <footer className="sticky-deep-actions"><span>{locked ? "当前审批门未解锁，可以查看资产但不能提交。" : submitted ? "当前 revision 已冻结并提交，等待指定人工角色完成会签。" : freezeConfirmed ? "提交会冻结当前 revision；后续语义修改会使受影响审批失效。" : "请先人工确认版本冻结影响，再提交审批。"}</span><button className="primary-action" disabled={locked || submitted || gate.status === "approved" || !freezeConfirmed} onClick={onSubmit}>{submitted ? "等待人工会签" : "提交人工审批"}</button></footer>
  </div>;
}

const assetSections = [
  {
    title: "研究问题与研究边界",
    status: "已核对",
    source: "S0 TopicBrief · Revision 3",
    summary: "明确研究对象、时间窗口、排除范围和可证伪的核心问题。",
    content: "核心问题：生成式 AI 的采用是否以及通过何种组织机制影响企业创新质量？\n\n研究对象：中国 A 股非金融企业；样本窗口以数据合同最终批准范围为准。\n\n纳入范围：企业层面的 AI 采用、组织互补能力与创新结果。排除范围：仅讨论工具曝光但无法识别实际采用的观察、缺少可追溯来源的二手判断。\n\n停止条件：若处理变量无法形成稳定、可审计的时间变化，主识别设计必须回到 G1 重新审批。",
  },
  {
    title: "理论机制与竞争解释",
    status: "已核对",
    source: "S2 TheoryGraph · Revision 4",
    summary: "记录主机制、边界条件以及至少一个可以被数据区分的竞争解释。",
    content: "主机制：AI 采用通过知识重组与搜索效率提升创新质量，组织互补能力强化这一作用。\n\n竞争解释 A：高质量企业同时更容易采用 AI 并产生创新，观察到的关系来自反向因果。\n竞争解释 B：行业冲击同时推动数字化投入与专利活动，关系来自共同趋势。\n\n可区分证据：采用前趋势、行业×年份冲击控制、机制变量时序与安慰剂结果。理论智能体可建议文字，但机制选择与删改由研究者确认。",
  },
  {
    title: "主设计、备选设计与 estimand",
    status: "待方法复核",
    source: "S3 ResearchProtocol · Revision 4",
    summary: "冻结目标量、主备识别设计、关键假设、失败规则和未采用理由。",
    content: "目标量（estimand）：采用生成式 AI 对采用企业创新质量的平均处理效应。\n\n主设计：企业与年份固定效应面板模型；标准误按企业聚类。\n备选设计：具备清晰采用时点时使用分期 DID；存在可信外生工具时使用 IV。\n\n必须检查：处理前趋势、共同支持、聚类层级、模型设定和多重检验。\n失败规则：平行趋势或重叠条件严重失败时，不得把相关性结果表述为因果效应。",
  },
  {
    title: "变量口径与数据约束",
    status: "已核对",
    source: "S4 DataContract · 草稿",
    summary: "列出变量定义、数据来源、许可、缺失处理和不可越过的使用边界。",
    content: "处理变量：企业 AI 采用指标，需保留来源文本、抽取规则、置信度与人工复核记录。\n结果变量：高质量专利占比、被引加权创新产出；窗口口径在正式运行前冻结。\n控制变量：规模、年龄、资本结构、研发投入及行业竞争度。\n\n数据约束：任何数据源必须登记许可与访问日期；受限数据不得上传外部模型；缺失、缩尾和样本排除规则必须写入分析计划与 do-file。",
  },
  {
    title: "证据覆盖与冲突来源",
    status: "1 条冲突",
    source: "S1 EvidenceSet · Revision 5",
    summary: "连接支持、反驳和背景证据，保留冲突而不是静默覆盖。",
    content: "当前覆盖：12 篇核心论文、4 个研究流派、92% 核心主张可追溯。\n\n已披露冲突：不同研究对 AI 投资与创新产出的短期关系方向不一致，可能来自采用测量、行业构成与观察窗口差异。\n\n处理方式：正文区分短期产出与长期质量，不合并不可比 estimand；冲突论文保留在证据图中，并在 G4 对核心主张做降级或限定。",
  },
  {
    title: "人工决定、风险和失败条件",
    status: "需最终确认",
    source: "G0–G3 Decision log",
    summary: "汇总不可委托给智能体的选择、剩余风险、停止条件与下游失效影响。",
    content: "人工决定：研究边界、理论机制、主备设计、变量代理、正式运行、失败结果解释与最终发布均由指定研究者审批。\n\n剩余风险：处理变量可能包含测量误差；采用时间可能不精确；行业共同冲击仍需更强检验。\n\n失败条件：关键诊断为阻塞时停止正式结论；修改 estimand、样本窗口或主模型会使 G1/G3 及受影响的下游资产失效。\n\n披露原则：智能体建议、人工修改、接受或拒绝及其理由全部进入版本和审计记录。",
  },
] as const;

export function AssetVersionPage({
  gate,
  snapshot,
  onBack,
  onSave,
}: {
  gate: GateRecord;
  snapshot: AssetVersionSnapshot;
  onBack: () => void;
  onSave: (
    sectionKey: string,
    title: string,
    content: string,
  ) => Promise<void>;
}) {
  const editable = gate.status === "draft" && snapshot.revision > 0;
  const [note, setNote] = useState(
    snapshot.sections.summary?.content
      || "本 revision 汇总阶段交付、证据覆盖、人工决定、风险与下游影响。请在提交前完成最终核对。",
  );
  const [expanded, setExpanded] = useState<number | null>(null);
  const [sectionText, setSectionText] = useState<Record<number, string>>(() => Object.fromEntries(
    assetSections.map((section, index) => [
      index,
      snapshot.sections[`section-${index + 1}`]?.content || section.content,
    ]),
  ));
  const [saving, setSaving] = useState("");
  const [saveError, setSaveError] = useState("");
  const openSection = expanded === null ? null : assetSections[expanded];

  function toggleSection(index: number) {
    const next = expanded === index ? null : index;
    setExpanded(next);
    if (next !== null) {
      window.requestAnimationFrame(() => document.getElementById("asset-section-detail")?.scrollIntoView({ behavior: "smooth", block: "nearest" }));
    }
  }

  async function saveSection(sectionKey: string, title: string, content: string) {
    setSaving(sectionKey);
    setSaveError("");
    try {
      await onSave(sectionKey, title, content);
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "资产章节保存失败");
    } finally {
      setSaving("");
    }
  }

  return (
    <div className="deep-page asset-version-page">
      <DeepHeader
        level="L4 · 版本资产"
        eyebrow={gate.id + " · Frozen asset revision"}
        title={gate.asset}
        description="查看审批对象的确定版本、内容哈希、上游依赖和与上一版本的差异。"
        trail={["人工审批中心", gate.title]}
        onBack={onBack}
        actions={<><span className="hash-chip">SHA-256 · {snapshot.contentHash ? `${snapshot.contentHash.slice(0, 7)}…${snapshot.contentHash.slice(-4)}` : "尚未生成"}</span>{editable && <button className="primary-action" disabled={Boolean(saving)} onClick={() => void saveSection("summary", "版本说明", note)}>{saving === "summary" ? "保存中…" : "保存资产说明"}</button>}</>}
      />
      <section className="asset-version-summary">
        <div><span>Revision</span><strong>{snapshot.revision}</strong></div>
        <div><span>内容状态</span><strong>{editable ? "工作草稿" : "冻结快照"}</strong></div>
        <div><span>生成角色</span><strong>研究者</strong></div>
        <div><span>上游依赖</span><strong>6 项已锁定</strong></div>
      </section>
      <div className="asset-version-grid">
        <section className="asset-document">
          <div className="section-heading"><div><p className="eyebrow">Asset content</p><h2>资产摘要</h2></div><span>{editable ? "可人工修改" : "只读"}</span></div>
          <Field label="版本说明"><textarea rows={6} value={note} onChange={(event) => setNote(event.target.value)} readOnly={!editable} /></Field>
          <div className="asset-section-list">
            {assetSections.map((section, index) => (
              <article className={expanded === index ? "is-open" : ""} key={section.title}>
                <span>{"0" + (index + 1)}</span>
                <div><strong>{section.title}</strong><small>{section.status} · {section.source}</small></div>
                <button data-testid={`asset-section-toggle-${index + 1}`} aria-expanded={expanded === index} aria-controls="asset-section-detail" onClick={() => toggleSection(index)}>{expanded === index ? "收起" : "展开"}</button>
              </article>
            ))}
          </div>
          {openSection && expanded !== null && (
            <section className="asset-section-detail" id="asset-section-detail" aria-live="polite">
              <header>
                <div><p className="eyebrow">Asset section · {"0" + (expanded + 1)}</p><h3>{openSection.title}</h3><p>{openSection.summary}</p></div>
                <button className="modal-close" onClick={() => setExpanded(null)} aria-label="关闭资产章节">×</button>
              </header>
              <dl>
                <div><dt>来源资产</dt><dd>{openSection.source}</dd></div>
                <div><dt>核对状态</dt><dd>{openSection.status}</dd></div>
                <div><dt>当前权限</dt><dd>{editable ? "研究者可编辑并保存" : "冻结版本，只读查看"}</dd></div>
                <div><dt>血缘影响</dt><dd>语义修改后需重新运行一致性检查，并评估受影响审批是否失效。</dd></div>
              </dl>
              <label className="asset-section-editor">
                <span>章节正文</span>
                <textarea
                  data-testid="asset-section-editor"
                  rows={15}
                  value={sectionText[expanded]}
                  onChange={(event) => setSectionText((current) => ({ ...current, [expanded]: event.target.value }))}
                  readOnly={!editable}
                />
              </label>
              <footer>
                <span>{editable ? "保存会形成新的工作草稿记录；提交审批后冻结。" : "这是审批时的确定快照，不能直接修改。"}</span>
                <div><button onClick={() => setExpanded(null)}>关闭</button>{editable && <button data-testid="asset-section-save" className="primary-action" disabled={Boolean(saving)} onClick={() => void saveSection(`section-${expanded + 1}`, openSection.title, sectionText[expanded])}>{saving === `section-${expanded + 1}` ? "保存中…" : "保存本章节"}</button>}</div>
              </footer>
              {saveError && <p className="deep-save-error" role="alert">{saveError}</p>}
            </section>
          )}
        </section>
        <aside className="version-provenance">
          <p className="eyebrow">Provenance</p><h2>版本血缘</h2>
          <div className="provenance-chain">
            <article><span>S0–S2</span><strong>上游批准资产</strong><small>6 个 revision</small></article><i>↓</i>
            <article><span>{gate.id}</span><strong>{gate.asset}</strong><small>当前 Revision {snapshot.revision}</small></article><i>↓</i>
            <article><span>下游</span><strong>等待审批结果</strong><small>尚未解锁</small></article>
          </div>
          <h3>与 Revision 3 的差异</h3>
          <ul><li>新增 1 条冲突证据说明</li><li>修改主变量口径</li><li>补充失败条件与停止规则</li><li>明确下游交接字段</li></ul>
        </aside>
      </div>
    </div>
  );
}
