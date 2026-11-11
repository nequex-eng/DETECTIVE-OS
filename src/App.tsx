import { useEffect, useMemo, useState, type ReactNode } from "react";

type TabId =
  | "cases" | "sources" | "evidence" | "timeline" | "graph"
  | "contradictions" | "hypotheses" | "plan" | "review" | "report";

type Row = Record<string, any>;
type LiveJob = { job_id: string; direction: string; language?: string; status: string; stage: string; stage_note?: string; created_at?: string; updated_at?: string; result?: Row | null; error?: string | null; parent_job_id?: string | null; version?: number; source_count?: number | null; fact_count?: number | null; };
type CaseIndexItem = {
  case_id: string;
  name: string;
  status: string;
  verdict: string;
  evidence_count: number;
  source_count: number;
  coverage_score: number | null;
  review_passed: boolean;
};
type CaseData = {
  case: Row;
  sources: Row[];
  evidence: Row[];
  events: Row[];
  entities: Row[];
  relationships: Row[];
  contradictions: Row[];
  hypotheses: Row[];
  bayesian: Row;
  qualitative: Row;
  plan: Row[];
  review: Row;
  gaps: Row[];
  limits: string[];
  coverage: Row | null;
  reportMarkdown: string;
  reportUrl: string;
};

const NAV: { id: TabId; label: string; sub: string; icon: string }[] = [
  { id: "cases", label: "案件中心", sub: "CASE CENTER", icon: "01" },
  { id: "sources", label: "来源库", sub: "SOURCE LIBRARY", icon: "02" },
  { id: "evidence", label: "证据板", sub: "EVIDENCE BOARD", icon: "03" },
  { id: "timeline", label: "时间线", sub: "TIMELINE", icon: "04" },
  { id: "graph", label: "关系图谱", sub: "RELATIONSHIP GRAPH", icon: "05" },
  { id: "contradictions", label: "矛盾实验室", sub: "CONTRADICTIONS", icon: "06" },
  { id: "hypotheses", label: "假设实验室", sub: "HYPOTHESES", icon: "07" },
  { id: "plan", label: "调查计划", sub: "INVESTIGATION PLAN", icon: "08" },
  { id: "review", label: "审查室", sub: "INDEPENDENT REVIEW", icon: "09" },
  { id: "report", label: "最终报告", sub: "FINAL REPORT", icon: "10" }
];

const gradeTone: Record<string, string> = {
  A: "grade-a", B: "grade-b", C: "grade-c", D: "grade-d",
  E: "grade-e", F: "grade-zero", G: "grade-zero", H: "grade-zero"
};

function pct(value: unknown): string {
  const n = Number(value);
  return Number.isFinite(n) ? (n * 100).toFixed(1) + "%" : "—";
}
function text(value: unknown, fallback = "—"): string {
  return value === null || value === undefined || value === "" ? fallback : String(value);
}
function gradeLabel(grade: string): string {
  return grade ? grade + "级" : "未分级";
}
function Empty({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state"><span className="empty-mark">∅</span><b>{title}</b><p>{detail}</p></div>;
}
function SectionHeading({ eyebrow, title, description, right }: {
  eyebrow: string; title: string; description?: string; right?: ReactNode;
}) {
  return <div className="section-heading"><div><div className="eyebrow">{eyebrow}</div><h2>{title}</h2>{description && <p>{description}</p>}</div>{right}</div>;
}
function Metric({ label, value, note }: { label: string; value: string; note?: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong>{note && <small>{note}</small>}</div>;
}

export default function App() {
  const [index, setIndex] = useState<CaseIndexItem[]>([]);
  const [jobs, setJobs] = useState<LiveJob[]>([]);
  const [jobsError, setJobsError] = useState("");
  const [activeCaseId, setActiveCaseId] = useState("");
  const [data, setData] = useState<CaseData | null>(null);
  const [tab, setTab] = useState<TabId>("cases");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [grade, setGrade] = useState("ALL");
  const [selectedEvidence, setSelectedEvidence] = useState("");
  const [selectedSource, setSelectedSource] = useState("");
  const [selectedEntityId, setSelectedEntityId] = useState("");

  useEffect(() => {
    fetch("/data/cases/index.json")
      .then((r) => { if (!r.ok) throw new Error("案件目录暂不可用"); return r.json(); })
      .then((rows: CaseIndexItem[]) => {
        setIndex(rows);
        if (rows.length) setActiveCaseId(rows[0].case_id);
        setLoading(false);
      })
      .catch((e: Error) => { setError(e.message); setLoading(false); });
  }, []);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setInterval> | undefined;
    const refresh = async () => {
      try {
        const response = await fetch("/api/jobs?ts=" + Date.now(), { cache: "no-store" });
        if (!response.ok) throw new Error("实时任务暂不可用");
        const payload = await response.json();
        if (!alive) return;
        const rows: LiveJob[] = Array.isArray(payload.jobs) ? payload.jobs : [];
        setJobs(rows);
        setJobsError("");
        const active = rows.some((job) => !["done", "failed"].includes(job.status));
        if (active && !timer) timer = setInterval(refresh, 10000);
        if (!active && timer) { clearInterval(timer); timer = undefined; }
      } catch (e) {
        if (alive) setJobsError(e instanceof Error ? e.message : "任务列表读取失败");
      }
    };
    refresh();
    return () => { alive = false; if (timer) clearInterval(timer); };
  }, []);

  useEffect(() => {
    if (!activeCaseId) return;
    setData(null);
    setLoading(true);
    fetch("/data/cases/" + encodeURIComponent(activeCaseId) + ".json")
      .then((r) => { if (!r.ok) throw new Error("案件数据尚未生成"); return r.json(); })
      .then((payload: CaseData) => { setData(payload); setLoading(false); setError(""); })
      .catch((e: Error) => { setError(e.message); setLoading(false); });
  }, [activeCaseId]);

  const activeIndex = index.find((x) => x.case_id === activeCaseId);
  const evidenceMap = useMemo(() => {
    const map = new Map<string, Row>();
    (data?.evidence || []).forEach((item) => map.set(item.evidence_id, item));
    return map;
  }, [data]);
  const sourceMap = useMemo(() => {
    const map = new Map<string, Row>();
    (data?.sources || []).forEach((item) => map.set(item.source_id, item));
    return map;
  }, [data]);

  function openEvidence(id: string) {
    if (!id) return;
    setSelectedEvidence(id);
    setTab("evidence");
  }
  function openSource(id: string) {
    if (!id) return;
    setSelectedSource(id);
    setTab("sources");
  }
  function renderEvidenceRef(id: string) {
    const ev = evidenceMap.get(id);
    return <button className="ref-chip" key={id} onClick={() => openEvidence(id)} title={ev?.content || id}>{id}</button>;
  }
  function renderSourceRef(id: string) {
    const src = sourceMap.get(id);
    return <button className="ref-chip source-ref" key={id} onClick={() => openSource(id)} title={src?.title || id}>{id}</button>;
  }

  function CaseCenter() {
    return <>
      <SectionHeading eyebrow="RESEARCH INDEX / 01" title="案件中心" description="只展示已经载入的真实案包与引擎输出。没有报告的案件不会填充演示数据。" />
      <div className="ops-banner">
        <div><span className="eyebrow">OPERATIONS / LIVE CASE QUEUE</span><h3>调查行动中心</h3><p>实时任务与已归档案卷统一呈现。任务记录保存在服务器端，刷新或重新进入不会丢失。</p></div>
        <a className="ops-primary" href="/investigate.html">＋ 新建调查委托</a>
      </div>
      <div className="metrics-grid">
        <Metric label="实时调查任务" value={String(jobs.length)} note="来自 Cloudflare 任务库" />
        <Metric label="正在执行" value={String(jobs.filter(j => !["done","failed"].includes(j.status)).length)} note="排队、采集或分析中" />
        <Metric label="已完成任务" value={String(jobs.filter(j => j.status === "done").length)} note="保留历史记录" />
        <Metric label="已归档案卷" value={String(index.length)} note="结构化研究案包" />
      </div>
      <div className="ops-section-head"><div><span className="eyebrow">LIVE OPERATIONS</span><h3>近期调查任务</h3></div><a href="/investigate.html">任务管理与新建 →</a></div>
      {jobsError && <div className="notice">{jobsError}。静态案卷仍可正常访问。</div>}
      {jobs.length ? <div className="live-job-grid">{jobs.map(job => {
        const done = job.status === "done", failed = job.status === "failed";
        const statusLabel = done ? "调查完成" : failed ? "执行失败" : job.status === "queued" ? "等待接手" : "执行中";
        const stamp = job.updated_at || job.created_at;
        return <div className="live-job-wrap" key={job.job_id}>
          <a className="live-job-card" href={"/investigate.html?job=" + encodeURIComponent(job.job_id)}>
            <div className="live-job-top"><span className="case-id">{job.job_id.slice(0, 13).toUpperCase()}</span><span className={"job-status " + (done ? "is-done" : failed ? "is-failed" : "is-active")}>{statusLabel}</span></div>
            <h4>{job.direction}</h4>{job.parent_job_id && <div className="job-lineage">续办版本v{job.version || 2} · 承接原任务{job.parent_job_id.slice(0, 8)}</div>}<p>{job.stage_note || job.stage || "等待状态更新"}</p>
            <div className="live-job-bottom"><span>{job.stage || "queued"}</span><span>{stamp ? new Date(stamp).toLocaleString("zh-CN", { hour12: false }) : "时间未记录"}</span></div>
            {done && <div className="job-result-hint">调查报告已生成 · 打开任务档案 →</div>}
            {failed && <div className="job-result-hint failed">{job.error || "需要检查执行错误"} · 查看详情 →</div>}
          </a>
          {done && <a className="continue-job-link" href={"/investigate.html?continue=" + encodeURIComponent(job.job_id)}>＋ 继续调查 · 添加信源与新线索</a>}
        </div>;
      })}</div> : <div className="ops-empty"><b>当前没有调查任务</b><span>创建新的调查委托后，任务会自动出现在这里，并持续更新状态。</span><a href="/investigate.html">创建第一项调查 →</a></div>}
      <div className="ops-section-head archive-head"><div><span className="eyebrow">ARCHIVED CASE FILES</span><h3>已归档案卷</h3></div><span>{index.length} FILES</span></div>
      <div className="case-grid">
        {index.map((item) => <button className={"case-card " + (item.case_id === activeCaseId ? "selected" : "")} key={item.case_id}
          onClick={() => { setActiveCaseId(item.case_id); setTab("cases"); }}>
          <div className="case-card-top"><span className="case-id">{item.case_id}</span><span className="status-dot">●</span></div>
          <h3>{item.name}</h3><p>{item.status}</p>
          <div className="case-card-bottom"><span>{item.evidence_count}条证据</span><span>{item.source_count}个来源</span></div>
          <div className="case-verdict">{item.verdict}</div>
        </button>)}
      </div>
      {data && <div className="panel case-overview">
        <div className="panel-title"><div><div className="eyebrow">ACTIVE CASE</div><h3>{data.case.name}</h3></div><span className="case-id">{data.case.case_id}</span></div>
        <p className="case-status">{data.case.status}</p>
        <div className="metrics-grid compact">
          <Metric label="来源" value={String(data.sources.length)} />
          <Metric label="证据" value={String(data.evidence.length)} />
          <Metric label="时间线" value={String(data.events.length)} />
          <Metric label="矛盾" value={String(data.contradictions.length)} />
          <Metric label="假设" value={String(data.hypotheses.length)} />
          <Metric label="调查任务" value={String(data.plan.length)} />
        </div>
        <div className="notice">研究边界：公开资料不等于完整警方卷宗。证据、报道、陈述、推断和未知必须分开；模型排序不代表犯罪概率。</div>
      </div>}
    </>;
  }

  function SourcesPage() {
    const rows = (data?.sources || []).filter((s) => {
      const q = query.toLowerCase();
      return !q || [s.source_id, s.title, s.publisher, s.author, s.url].some((v) => String(v || "").toLowerCase().includes(q));
    });
    const selected = rows.find((s) => s.source_id === selectedSource) || sourceMap.get(selectedSource);
    return <>
      <SectionHeading eyebrow="SOURCE INTELLIGENCE / 02" title="来源库" description="按来源编号、出版机构、标题与链接检索。转载链在引擎中按原始来源归并。" />
      <div className="toolbar"><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索来源、机构、作者…" /><span className="count">{rows.length} / {data?.sources.length || 0} SOURCES</span></div>
      {selected && <div className="panel detail-panel"><div className="panel-title"><h3>{selected.title}</h3><button className="quiet-button" onClick={() => setSelectedSource("")}>关闭</button></div>
        <p>{selected.publisher} · {selected.author || "作者未列"} · {selected.published_at || "日期未列"}</p>
        <p className="muted">{selected.notes}</p><p><a href={selected.url} target="_blank" rel="noreferrer">打开原始来源 ↗</a></p>
      </div>}
      <div className="list-stack">{rows.map((s) => <div className="list-row" key={s.source_id}>
        <div className="row-main"><span className="source-id">{s.source_id}</span><b>{s.title}</b><small>{s.publisher} · {s.published_at || "日期未列"} · {s.reliability || "可信度未标"}</small></div>
        <div className="row-actions"><button onClick={() => setSelectedSource(s.source_id)}>详情</button><a href={s.url} target="_blank" rel="noreferrer">原文 ↗</a></div>
      </div>)}</div>
      {!rows.length && <Empty title="没有匹配来源" detail="调整关键词后重试。" />}
    </>;
  }

  function EvidencePage() {
    const rows = (data?.evidence || []).filter((e) => {
      const q = query.toLowerCase();
      const matchQuery = !q || [e.evidence_id, e.content, e.source_id, e.original_quote].some((v) => String(v || "").toLowerCase().includes(q));
      return matchQuery && (grade === "ALL" || e.grade === grade);
    });
    const selected = evidenceMap.get(selectedEvidence);
    return <>
      <SectionHeading eyebrow="EVIDENCE REGISTER / 03" title="证据板" description="每条证据都保留来源编号、原文引文、位置、分级理由与状态。点击编号可在页面内回链。" />
      <div className="toolbar"><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索证据内容、编号或引文…" />
        <select value={grade} onChange={(e) => setGrade(e.target.value)}><option value="ALL">全部等级</option>{["A","B","C","D","E","F","G","H"].map((g) => <option key={g} value={g}>{g}级</option>)}</select><span className="count">{rows.length} EVIDENCE</span></div>
      {selected && <div className="panel detail-panel focus-panel"><div className="panel-title"><h3>{selected.evidence_id} · 证据原文</h3><button className="quiet-button" onClick={() => setSelectedEvidence("")}>关闭</button></div>
        <p className="evidence-content">{selected.content}</p><blockquote>{selected.original_quote}</blockquote>
        <p className="muted">{selected.source_location} · {selected.publication_date || "日期未列"}</p>
        <p>{selected.source_id ? renderSourceRef(selected.source_id) : <span className="muted">无可引用来源；F/G/H级记录不作为事实或覆盖证据。</span>}</p><p className="muted">{selected.reliability_assessment}</p>
        {selected.analyst_notes && <p className="notice">{selected.analyst_notes}</p>}
      </div>}
      <div className="evidence-grid">{rows.map((e) => <article className="panel evidence-card" key={e.evidence_id}>
        <div className="evidence-top"><b>{e.evidence_id}</b><span className={"grade " + (gradeTone[e.grade] || "")}>{gradeLabel(e.grade)}</span><span className="verification">{e.verification_status || "状态未标"}</span></div>
        <p>{e.content}</p><blockquote>{e.original_quote}</blockquote>
        <div className="evidence-foot"><span>{e.source_location}</span>{e.source_id ? renderSourceRef(e.source_id) : <span className="no-source">无可引用来源</span>}</div>
        <button className="text-action" onClick={() => setSelectedEvidence(e.evidence_id)}>查看完整档案 →</button>
      </article>)}</div>
      {!rows.length && <Empty title="没有匹配证据" detail="更换等级或搜索词。" />}
    </>;
  }

  function TimelinePage() {
    const events = [...(data?.events || [])].sort((a, b) => String(a.time?.earliest || "").localeCompare(String(b.time?.earliest || "")));
    return <>
      <SectionHeading eyebrow="CHRONOLOGY / 04" title="时间线" description="时间精度沿用案包原始记录；范围不压成单日，未知不补造。" />
      <div className="timeline">{events.map((ev) => <div className="timeline-item" key={ev.event_id}>
        <div className="timeline-date"><b>{ev.time?.label || "时间未知"}</b><small>{ev.time?.kind || "unknown"}</small></div>
        <div className="timeline-body"><h3>{ev.title}</h3><p>{ev.notes || ""}</p><div className="ref-line">{(ev.evidence_ids || []).map((id: string) => renderEvidenceRef(id))}</div></div>
      </div>)}</div>
      {!events.length && <Empty title="尚无时间线事件" detail="当前案包没有可展示的事件记录。" />}
    </>;
  }

  function GraphPage() {
    const entities = data?.entities || [];
    const relationships = data?.relationships || [];
    const [graphQuery, setGraphQuery] = useState("");
    const [kindFilter, setKindFilter] = useState("ALL");
    const [relationFilter, setRelationFilter] = useState("ALL");
    const [confidenceFilter, setConfidenceFilter] = useState("ALL");
    const [neighborMode, setNeighborMode] = useState(false);
    const [showLabels, setShowLabels] = useState(true);
    const selectedEntity = entities.find((entity) => entity.entity_id === selectedEntityId);
    const kinds = Array.from(new Set(entities.map((x) => String(x.kind || "unknown"))));
    const relationKinds = Array.from(new Set(relationships.map((x) => String(x.relation || "未分类"))));
    const tone=(x:Row)=>/推断|inferred/i.test(String(x.status||x.confidence||""))?"inferred":/争议|disputed/i.test(String(x.status||x.confidence||""))?"disputed":/待核|unverified|reported/i.test(String(x.status||x.confidence||""))?"unverified":"documented";
    const baseVisible = entities.filter((x) => (kindFilter === "ALL" || x.kind === kindFilter) &&
      (!graphQuery || (String(x.name || "") + " " + String(x.entity_id || "")).toLowerCase().includes(graphQuery.toLowerCase())));
    const neighborhoodIds = new Set<string>([selectedEntityId]);
    if (neighborMode && selectedEntityId) relationships.forEach((edge) => {
      if (edge.from_id === selectedEntityId) neighborhoodIds.add(edge.to_id);
      if (edge.to_id === selectedEntityId) neighborhoodIds.add(edge.from_id);
    });
    const visible = (neighborMode && selectedEntityId
      ? baseVisible.filter((x) => neighborhoodIds.has(x.entity_id)) : baseVisible).slice(0, 180);
    const ids = new Set(visible.map((x) => x.entity_id));
    const edges = relationships.filter((x) => ids.has(x.from_id) && ids.has(x.to_id) &&
      (relationFilter === "ALL" || String(x.relation || "未分类") === relationFilter) &&
      (confidenceFilter === "ALL" || tone(x) === confidenceFilter));
    const degree = new Map<string,number>();
    edges.forEach((x) => { degree.set(x.from_id,(degree.get(x.from_id)||0)+1); degree.set(x.to_id,(degree.get(x.to_id)||0)+1); });
    const ordered = [...visible].sort((x,y)=>(degree.get(y.entity_id)||0)-(degree.get(x.entity_id)||0));
    const W=1200,H=820,cx=600,cy=410;
    const pos = new Map<string,{x:number;y:number}>();
    const nodes = ordered.slice(0, 180);
    const coords = nodes.map((node,i) => {
      const angle = i / Math.max(1,nodes.length) * Math.PI * 2;
      const radius = Math.min(330, 95 + Math.sqrt(nodes.length) * 23);
      return {x:cx + Math.cos(angle) * radius, y:cy + Math.sin(angle) * radius, vx:0, vy:0};
    });
    const nodeIndex = new Map(nodes.map((node,i)=>[node.entity_id,i]));
    const springs = edges.flatMap(edge => {
      const a=nodeIndex.get(edge.from_id), b=nodeIndex.get(edge.to_id);
      return a===undefined || b===undefined ? [] : [{a,b}];
    });
    // Deterministic force-directed layout: repulsion separates entities; recorded links pull neighbors together.
    for (let iteration=0; iteration<90 && nodes.length>1; iteration++) {
      const forces = coords.map(()=>({x:0,y:0}));
      for(let i=0;i<coords.length;i++) for(let j=i+1;j<coords.length;j++) {
        const dx=coords[i].x-coords[j].x, dy=coords[i].y-coords[j].y;
        const d2=Math.max(100,dx*dx+dy*dy), d=Math.sqrt(d2), force=1800/d2;
        const fx=dx/d*force, fy=dy/d*force;
        forces[i].x+=fx; forces[i].y+=fy; forces[j].x-=fx; forces[j].y-=fy;
      }
      springs.forEach(({a,b})=>{
        const dx=coords[b].x-coords[a].x, dy=coords[b].y-coords[a].y, d=Math.max(1,Math.hypot(dx,dy));
        const force=(d-165)*0.0018, fx=dx/d*force, fy=dy/d*force;
        forces[a].x+=fx; forces[a].y+=fy; forces[b].x-=fx; forces[b].y-=fy;
      });
      coords.forEach((p,i)=>{
        forces[i].x+=(cx-p.x)*0.0009; forces[i].y+=(cy-p.y)*0.0009;
        p.vx=(p.vx+forces[i].x)*0.82; p.vy=(p.vy+forces[i].y)*0.82;
        p.x=Math.max(55,Math.min(W-55,p.x+p.vx)); p.y=Math.max(55,Math.min(H-55,p.y+p.vy));
      });
    }
    nodes.forEach((node,i)=>pos.set(node.entity_id,{x:coords[i].x,y:coords[i].y}));
    const linked = selectedEntity ? relationships.filter((x)=>x.from_id===selectedEntityId||x.to_id===selectedEntityId) : [];
    return <>
      <SectionHeading eyebrow="INTELLIGENCE LINK ANALYSIS / 05" title="关系图谱" description="实体网络、关系溯源与实体档案。只显示案包中有记录的关系；推断、争议和待核实关系使用独立样式。" />
      <div className="graph-command"><input value={graphQuery} onChange={(e)=>setGraphQuery(e.target.value)} placeholder="搜索实体名称或编号…"/><select value={kindFilter} onChange={(e)=>setKindFilter(e.target.value)}><option value="ALL">全部实体类型</option>{kinds.map(k=><option key={k} value={k}>{k}</option>)}</select><select value={relationFilter} onChange={(e)=>setRelationFilter(e.target.value)}><option value="ALL">全部关系类型</option>{relationKinds.map(k=><option key={k} value={k}>{k}</option>)}</select><select value={confidenceFilter} onChange={(e)=>setConfidenceFilter(e.target.value)}><option value="ALL">全部可信状态</option><option value="documented">有来源记录</option><option value="unverified">待核实</option><option value="inferred">推断</option><option value="disputed">争议</option></select><button className="quiet-button" onClick={()=>setNeighborMode(!neighborMode)} disabled={!selectedEntityId}>{neighborMode?"显示全部实体":"仅看选中实体邻居"}</button><button className="quiet-button" onClick={()=>{setGraphQuery("");setKindFilter("ALL");setRelationFilter("ALL");setConfidenceFilter("ALL");setNeighborMode(false);setSelectedEntityId("");}}>重置</button></div>
      <div className="graph-kpis"><span>实体 <b>{visible.length}</b> / {entities.length}</span><span>关系 <b>{edges.length}</b> / {relationships.length}</span><span>孤立节点 <b>{visible.filter(x=>!(degree.get(x.entity_id)||0)).length}</b></span><span>核心实体 <b>{ordered.slice(0,3).map(x=>x.name).join("、")||"—"}</b></span></div>
      {entities.length ? <div className="intel-graph-layout">
        <aside className="graph-entity-rail"><div className="graph-rail-title">ENTITY INDEX</div>{visible.map(x=><button key={x.entity_id} className={"graph-entity-row "+(selectedEntityId===x.entity_id?"active":"")} onClick={()=>setSelectedEntityId(x.entity_id)}><b>{x.name}</b><small>{x.kind||"unknown"} · {degree.get(x.entity_id)||0} links</small></button>)}</aside>
        <div className="graph-stage"><div className="graph-legend"><span><i className="edge-documented"/>有来源记录</span><span><i className="edge-unverified"/>待核实</span><span><i className="edge-inferred"/>推断</span><span><i className="edge-disputed"/>争议</span></div>
          <div className="graph-viewport"><svg viewBox={"0 0 "+W+" "+H} role="img" aria-label="案件关系网络"><defs><pattern id="intelGrid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="#203247"/></pattern></defs><rect width={W} height={H} fill="url(#intelGrid)"/>
            {edges.map((x,i)=>{const p=pos.get(x.from_id),q=pos.get(x.to_id);if(!p||!q)return null;const mx=(p.x+q.x)/2,my=(p.y+q.y)/2-24;return <g key={i} className={"graph-edge "+tone(x)}><path d={"M"+p.x+" "+p.y+" Q"+mx+" "+my+" "+q.x+" "+q.y}/>{showLabels&&<text x={mx} y={my-6}>{String(x.relation||"关联").slice(0,16)}</text>}</g>;})}
            {visible.map(x=>{const p=pos.get(x.entity_id)!;const n=degree.get(x.entity_id)||0;return <g key={x.entity_id} className={"graph-entity-node "+(selectedEntityId===x.entity_id?"selected":"")} transform={"translate("+p.x+" "+p.y+")"} onClick={()=>setSelectedEntityId(x.entity_id)} role="button" tabIndex={0} onKeyDown={(e)=>{if(e.key==="Enter")setSelectedEntityId(x.entity_id);}}><circle r={Math.min(37,25+n*2)}/><text y="-3" className="node-name">{String(x.name||"未命名").slice(0,13)}</text><text y="14" className="node-kind">{String(x.kind||"ENTITY")} · {n}</text></g>;})}
          </svg></div><div className="graph-stage-foot"><span>CASE-SCOPED LINK ANALYSIS</span><label><input type="checkbox" checked={showLabels} onChange={e=>setShowLabels(e.target.checked)}/> 显示关系标签</label></div>
        </div>
        <aside className="graph-intel-panel"><div className="graph-rail-title">ENTITY DOSSIER</div>{selectedEntity?<><div className="dossier-type">{selectedEntity.kind||"ENTITY"}</div><h3>{selectedEntity.name}</h3><code>{selectedEntity.entity_id}</code><p>{selectedEntity.notes||"案包未提供补充描述。"}</p><div className="dossier-stats"><span>关系数<strong>{linked.length}</strong></span><span>直接邻居<strong>{new Set(linked.map(x=>x.from_id===selectedEntityId?x.to_id:x.from_id)).size}</strong></span></div><h4>关系与来源</h4>{linked.map((x,i)=><div className="dossier-link" key={i}><b>{x.relation}</b><span>{x.from_id} → {x.to_id}</span><div>{x.evidence_id?renderEvidenceRef(x.evidence_id):null}{x.source_id?renderSourceRef(x.source_id):null}</div><small>{x.status||x.confidence||"状态未标注"}</small></div>)}</>:<div className="graph-select-empty">选择节点查看实体档案、直接关系与证据来源。</div>}</aside>
      </div> : <Empty title="当前案卷没有结构化关系数据" detail="当前案包尚未录入实体和关系。没有关系记录不代表没有关系；请补充资料后再建立可溯源连线，系统不会凭空推断。" />}
      <div className="relationship-list"><h3>关系明细 / TRACEABLE LINKS</h3>{edges.map((x,i)=><div className="list-row" key={i}><b>{x.from_id} → {x.to_id}</b><span>{x.relation}</span><span className={"link-status "+tone(x)}>{x.status||x.confidence||"未标注"}</span>{x.source_id?renderSourceRef(x.source_id):null}{x.evidence_id?renderEvidenceRef(x.evidence_id):null}</div>)}</div>
    </>;
  }

  function ContradictionsPage() {
    return <>
      <SectionHeading eyebrow="CONFLICT ANALYSIS / 06" title="矛盾实验室" description="区分事实冲突、解释分歧、口径差异和资料缺口；不自动推断任何一方撒谎。" />
      <div className="list-stack">{(data?.contradictions || []).map((c) => <article className="panel contradiction-card" key={c.contradiction_id}>
        <div className="panel-title"><div><span className="source-id">{c.contradiction_id}</span><h3>{c.wording_a} <em>vs</em> {c.wording_b}</h3></div><span className="tag">{c.type_label || c.ctype || "未分类"}</span></div>
        <div className="quote-grid"><blockquote>{c.quote_a || "未提供逐字引文"}</blockquote><blockquote>{c.quote_b || "未提供逐字引文"}</blockquote></div>
        <p><b>可能的口径漂移：</b>{c.could_be_drift}</p><p><b>还需要：</b>{c.needs_what}</p>
        <div className="ref-line">{(c.evidence_ids || []).map((id: string) => renderEvidenceRef(id))}{(c.source_ids || []).map((id: string) => renderSourceRef(id))}</div>
      </article>)}</div>
      {!data?.contradictions.length && <Empty title="尚无记录矛盾" detail="没有手工或引擎识别的矛盾记录。" />}
    </>;
  }

  function HypothesesPage() {
    const posteriors = data?.bayesian?.posteriors || [];
    const qualitative = Array.isArray(data?.qualitative) ? data?.qualitative : (data?.qualitative?.scores || []);
    const qualMap = new Map<string, Row>();
    qualitative.forEach((q: Row) => qualMap.set(q.hypothesis_id, q));
    return <>
      <SectionHeading eyebrow="COMPETING EXPLANATIONS / 07" title="假设实验室" description="后验排序、定性分数、支持与反对证据分别展示。似然是分析判断，不等于真实犯罪概率。" />
      <div className="notice verdict-notice">贝叶斯结论：<b>{data?.bayesian?.verdict || "尚未生成"}</b><span>{data?.bayesian?.disclosure || ""}</span></div>
      <div className="list-stack">{posteriors.map((p: Row, i: number) => {
        const h = data?.hypotheses.find((x) => x.hypothesis_id === p.hypothesis_id);
        const q = qualMap.get(p.hypothesis_id) as Row | undefined;
        return <article className="panel hypothesis-card" key={p.hypothesis_id}>
          <div className="hypothesis-head"><div><span className="rank">#{i+1}</span><b>{p.hypothesis_id}</b><p>{h?.description || p.description || "假设描述未提供"}</p></div><strong>{pct(p.posterior)}</strong></div>
          <div className="bar-track"><span style={{ width: Math.max(2, Number(p.posterior || 0) * 100) + "%" }} /></div>
          <div className="hypothesis-stats"><span>先验 {pct(p.prior)}</span><span>定性净分 {text(q?.net_score ?? q?.net)}</span><span>状态 {h?.status || "open"}</span></div>
          {h && <div className="hypothesis-columns">
            <div><b>支持</b><div className="ref-line">{(h.supports || []).map((id: string) => renderEvidenceRef(id))}</div></div>
            <div><b>反对</b><div className="ref-line">{(h.opposes || []).map((id: string) => renderEvidenceRef(id))}</div></div>
            <div><b>未解释</b><div className="ref-line">{(h.unexplained || []).map((id: string) => renderEvidenceRef(id))}</div></div>
          </div>}
          {h && h.predictions?.length > 0 && <details><summary>可验证预测与证伪条件</summary><ul>{h.predictions.map((x: string, j: number) => <li key={j}>{x}</li>)}</ul><ul>{(h.falsifiers || []).map((x: string, j: number) => <li key={j}>证伪：{x}</li>)}</ul></details>}
        </article>;
      })}</div>
      {!posteriors.length && <Empty title="尚未生成假设排序" detail="当前报告没有贝叶斯后验数据。" />}
    </>;
  }

  function PlanPage() {
    const plan = data?.plan || [];
    return <>
      <SectionHeading eyebrow="NEXT BEST ACTIONS / 08" title="调查计划" description="任务来自引擎调查计划。优先验证单来源主张、关键矛盾和能区分竞争假设的资料。" />
      <div className="list-stack">{plan.map((task, i) => <article className="panel task-card" key={task.task_id || i}>
        <div className="task-top"><span className="rank">#{i+1}</span><span className="source-id">{task.task_id || "TASK"}</span><span className="tag">{task.status || task.priority || "open"}</span></div>
        <h3>{task.question || task.title || "待调查问题"}</h3><p>{task.purpose || ""}</p>
        <div className="task-grid"><div><b>预期信息</b><span>{task.expected_info || "—"}</span></div><div><b>若证实</b><span>{task.impact_if_yes || "—"}</span></div><div><b>若否定</b><span>{task.impact_if_no || "—"}</span></div><div><b>渠道</b><span>{task.source_or_channel || "—"}</span></div></div>
        {(task.hypotheses || []).length > 0 && <div className="ref-line">{task.hypotheses.map((h: string) => <span className="ref-chip static" key={h}>{h}</span>)}</div>}
      </article>)}</div>
      {!plan.length && <Empty title="尚无调查任务" detail="引擎尚未生成下一步调查计划。" />}
    </>;
  }

  function ReviewPage() {
    const review = data?.review || {};
    const findings = review.findings || [];
    return <>
      <SectionHeading eyebrow="ADVERSARIAL AUDIT / 09" title="独立审查室" description="反方审查必须列出具体反证；blocker未清零时不得将报告当作最终结论。" />
      <div className="metrics-grid">
        <Metric label="审查状态" value={review.passed ? "通过" : "未通过"} />
        <Metric label="Blockers" value={String(review.blockers ?? "—")} />
        <Metric label="发现项" value={String(findings.length)} />
        <Metric label="审查角色" value={String(new Set(findings.map((x: Row) => x.role)).size)} />
      </div>
      <div className="list-stack">{findings.map((f: Row, i: number) => <article className="panel review-row" key={f.finding_id || i}>
        <div className="panel-title"><b>{f.role || "审查项"}</b><span className={"tag " + (f.severity === "blocker" ? "tag-danger" : "")}>{f.severity || "note"}</span></div>
        <p>{f.message || f.finding || JSON.stringify(f)}</p>
        {f.evidence_ids && <div className="ref-line">{f.evidence_ids.map((id: string) => renderEvidenceRef(id))}</div>}
      </article>)}</div>
      {!findings.length && <Empty title="没有审查发现项" detail="以报告中的审查状态为准；空列表不等于独立复核完成。" />}
    </>;
  }

  function ReportPage() {
    return <>
      <SectionHeading eyebrow="AUDITABLE OUTPUT / 10" title="最终报告" description="报告由结构化引擎生成。自动调查草稿与手工案包报告的审查状态不同，不能混用。" right={data?.reportUrl ? <a className="primary-link" href={data.reportUrl} download>下载Markdown ↓</a> : null} />
      <div className="notice">当前案件：{data?.case.case_id}。任何模型排序都必须与证据等级、来源数量、覆盖缺口和独立审查一起阅读。</div>
      {data?.reportMarkdown ? <pre className="report-preview">{data.reportMarkdown}</pre> : <Empty title="报告尚未生成" detail="本案没有可读取的引擎报告Markdown。" />}
      {data?.limits?.length ? <div className="panel"><h3>研究限制</h3><ul>{data.limits.map((x, i) => <li key={i}>{x}</li>)}</ul></div> : null}
    </>;
  }

  let content: ReactNode = null;
  if (loading && !data) content = <Empty title="正在载入案件数据" detail="从静态案包与引擎报告读取，不使用演示数据。" />;
  else if (error && !data) content = <Empty title="数据载入失败" detail={error} />;
  else if (!data) content = <Empty title="没有可展示的数据" detail="请先在案件中心选择一个已构建的案包。" />;
  else {
    switch (tab) {
      case "cases": content = <CaseCenter />; break;
      case "sources": content = <SourcesPage />; break;
      case "evidence": content = <EvidencePage />; break;
      case "timeline": content = <TimelinePage />; break;
      case "graph": content = <GraphPage />; break;
      case "contradictions": content = <ContradictionsPage />; break;
      case "hypotheses": content = <HypothesesPage />; break;
      case "plan": content = <PlanPage />; break;
      case "review": content = <ReviewPage />; break;
      case "report": content = <ReportPage />; break;
    }
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">D<span>·</span>OS</div><div><b>DETECTIVE OS</b><small>INTELLIGENCE WORKBENCH</small></div></div>
      <div className="side-caption">INVESTIGATION MODULES</div>
      <nav>{NAV.map((item) => <button key={item.id} className={"nav-item " + (tab === item.id ? "active" : "")}
        onClick={() => { setTab(item.id); setQuery(""); setSelectedEvidence(""); setSelectedSource(""); }}>
        <span className="nav-index">{item.icon}</span><span><b>{item.label}</b><small>{item.sub}</small></span>
      </button>)}</nav>
      <div className="sidebar-bottom"><span className="live-dot" /> SECURE OPERATIONS LINK <small>LIVE QUEUE · ARCHIVED FILES</small></div>
    </aside>
    <main className="main-shell">
      <header className="topbar">
        <div><div className="eyebrow">REAL CASE RESEARCH / EVIDENCE FIRST</div><h1>{NAV.find((x) => x.id === tab)?.label || "案件中心"}</h1></div>
        <div className="top-actions">
          <label className="case-picker"><span>ACTIVE CASE</span><select value={activeCaseId} onChange={(e) => { setActiveCaseId(e.target.value); setTab("cases"); }}>
            {index.map((x) => <option key={x.case_id} value={x.case_id}>{x.case_id}</option>)}
          </select></label>
          <a className="environment-pill" href="/investigate.html">NEW INVESTIGATION ↗</a>
        </div>
      </header>
      <div className="workspace">
        {activeIndex && <div className="active-case-strip"><b>{activeIndex.name}</b><span>{activeIndex.case_id}</span><span>{activeIndex.evidence_count} EVIDENCE</span></div>}
        {content}
      </div>
      <footer className="footer-note">DETECTIVE OS · 公开资料研究工具 · 推断不是事实 · 不作现实个人指控</footer>
    </main>
  </div>;
}
