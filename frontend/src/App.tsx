import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Activity, ArrowDownToLine, ArrowLeftRight, ArrowRight, Bell, BookOpenText,
  Building2, Check, ChevronDown, CircleHelp, Clock3, Database, FileSpreadsheet, FileUp,
  Fingerprint, Gauge, LayoutDashboard, ListChecks, LockKeyhole, Menu, Network,
  RefreshCw, Search, ShieldAlert, ShieldCheck, SlidersHorizontal, Sparkles, UploadCloud,
  Users, X, Zap,
} from "lucide-react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) || "http://127.0.0.1:8000";
let accessToken: string | null = null;

type CurrentUser = { id: string; email: string; display_name: string; role: string };
type CaseItem = {
  id: string; case_reference: string; analysis_run_id: string; alert_id: string; title: string;
  severity: string; status: string; disposition: string | null; subject_reference: string | null;
  alert_snapshot: AlertItem; analyst_notes: string; created_at: string; updated_at: string;
  assigned_to: string | null; created_by: string; investigation_report?: Record<string, any> | null;
};
type PolicyDoc = { id: string; title: string; file_name: string; page_count: number; chunk_count: number; created_at: string | null };
type PolicyResult = { chunk_id: string; document_id: string; title: string; citation: string; page_number: number | null; score: number; content: string };

type ColumnInfo = { name: string; inferred_type: string; null_count: number; sample_values: string[] };
type PreviewData = {
  filename?: string;
  format?: string;
  kind?: string;
  engine?: string;
  table?: string;
  schema?: string | null;
  row_count: number;
  truncated?: boolean;
  columns: ColumnInfo[];
  preview_rows: Record<string, string | null>[];
  mapping_suggestions: Record<string, string | null>;
  warnings: string[];
  sheet_names?: string[];
};
type AlertItem = {
  alert_id: string;
  rule_id: string;
  rule_version: string;
  severity: "high" | "medium" | "low" | string;
  status: string;
  title: string;
  explanation: string;
  subject_reference?: string | null;
  evidence_row_numbers: number[];
  evidence_count: number;
  measured_values: Record<string, unknown>;
  interpretation: string;
};
type AnalysisResult = {
  source?: Record<string, unknown>;
  summary: {
    total_transactions: number;
    analyzed_transactions: number;
    excluded_transactions: number;
    date_range: { start: string; end: string } | null;
    unique_source_accounts: number;
    unique_destination_accounts: number;
    unique_customers: number;
    alert_count: number;
    alerts_by_severity: Record<string, number>;
  };
  totals_by_currency: { currency: string; transaction_count: number; total_amount: number | null; average_amount: number | null; median_amount: number | null; maximum_amount: number | null }[];
  data_quality: { finding_key: string; severity: string; message: string; affected_rows: number; example_row_numbers: number[] }[];
  alerts: AlertItem[];
  rule_counts: Record<string, number>;
  options_used: Record<string, number>;
  warnings: string[];
  analysis_run_id?: string;
};
type CanonicalField = "timestamp" | "amount" | "source_account" | "transaction_id" | "destination_account" | "customer_id" | "currency" | "transaction_type" | "channel" | "status" | "country" | "balance_after";
type SqlConnection = {
  engine: "postgresql" | "mysql" | "sqlite";
  host: string;
  port: string;
  database: string;
  username: string;
  password: string;
  sqlite_path: string;
};
type Notice = { kind: "success" | "error" | "info"; text: string };

const EMPTY_MAPPING: Record<CanonicalField, string | null> = {
  timestamp: null, amount: null, source_account: null, transaction_id: null,
  destination_account: null, customer_id: null, currency: null, transaction_type: null,
  channel: null, status: null, country: null, balance_after: null,
};
const FIELDS: { key: CanonicalField; label: string; required?: boolean; hint: string }[] = [
  { key: "timestamp", label: "Transaction timestamp", required: true, hint: "Posting date / transaction time" },
  { key: "amount", label: "Transaction amount", required: true, hint: "Numeric value in source currency" },
  { key: "source_account", label: "Source account", required: true, hint: "Debit / originator account" },
  { key: "destination_account", label: "Destination account", hint: "Credit / beneficiary account" },
  { key: "transaction_id", label: "Transaction ID", hint: "Reference number" },
  { key: "customer_id", label: "Customer ID", hint: "Customer or CIF identifier" },
  { key: "currency", label: "Currency", hint: "PKR, USD, etc. — never inferred as PKR" },
  { key: "transaction_type", label: "Transaction type", hint: "Transfer, cash, card, reversal..." },
  { key: "channel", label: "Channel", hint: "Branch, mobile, ATM, agent..." },
  { key: "status", label: "Transaction status", hint: "Posted, pending, reversed..." },
  { key: "country", label: "Country", hint: "Optional geography field" },
  { key: "balance_after", label: "Balance after", hint: "Optional available/closing balance" },
];

const navItems = [
  { key: "overview", label: "Overview", icon: LayoutDashboard },
  { key: "sources", label: "Data sources", icon: Database },
  { key: "alerts", label: "Alerts & signals", icon: ShieldAlert },
  { key: "investigations", label: "Investigations", icon: ListChecks },
  { key: "cases", label: "Investigation cases", icon: ListChecks },
  { key: "policies", label: "Policy intelligence", icon: BookOpenText },
  { key: "audit", label: "Audit trail", icon: ShieldCheck },
  { key: "quality", label: "Data quality", icon: Activity },
] as const;
type PageKey = typeof navItems[number]["key"];

const INITIAL_SQL: SqlConnection = {
  engine: "postgresql", host: "localhost", port: "5432", database: "", username: "", password: "", sqlite_path: "sample.db",
};
const INITIAL_OPTIONS = {
  large_amount_threshold: 1000000,
  velocity_count_threshold: 10,
  velocity_window_minutes: 60,
  structuring_reference_threshold: 1000000,
  structuring_min_transactions: 3,
  structuring_window_hours: 24,
  outlier_mad_multiplier: 6,
  outlier_min_transactions: 8,
};

async function apiRequest(path: string, init: RequestInit = {}) {
  let response: Response;
  try {
    const headers = new Headers(init.headers || {});
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
    response = await fetch(API_BASE + path, { ...init, headers });
  } catch {
    throw new Error(`Cannot reach the SentinelAML API at ${API_BASE}. Start the backend and try again.`);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data?.detail || data?.error?.message || "The request could not be completed.";
    const details = data?.error?.details;
    throw new Error(Array.isArray(details) && details.length ? `${message} ${details.map((d: { message?: string }) => d.message).join(" ")}` : String(message));
  }
  return data;
}

function number(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
  return Number(value).toLocaleString("en-US", { maximumFractionDigits: 2 });
}
function compact(value: number | undefined) {
  if (value === undefined) return "—";
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}
function dateLabel(value?: string) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}
function severityClass(severity: string) {
  return severity === "high" ? "severity-high" : severity === "medium" ? "severity-medium" : "severity-low";
}
function ruleLabel(rule: string) {
  return rule.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (letter: string) => letter.toUpperCase());
}

function NoticeBar({ notice, onClose }: { notice: Notice; onClose: () => void }) {
  return (
    <div className={`notice notice-${notice.kind}`} role="status">
      {notice.kind === "success" ? <Check size={17} /> : notice.kind === "error" ? <ShieldAlert size={17} /> : <CircleHelp size={17} />}
      <span>{notice.text}</span>
      <button className="icon-button notice-close" aria-label="Dismiss message" onClick={onClose}><X size={16} /></button>
    </div>
  );
}

function MappingEditor({
  preview, mapping, onChange,
}: {
  preview: PreviewData;
  mapping: Record<CanonicalField, string | null>;
  onChange: (field: CanonicalField, value: string | null) => void;
}) {
  return (
    <div className="mapping-grid">
      {FIELDS.map((field) => (
        <label className="mapping-field" key={field.key}>
          <span className="mapping-label">{field.label}{field.required && <em className="required-star"> *</em>}</span>
          <select value={mapping[field.key] || ""} onChange={(event) => onChange(field.key, event.target.value || null)}>
            <option value="">Not mapped</option>
            {preview.columns.map((column) => <option key={column.name} value={column.name}>{column.name}</option>)}
          </select>
          <span className="mapping-hint">{field.hint}</span>
        </label>
      ))}
    </div>
  );
}

function AlertsTable({ alerts, onInspect }: { alerts: AlertItem[]; onInspect: (alert: AlertItem) => void }) {
  if (!alerts.length) return (
    <div className="empty-state small-empty">
      <div className="empty-icon"><ShieldCheck size={24} /></div>
      <h3>No alerts in this result</h3>
      <p>Try adjusting the demonstration thresholds, or inspect data-quality findings.</p>
    </div>
  );
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead><tr><th>Signal</th><th>Account</th><th>Severity</th><th>Evidence</th><th>Rule</th><th></th></tr></thead>
        <tbody>
          {alerts.map((alert) => (
            <tr key={alert.alert_id}>
              <td><div className="cell-title">{alert.title}</div><div className="cell-sub">{alert.alert_id}</div></td>
              <td className="mono">{alert.subject_reference || "—"}</td>
              <td><span className={`severity-pill ${severityClass(alert.severity)}`}><span />{alert.severity}</span></td>
              <td>{alert.evidence_count} row{alert.evidence_count === 1 ? "" : "s"}</td>
              <td><span className="rule-tag">{ruleLabel(alert.rule_id)}</span></td>
              <td><button className="text-button" onClick={() => onInspect(alert)}>Review <ArrowRight size={14} /></button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Sparkline({ values, color = "#2dd4bf", height = 42 }: { values: number[]; color?: string; height?: number }) {
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const points = values.map((value, index) => {
    const x = values.length < 2 ? 50 : (index / (values.length - 1)) * 180;
    const y = 34 - ((value - min) / Math.max(1, max - min)) * 28;
    return `${x},${y}`;
  }).join(" ");
  return <svg className="sparkline" viewBox="0 0 180 42" preserveAspectRatio="none" style={{ height }} aria-hidden="true">
    <polyline points={points} fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>;
}

function MiniDonut({ high, medium, low }: { high: number; medium: number; low: number }) {
  const total = Math.max(1, high + medium + low);
  const highEnd = high / total * 100;
  const mediumEnd = highEnd + medium / total * 100;
  return <div className="donut-visual" style={{ background: `conic-gradient(#fb7185 0 ${highEnd}%, #fbbf24 ${highEnd}% ${mediumEnd}%, #2dd4bf ${mediumEnd}% 100%)` }}>
    <div className="donut-hole"><strong>{number(total)}</strong><span>Total alerts</span></div>
  </div>;
}

function MiniWorldMap() {
  const dots = Array.from({ length: 210 }, (_, i) => {
    const row = Math.floor(i / 21);
    const column = i % 21;
    const cx = 12 + column * 8.3;
    const cy = 10 + row * 8.1;
    const land = (column >= 1 && column <= 7 && row >= 1 && row <= 5 && !(column < 3 && row > 3))
      || (column >= 7 && column <= 10 && row >= 2 && row <= 7)
      || (column >= 11 && column <= 19 && row >= 1 && row <= 5 && !(column > 16 && row > 3))
      || (column >= 15 && column <= 19 && row >= 6 && row <= 8);
    if (!land) return null;
    const highlight = [28, 54, 90, 126, 157].includes(i);
    return <circle key={i} cx={cx} cy={cy} r={highlight ? 2.5 : 1.1} fill={highlight ? "#2dd4bf" : "#254a64"} opacity={highlight ? 1 : .7} />;
  });
  return <svg className="world-map" viewBox="0 0 190 105" role="img" aria-label="Illustrative dot map with synthetic activity markers">{dots}
    <circle cx="40" cy="30" r="10" fill="#2dd4bf" opacity=".08" /><circle cx="40" cy="30" r="4" fill="#2dd4bf" opacity=".6" />
    <circle cx="111" cy="45" r="11" fill="#2dd4bf" opacity=".08" /><circle cx="111" cy="45" r="4" fill="#2dd4bf" opacity=".65" />
    <circle cx="147" cy="53" r="10" fill="#2dd4bf" opacity=".08" /><circle cx="147" cy="53" r="3.5" fill="#2dd4bf" opacity=".6" />
  </svg>;
}

function LoginScreen({ email, password, setEmail, setPassword, onSubmit, busy, error }: {
  email: string; password: string; setEmail: (value: string) => void; setPassword: (value: string) => void;
  onSubmit: () => void; busy: boolean; error: string;
}) {
  return <div className="login-shell">
    <div className="login-ambient login-ambient-one" /><div className="login-ambient login-ambient-two" />
    <section className="login-card">
      <div className="brand-lockup login-brand"><div className="brand-mark"><Fingerprint size={23} /></div><div><div className="brand-name">Sentinel<span>AML</span></div><div className="brand-subtitle">RISK INTELLIGENCE</div></div></div>
      <div className="login-overline"><ShieldCheck size={15} /> SECURE ANALYST WORKSPACE</div>
      <h1>Welcome back.</h1><p className="login-intro">Sign in to investigate financial crime signals, review evidence and explore approved compliance policies.</p>
      <form onSubmit={(event) => { event.preventDefault(); onSubmit(); }}>
        <label className="login-field"><span>Work email</span><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" required /></label>
        <label className="login-field"><span>Password</span><input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required /></label>
        {error && <div className="login-error" role="alert"><ShieldAlert size={15} />{error}</div>}
        <button className="btn btn-primary login-submit" disabled={busy}>{busy ? <RefreshCw className="spin" size={16} /> : <LockKeyhole size={16} />} Sign in securely</button>
      </form>
      <div className="login-local-note"><LockKeyhole size={15} /><span>Local prototype · no public registration. Configure your credentials in <code>backend/.env</code>.</span></div>
    </section>
    <div className="login-footer">SentinelAML <span>•</span> Explainable signals. Human-led decisions.</div>
  </div>;
}

const DEMO_ALERTS: AlertItem[] = [
  { alert_id: "DEMO-ALR-78491", rule_id: "POSSIBLE_STRUCTURING", rule_version: "demo", severity: "high", status: "needs_review", title: "Repeated near-threshold activity", explanation: "Synthetic demo alert: several transactions fall just below a configurable reference threshold in a short period. The pattern requires context and does not establish intent.", subject_reference: "DEMO-ACC-1042", evidence_row_numbers: [12, 14, 18], evidence_count: 3, measured_values: { transaction_count: 3, window_hours: 24, data_source: "synthetic demo" }, interpretation: "Synthetic signal for interface demonstration only." },
  { alert_id: "DEMO-ALR-78490", rule_id: "VELOCITY_SPIKE", rule_version: "demo", severity: "high", status: "needs_review", title: "Unusual transaction frequency", explanation: "Synthetic demo alert: transaction velocity crossed the configured demonstration threshold.", subject_reference: "DEMO-ACC-0831", evidence_row_numbers: [28, 29, 30, 31], evidence_count: 4, measured_values: { transaction_count: 12, window_minutes: 60 }, interpretation: "Synthetic signal for interface demonstration only." },
  { alert_id: "DEMO-ALR-78489", rule_id: "HIGH_VALUE", rule_version: "demo", severity: "medium", status: "needs_review", title: "High-value transaction", explanation: "Synthetic demo alert: one transaction meets the configured value threshold.", subject_reference: "DEMO-ACC-0217", evidence_row_numbers: [44], evidence_count: 1, measured_values: { amount: 1500000, currency: "PKR", threshold: 1000000 }, interpretation: "Synthetic signal for interface demonstration only." },
  { alert_id: "DEMO-ALR-78488", rule_id: "ROBUST_AMOUNT_OUTLIER", rule_version: "demo", severity: "medium", status: "needs_review", title: "Account-level amount outlier", explanation: "Synthetic demo alert: an amount is unusually large compared with the imported account baseline.", subject_reference: "DEMO-ACC-1104", evidence_row_numbers: [52], evidence_count: 1, measured_values: { configured_multiplier: 6, baseline: "synthetic" }, interpretation: "Synthetic signal for interface demonstration only." },
  { alert_id: "DEMO-ALR-78487", rule_id: "DUPLICATE_TRANSACTION_ID", rule_version: "demo", severity: "low", status: "needs_review", title: "Duplicate transaction reference", explanation: "Synthetic demo alert: the same transaction reference appears in multiple rows and should be checked against source-system retry or reversal semantics.", subject_reference: "DEMO-ACC-0590", evidence_row_numbers: [63, 64], evidence_count: 2, measured_values: { row_count: 2 }, interpretation: "Synthetic signal for interface demonstration only." },
];

function App() {
  const [page, setPage] = useState<PageKey>("overview");
  const [accessTokenState, setAccessTokenState] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [loginEmail, setLoginEmail] = useState("sentinel.admin@sentinelaml.local");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginBusy, setLoginBusy] = useState(false);
  const [loginError, setLoginError] = useState("");
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [selectedCase, setSelectedCase] = useState<CaseItem | null>(null);
  const [caseQuestion, setCaseQuestion] = useState("");
  const [caseBusy, setCaseBusy] = useState(false);
  const [policyDocs, setPolicyDocs] = useState<PolicyDoc[]>([]);
  const [policyQuery, setPolicyQuery] = useState("");
  const [policyResults, setPolicyResults] = useState<PolicyResult[]>([]);
  const [auditEvents, setAuditEvents] = useState<Record<string, unknown>[]>([]);
  const [sourceMode, setSourceMode] = useState<"file" | "sql">("file");
  const [file, setFile] = useState<File | null>(null);
  const [sheetName, setSheetName] = useState("");
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [mapping, setMapping] = useState<Record<CanonicalField, string | null>>(EMPTY_MAPPING);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [sql, setSql] = useState<SqlConnection>(INITIAL_SQL);
  const [sqlConnected, setSqlConnected] = useState(false);
  const [tables, setTables] = useState<{ schema: string | null; name: string }[]>([]);
  const [selectedTable, setSelectedTable] = useState("");
  const [selectedSchema, setSelectedSchema] = useState<string | null>(null);
  const [options, setOptions] = useState(INITIAL_OPTIONS);
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);
  const [mobileNav, setMobileNav] = useState(false);

  const setMappingField = (field: CanonicalField, value: string | null) => setMapping((current) => ({ ...current, [field]: value }));
  const requiredMapped = Boolean(mapping.timestamp && mapping.amount && mapping.source_account);
  const totalHigh = result?.summary.alerts_by_severity.high || 0;
  const totalMedium = result?.summary.alerts_by_severity.medium || 0;
  const currentNavLabel = navItems.find((item) => item.key === page)?.label || "Overview";
  const visibleAlerts = useMemo(() => result?.alerts || [], [result]);
  const isDemoPreview = !result;
  const dashboardAlerts = result ? result.alerts.slice(0, 5) : DEMO_ALERTS;
  const metricTotalAlerts = result ? result.summary.alert_count : 1248;
  const metricHighAlerts = result ? result.summary.alerts_by_severity.high || 0 : 126;
  const metricTransactions = result ? result.summary.total_transactions : 2430000;
  const metricAccounts = result ? result.summary.unique_source_accounts : 2431;
  const metricOpenCases = cases.filter((item) => item.status === "open" || item.status === "in_review").length;
  const metricAverageRisk = result ? Math.min(99, Math.round((metricHighAlerts / Math.max(result.summary.alert_count, 1)) * 100)) : 68;

  // Keep SQL credentials in memory only; clear them when leaving the connector workflow.
  useEffect(() => {
    if (page !== "sources" || sourceMode !== "sql") {
      setSql((current) => current.username || current.password || current.database
        ? { ...current, username: "", password: "", database: "" }
        : current);
      setSqlConnected(false);
      setTables([]);
      setSelectedTable("");
      setSelectedSchema(null);
    }
  }, [page, sourceMode]);

  useEffect(() => {
    if (!accessTokenState) return;
    const loadPageData = async () => {
      try {
        if (page === "cases" || page === "investigations") {
          const data = await apiRequest("/api/cases") as { cases: CaseItem[] };
          setCases(data.cases);
          if (selectedCase) {
            const refreshed = data.cases.find((item) => item.id === selectedCase.id);
            if (refreshed) setSelectedCase(refreshed);
          }
        }
        if (page === "policies") {
          const data = await apiRequest("/api/policies") as { documents: PolicyDoc[] };
          setPolicyDocs(data.documents);
        }
        if (page === "audit") {
          const data = await apiRequest("/api/audit") as { events: Record<string, unknown>[] };
          setAuditEvents(data.events);
        }
      } catch (error) {
        setNotice({ kind: "error", text: error instanceof Error ? error.message : "Could not load workspace records." });
      }
    };
    void loadPageData();
  }, [page, accessTokenState]);

  const signIn = async () => {
    setLoginBusy(true);
    setLoginError("");
    try {
      const data = await apiRequest("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: loginEmail, password: loginPassword }),
      }) as { access_token: string; user: CurrentUser };
      accessToken = data.access_token;
      setAccessTokenState(data.access_token);
      setCurrentUser(data.user);
      setLoginPassword("");
      setNotice({ kind: "success", text: `Signed in as ${data.user.display_name}.` });
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : "Sign in failed.");
    } finally {
      setLoginBusy(false);
    }
  };

  const signOut = () => {
    accessToken = null;
    setAccessTokenState(null);
    setCurrentUser(null);
    setResult(null);
    setPreview(null);
    setFile(null);
    setCases([]);
    setSelectedCase(null);
    setPage("overview");
    setNotice(null);
  };

  const openCaseFromAlert = async (alert: AlertItem) => {
    if (!result?.analysis_run_id) {
      setNotice({ kind: "info", text: "Upload and analyze a dataset before creating a persistent investigation case." });
      return;
    }
    setCaseBusy(true);
    try {
      const created = await apiRequest("/api/cases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ analysis_run_id: result.analysis_run_id, alert_id: alert.alert_id }),
      }) as CaseItem;
      setSelectedCase(created);
      const data = await apiRequest("/api/cases") as { cases: CaseItem[] };
      setCases(data.cases);
      setPage("investigations");
      setNotice({ kind: "success", text: `Investigation case ${created.case_reference} created and saved.` });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Could not create case." });
    } finally {
      setCaseBusy(false);
    }
  };

  const generateInvestigation = async () => {
    if (!selectedCase) return;
    setCaseBusy(true);
    try {
      const data = await apiRequest(`/api/cases/${selectedCase.id}/investigate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: caseQuestion || null }),
      }) as { case: CaseItem; workflow: Record<string, any> };
      setSelectedCase(data.case);
      setCases((items) => items.map((item) => item.id === data.case.id ? data.case : item));
      setNotice({ kind: "success", text: "Multi-agent investigation draft generated with evidence notes and policy citations for analyst review." });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Investigation workflow failed." });
    } finally {
      setCaseBusy(false);
    }
  };

  const changeCaseStatus = async (caseItem: CaseItem, status: string, disposition?: string) => {
    setCaseBusy(true);
    try {
      const updated = await apiRequest(`/api/cases/${caseItem.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, ...(disposition ? { disposition } : {}) }),
      }) as CaseItem;
      setCases((items) => items.map((item) => item.id === updated.id ? updated : item));
      if (selectedCase?.id === updated.id) setSelectedCase(updated);
      setNotice({ kind: "success", text: `Case ${updated.case_reference} updated to ${status.replaceAll("_", " ")}.` });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Could not update case." });
    } finally {
      setCaseBusy(false);
    }
  };

  const uploadPolicy = async (selected: File | null) => {
    if (!selected) return;
    setCaseBusy(true);
    setNotice(null);
    try {
      const form = new FormData();
      form.append("file", selected);
      const data = await apiRequest("/api/policies/upload", { method: "POST", body: form }) as { title: string; chunk_count: number };
      const listed = await apiRequest("/api/policies") as { documents: PolicyDoc[] };
      setPolicyDocs(listed.documents);
      setNotice({ kind: "success", text: `Policy document “${data.title}” indexed into ${data.chunk_count} searchable passages.` });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Policy upload failed." });
    } finally {
      setCaseBusy(false);
    }
  };

  const searchPolicies = async () => {
    if (policyQuery.trim().length < 3) {
      setNotice({ kind: "error", text: "Enter at least three characters to search the policy library." });
      return;
    }
    setCaseBusy(true);
    try {
      const data = await apiRequest("/api/policies/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: policyQuery, limit: 8 }),
      }) as { results: PolicyResult[] };
      setPolicyResults(data.results);
      setNotice({ kind: "info", text: `${data.results.length} matching passage(s) found using lexical search. Verify the original document and its current version.` });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Policy search failed." });
    } finally {
      setCaseBusy(false);
    }
  };

  const chooseFile = (selected: File | null) => {
    setFile(selected);
    setPreview(null);
    setResult(null);
    if (selected) {
      setSourceMode("file");
      setNotice({ kind: "info", text: `${selected.name} selected. Preview the columns before analyzing.` });
    }
  };

  const previewFile = async () => {
    if (!file) {
      setNotice({ kind: "error", text: "Choose a CSV or Excel file first." });
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      const form = new FormData();
      form.append("file", file);
      if (sheetName) form.append("sheet_name", sheetName);
      const data = await apiRequest("/api/files/preview", { method: "POST", body: form }) as PreviewData;
      setPreview(data);
      setMapping({ ...EMPTY_MAPPING, ...data.mapping_suggestions });
      setResult(null);
      setNotice({ kind: "success", text: `Preview ready: ${number(data.row_count)} rows and ${data.columns.length} columns detected.` });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "File preview failed." });
    } finally {
      setBusy(false);
    }
  };

  const analyzeFile = async () => {
    if (!file || !preview) {
      setNotice({ kind: "error", text: "Preview the file before starting analysis." });
      return;
    }
    if (!requiredMapped) {
      setNotice({ kind: "error", text: "Map the timestamp, amount, and source account fields first." });
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("mapping", JSON.stringify(mapping));
      form.append("options", JSON.stringify(options));
      if (sheetName) form.append("sheet_name", sheetName);
      const data = await apiRequest("/api/files/analyze", { method: "POST", body: form }) as AnalysisResult;
      setResult(data);
      setPage("overview");
      setNotice({ kind: "success", text: `Analysis complete. ${number(data.summary.analyzed_transactions)} valid transactions examined and ${number(data.summary.alert_count)} review signals generated.` });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Analysis failed." });
    } finally {
      setBusy(false);
    }
  };

  const updateSql = (field: keyof SqlConnection, value: string) => setSql((current) => ({ ...current, [field]: value }));
  const sqlBody = () => {
    const credentials: Record<string, unknown> = { engine: sql.engine };
    if (sql.engine === "sqlite") credentials.sqlite_path = sql.sqlite_path;
    else {
      credentials.host = sql.host.trim();
      credentials.port = sql.port ? Number(sql.port) : undefined;
      credentials.database = sql.database.trim();
      credentials.username = sql.username.trim();
      credentials.password = sql.password;
    }
    return credentials;
  };

  const connectSql = async () => {
    setBusy(true);
    setNotice(null);
    try {
      await apiRequest("/api/sql/test", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(sqlBody()) });
      const tableResult = await apiRequest("/api/sql/tables", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(sqlBody()) }) as { tables: { schema: string | null; name: string }[] };
      setTables(tableResult.tables);
      setSqlConnected(true);
      setSelectedTable("");
      setSelectedSchema(null);
      setPreview(null);
      setResult(null);
      setNotice({ kind: "success", text: `Database connection confirmed. ${tableResult.tables.length} accessible tables found. Credentials are used request-by-request and are not saved by SentinelAML.` });
    } catch (error) {
      setSqlConnected(false);
      setTables([]);
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Database connection failed." });
    } finally {
      setBusy(false);
    }
  };

  const previewSql = async () => {
    if (!selectedTable) {
      setNotice({ kind: "error", text: "Select a table to preview." });
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      const body = { ...sqlBody(), schema_name: selectedSchema, table_name: selectedTable, limit: 500 };
      const data = await apiRequest("/api/sql/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }) as PreviewData;
      setPreview(data);
      setMapping({ ...EMPTY_MAPPING, ...data.mapping_suggestions });
      setResult(null);
      setNotice({ kind: "success", text: `Preview ready: ${number(data.row_count)} rows shown from ${selectedTable}.` });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Table preview failed." });
    } finally {
      setBusy(false);
    }
  };

  const analyzeSql = async () => {
    if (!preview || !selectedTable || !requiredMapped) {
      setNotice({ kind: "error", text: "Select and preview a table, then map timestamp, amount, and source account." });
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      const body = { ...sqlBody(), schema_name: selectedSchema, table_name: selectedTable, limit: 5000, mapping, options };
      const data = await apiRequest("/api/sql/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }) as AnalysisResult;
      setResult(data);
      setPage("overview");
      setNotice({ kind: "success", text: `SQL analysis complete. ${number(data.summary.analyzed_transactions)} valid rows analyzed.` });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "SQL analysis failed." });
    } finally {
      setBusy(false);
    }
  };

  const clearSqlCredentials = () => {
    setSql((current) => ({ ...current, password: "", username: "", database: "" }));
    setSqlConnected(false);
    setTables([]);
    setSelectedTable("");
    setNotice({ kind: "info", text: "Username, password and database name cleared from this page's component state." });
  };

  const exportAlerts = () => {
    if (!result) return;
    const headers = ["alert_id", "rule_id", "severity", "title", "subject_reference", "evidence_row_numbers", "explanation"];
    const escapeCsv = (value: unknown) => {
      const rawText = Array.isArray(value) ? value.join("; ") : String(value ?? "");
      // Prevent spreadsheet formula injection from source-controlled account identifiers.
      const safeText = /^[=+\-@\t\r]/.test(rawText) ? "'" + rawText : rawText;
      return `"${safeText.replace(/"/g, '""')}"`;
    };
    const csv = [headers.join(","), ...result.alerts.map((alert) => headers.map((header) => escapeCsv((alert as unknown as Record<string, unknown>)[header])).join(","))].join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "sentinelaml-alerts-review.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  const resetWorkspace = () => {
    setFile(null); setPreview(null); setResult(null); setMapping(EMPTY_MAPPING); setSelectedAlert(null);
    setNotice({ kind: "info", text: "Workspace results cleared. Your original source file was never saved by this page." });
  };

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
        <div className="brand-lockup">
          <div className="brand-mark"><Fingerprint size={23} strokeWidth={1.9} /></div>
          <div><div className="brand-name">Sentinel<span>AML</span></div><div className="brand-subtitle">RISK INTELLIGENCE</div></div>
          <button className="icon-button mobile-close" onClick={() => setMobileNav(false)} aria-label="Close navigation"><X size={18} /></button>
        </div>
        <div className="workspace-switcher">
          <div className="workspace-avatar"><Building2 size={17} /></div>
          <div className="workspace-copy"><strong>Analyst workspace</strong><small>Local prototype</small></div>
          <ChevronDown size={15} className="muted-icon" />
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          {navItems.map((item) => (
            <button key={item.key} className={`nav-item ${page === item.key ? "active" : ""}`} onClick={() => { setPage(item.key); setMobileNav(false); }}>
              <item.icon size={18} strokeWidth={1.8} /><span>{item.label}</span>
              {item.key === "alerts" && result && result.summary.alert_count > 0 && <span className="nav-count">{result.summary.alert_count}</span>}
            </button>
          ))}
        </nav>
        <div className="nav-label tools-label">PLATFORM</div>
        <button className="nav-item" onClick={() => { setPage("sources"); setSourceMode("sql"); setMobileNav(false); }}><ArrowLeftRight size={18} strokeWidth={1.8} /><span>Database connectors</span></button>
        <button className="nav-item" onClick={() => setNotice({ kind: "info", text: "Rule catalogue and design references are available in the repository's docs/ folder." })}><BookOpenText size={18} strokeWidth={1.8} /><span>Rule catalogue</span></button>
        <div className="sidebar-bottom">
          <div className="security-note"><div className="security-icon"><LockKeyhole size={16} /></div><div><strong>Privacy-first MVP</strong><p>Results are held in this browser session. Use synthetic data.</p></div></div>
          <div className="user-profile"><div className="user-avatar">SA</div><div><strong>Sentinel Analyst</strong><small>Prototype operator</small></div><ChevronDown size={15} className="muted-icon" /></div>
        </div>
      </aside>

      {mobileNav && <button className="mobile-scrim" aria-label="Close navigation overlay" onClick={() => setMobileNav(false)} />}

      <main className="main-shell">
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button mobile-menu" onClick={() => setMobileNav(true)} aria-label="Open navigation"><Menu size={20} /></button>
            <div className="breadcrumb"><span>SentinelAML</span><span className="crumb-slash">/</span><strong>{currentNavLabel}</strong></div>
          </div>
          <div className="topbar-actions">
            <span className="environment-chip"><span /> Prototype environment</span>
            <button className="icon-button" aria-label="Help" onClick={() => setNotice({ kind: "info", text: "Start from Data sources: preview a CSV/Excel file or test an approved SQL connection, map columns, then run analysis." })}><CircleHelp size={18} /></button>
            <button className="icon-button notification-button" aria-label="Notifications" onClick={() => setPage("alerts")}><Bell size={18} />{result && result.summary.alert_count > 0 && <i />}</button>
          </div>
        </header>

        <div className="page-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow"><span className="eyebrow-dot" /> FINANCIAL CRIME INTELLIGENCE</div>
              <h1>{page === "overview" ? "Risk overview" : currentNavLabel}</h1>
              <p>{page === "overview" ? "Turn transaction data into explainable signals for analyst review." : page === "sources" ? "Import transaction records or securely inspect an approved SQL source." : page === "alerts" ? "Review rule-triggered signals and inspect the underlying evidence." : page === "quality" ? "Understand missing, invalid, or inconsistent transaction data." : "Case orchestration and human approvals are part of the next milestone."}</p>
            </div>
            <div className="heading-actions">
              {result && <button className="btn btn-secondary" onClick={resetWorkspace}><RefreshCw size={16} /> Clear run</button>}
              {result && <button className="btn btn-secondary" onClick={exportAlerts}><ArrowDownToLine size={16} /> Export alerts</button>}
              <button className="btn btn-primary" onClick={() => { setPage("sources"); setSourceMode("file"); }}><UploadCloud size={16} /> Import data</button>
            </div>
          </div>

          {notice && <NoticeBar notice={notice} onClose={() => setNotice(null)} />}

          {page === "overview" && (
            <section className="command-center">
              <div className="command-titlebar">
                <div>
                  <div className="command-overline"><span className="live-pulse" /> AML COMMAND CENTER</div>
                  <h2>Risk intelligence overview</h2>
                  <p>{isDemoPreview ? "Illustrative synthetic telemetry · Upload your data to replace all demo metrics." : `Latest analysis · ${result?.source?.filename || result?.source?.table || "Imported transaction data"}`}</p>
                </div>
                <div className="command-title-actions">
                  <span className={`data-state-pill ${isDemoPreview ? "demo-state" : "live-state"}`}><span />{isDemoPreview ? "SYNTHETIC DEMO" : "ANALYSIS LOADED"}</span>
                  <button className="btn btn-secondary" onClick={() => { setPage("sources"); setSourceMode("file"); }}><UploadCloud size={15} /> Import data</button>
                  {result && <button className="btn btn-primary" onClick={exportAlerts}><ArrowDownToLine size={15} /> Export</button>}
                </div>
              </div>

              <div className="command-kpis">
                <MetricCard icon={<ShieldAlert size={17} />} label="Total alerts" value={number(metricTotalAlerts)} note={result ? "Current analysis run" : "Demo-only example"} tone="teal" trend={result ? `${number(metricHighAlerts)} high priority` : "+18.6% vs previous period"} points={[12, 18, 15, 24, 20, 31, 36, 42]} />
                <MetricCard icon={<Activity size={17} />} label="High-risk alerts" value={number(metricHighAlerts)} note={result ? "Require analyst review" : "Illustrative sample"} tone="red" trend={result ? "Heuristic signal count" : "+2.4% vs previous period"} points={[28, 23, 33, 29, 41, 37, 49, 54]} />
                <MetricCard icon={<ListChecks size={17} />} label="Open investigations" value={number(metricOpenCases || (isDemoPreview ? 32 : 0))} note={isDemoPreview && !cases.length ? "Synthetic placeholder" : "Persisted case records"} tone="blue" trend={`${number(cases.filter((item) => item.status === "escalated").length)} escalated`} points={[10, 14, 13, 18, 16, 23, 20, 26]} />
                <MetricCard icon={<ArrowLeftRight size={17} />} label="Transactions analyzed" value={compact(metricTransactions)} note={result ? `${number(result.summary.analyzed_transactions)} valid rows` : "Synthetic example volume"} tone="green" trend={result ? `${number(result.summary.excluded_transactions)} excluded` : "Illustrative only"} points={[18, 20, 18, 30, 28, 35, 32, 43]} />
                <MetricCard icon={<Gauge size={17} />} label="Risk index" value={number(metricAverageRisk)} note={result ? "High-alert share index" : "Illustrative synthetic score"} tone="violet" trend={isDemoPreview ? "Demo score only" : "Not a probability of crime"} points={[16, 22, 20, 18, 28, 30, 26, 37]} />
              </div>

              <div className="command-grid command-grid-top">
                <section className="command-panel map-panel">
                  <div className="command-panel-heading"><div><h3>Exposure activity map</h3><p>{isDemoPreview ? "Illustrative markers · not real geographic or customer data" : "Geography is only available if your imported dataset contains it"}</p></div><span className="panel-tag">OVERVIEW</span></div>
                  <div className="map-panel-body"><div className="map-glow" /><MiniWorldMap /><div className="map-legend"><span><i className="legend-dot high-dot" /> High</span><span><i className="legend-dot medium-dot" /> Medium</span><span><i className="legend-dot low-dot" /> Low</span></div></div>
                  <div className="map-footer"><span><span className="status-dot" /> {isDemoPreview ? "Synthetic preview active" : `${number(result?.summary.unique_source_accounts)} source accounts in analysis`}</span><span>{isDemoPreview ? "No live feeds connected" : "No live feed connected"}</span></div>
                </section>

                <section className="command-panel risk-level-panel">
                  <div className="command-panel-heading"><div><h3>Alerts by risk level</h3><p>Rule severity distribution</p></div><button className="ghost-icon" onClick={() => setPage("alerts")} aria-label="Open alerts"><ArrowRight size={15} /></button></div>
                  <div className="donut-layout"><MiniDonut high={result ? result.summary.alerts_by_severity.high || 0 : 126} medium={result ? result.summary.alerts_by_severity.medium || 0 : 398} low={result ? result.summary.alerts_by_severity.low || 0 : 724} /><div className="donut-legend">
                    <div><span><i className="legend-dot high-dot" />High priority</span><strong>{number(result ? result.summary.alerts_by_severity.high || 0 : 126)}</strong></div>
                    <div><span><i className="legend-dot medium-dot" />Medium priority</span><strong>{number(result ? result.summary.alerts_by_severity.medium || 0 : 398)}</strong></div>
                    <div><span><i className="legend-dot low-dot" />Low priority</span><strong>{number(result ? result.summary.alerts_by_severity.low || 0 : 724)}</strong></div>
                  </div></div>
                  <div className="panel-footnote">{isDemoPreview ? "Sample values are fabricated for UI preview." : "Severity indicates configured review priority, not criminal intent."}</div>
                </section>

                <section className="command-panel countries-panel">
                  <div className="command-panel-heading"><div><h3>{isDemoPreview ? "Illustrative risk regions" : "Geographic risk signals"}</h3><p>{isDemoPreview ? "Synthetic demo-only sample" : "Country field not inferred without source data"}</p></div><span className="panel-tag">REGIONS</span></div>
                  {isDemoPreview ? [
                    ["Region Alpha", 78, "high"], ["Region Bravo", 64, "high"], ["Region Charlie", 52, "medium"], ["Region Delta", 48, "medium"], ["Region Echo", 35, "low"]
                  ].map(([name, count, risk]) => <div className="country-line" key={String(name)}><span className="country-name">{name}</span><div className="country-track"><span className={`country-bar ${risk === "high" ? "bar-high" : risk === "medium" ? "bar-medium" : "bar-low"}`} style={{ width: `${Number(count) / 80 * 100}%` }} /></div><strong>{count}</strong><span className={`mini-risk ${String(risk)}`}>{risk}</span></div>) : <div className="panel-empty-note"><Network size={22} /><span>Import a country or channel field to enrich geographic analysis. No locations are invented for your dataset.</span></div>}
                  <button className="panel-link" onClick={() => setPage("sources")}>{isDemoPreview ? "Replace demo with my data" : "Review source mappings"} <ArrowRight size={13} /></button>
                </section>
              </div>

              <div className="command-grid command-grid-middle">
                <section className="command-panel recent-alerts-panel">
                  <div className="command-panel-heading"><div><h3>Recent risk signals</h3><p>{isDemoPreview ? "Synthetic rows for visual demonstration" : "Signals generated from the current analysis"}</p></div><button className="panel-link inline-link" onClick={() => setPage("alerts")}>View all <ArrowRight size={13} /></button></div>
                  <div className="recent-alert-list">
                    {dashboardAlerts.slice(0, 5).map((alert) => <button className="recent-alert-row" key={alert.alert_id} onClick={() => setSelectedAlert(alert)}>
                      <span className={`alert-symbol ${alert.severity}`}><ShieldAlert size={14} /></span>
                      <span className="recent-alert-copy"><strong>{alert.title}</strong><small>{alert.alert_id} · {ruleLabel(alert.rule_id)}</small></span>
                      <span className={`severity-pill ${severityClass(alert.severity)}`}><span />{alert.severity}</span>
                      <ArrowRight className="recent-row-arrow" size={14} />
                    </button>)}
                    {!dashboardAlerts.length && <div className="panel-empty-note"><ShieldCheck size={22} /><span>No alerts were generated in this analysis run.</span></div>}
                  </div>
                  {isDemoPreview && <div className="demo-footnote"><CircleHelp size={13} /> Demo alerts are fabricated and cannot be opened as persisted cases.</div>}
                </section>

                <section className="command-panel transaction-panel">
                  <div className="command-panel-heading"><div><h3>Transaction monitoring</h3><p>{result ? "Top signals from the current run" : "Illustrative synthetic activity feed"}</p></div><span className="feed-indicator"><i /> {result ? "Analysis result" : "Demo feed"}</span></div>
                  <div className="compact-table-wrap"><table className="compact-table"><thead><tr><th>Signal</th><th>Account ref.</th><th>Value</th><th>Risk</th></tr></thead><tbody>
                    {dashboardAlerts.slice(0, 5).map((alert) => <tr key={alert.alert_id} onClick={() => setSelectedAlert(alert)}><td><span className="mono-id">{alert.alert_id}</span><small>{ruleLabel(alert.rule_id)}</small></td><td>{alert.subject_reference || "Not available"}</td><td>{alert.measured_values.currency ? `${String(alert.measured_values.currency)} ${number(Number(alert.measured_values.amount))}` : (alert.measured_values.transaction_count ? `${number(Number(alert.measured_values.transaction_count))} events` : "Review")}</td><td><span className={`severity-pill ${severityClass(alert.severity)}`}><span />{alert.severity}</span></td></tr>)}
                    {!dashboardAlerts.length && <tr><td colSpan={4}>No transaction signals in this run.</td></tr>}
                  </tbody></table></div>
                  <button className="panel-link panel-link-bottom" onClick={() => setPage("alerts")}>Open signal explorer <ArrowRight size={13} /></button>
                </section>

                <section className="command-panel ai-panel">
                  <div className="command-panel-heading"><div><h3>AI risk intelligence</h3><p>Evidence-first investigation assistant</p></div><span className="ai-status"><Sparkles size={13} /> {result ? "Ready" : "Preview"}</span></div>
                  <div className="ai-insight-art"><div className="ai-orbit orbit-one" /><div className="ai-orbit orbit-two" /><div className="ai-core"><Sparkles size={23} /></div></div>
                  <div className="ai-insight-title">{result ? (dashboardAlerts[0]?.title || "No leading alert") : "Structuring-pattern review"}</div>
                  <p className="ai-insight-copy">{result ? (dashboardAlerts[0]?.explanation || "This run did not create any review signals.") : "Demo insight: a near-threshold pattern needs context. The real workflow uses your alert evidence and approved policy excerpts."}</p>
                  <div className="confidence-row"><span>Evidence linkage</span><strong>{result ? (dashboardAlerts[0] ? "Available" : "Not applicable") : "Illustrative"}</strong></div>
                  <div className="confidence-track"><span style={{ width: result && dashboardAlerts.length ? "82%" : "58%" }} /></div>
                  <button className="ai-action" onClick={() => { if (result && dashboardAlerts[0]) void openCaseFromAlert(dashboardAlerts[0]); else setPage("sources"); }} disabled={caseBusy}>{result && dashboardAlerts[0] ? "Open investigation case" : "Analyze my dataset"} <ArrowRight size={13} /></button>
                </section>
              </div>

              <div className="command-grid command-grid-bottom">
                <section className="command-panel bottom-chart-panel">
                  <div className="command-panel-heading"><div><h3>Customer risk distribution</h3><p>{isDemoPreview ? "Illustrative synthetic scoring" : "Risk scoring model not configured"}</p></div><Users size={16} className="muted-icon" /></div>
                  <div className="customer-risk-body"><div className="customer-ring"><div><strong>{number(metricAccounts)}</strong><span>Accounts</span></div></div><div className="customer-legend"><span><i className="legend-dot high-dot" />High risk <b>{isDemoPreview ? "312" : number(metricHighAlerts)}</b></span><span><i className="legend-dot medium-dot" />Medium <b>{isDemoPreview ? "1,024" : "—"}</b></span><span><i className="legend-dot low-dot" />Low <b>{isDemoPreview ? "1,095" : "—"}</b></span></div></div>
                </section>
                <section className="command-panel bottom-chart-panel">
                  <div className="command-panel-heading"><div><h3>Risk signal trend</h3><p>{isDemoPreview ? "Sample activity curve" : "Historical time series not stored in this run"}</p></div><Activity size={16} className="muted-icon" /></div>
                  <div className="trend-value"><strong>{number(metricAverageRisk)}</strong><span>Risk index</span></div><Sparkline values={[16, 22, 20, 18, 29, 26, 31, 27, 39, 34, 45, 49]} color="#2dd4bf" height={74} /><div className="axis-labels"><span>Earlier</span><span>Recent</span></div>
                </section>
                <section className="command-panel bottom-chart-panel">
                  <div className="command-panel-heading"><div><h3>Compliance knowledge</h3><p>Approved policy library status</p></div><BookOpenText size={16} className="muted-icon" /></div>
                  <div className="compliance-meter-list"><div><span>Policy documents indexed</span><strong>{number(policyDocs.length)}</strong></div><div className="meter-track"><span style={{ width: policyDocs.length ? "100%" : "4%" }} /></div><div><span>Policy retrieval</span><strong>{policyDocs.length ? "Available" : "Not configured"}</strong></div><div className="meter-track"><span style={{ width: policyDocs.length ? "76%" : "4%" }} /></div><div><span>Human approval</span><strong>Required</strong></div><div className="meter-track"><span style={{ width: "100%" }} /></div></div>
                  <button className="panel-link panel-link-bottom" onClick={() => setPage("policies")}>Open policy library <ArrowRight size={13} /></button>
                </section>
                <section className="command-panel bottom-chart-panel">
                  <div className="command-panel-heading"><div><h3>Watchlist screening</h3><p>{isDemoPreview ? "Illustrative sample only" : "External lists are not integrated"}</p></div><Fingerprint size={16} className="muted-icon" /></div>
                  <div className="watchlist-number">{isDemoPreview ? "24" : "—"}<span>{isDemoPreview ? "synthetic hits" : "not connected"}</span></div>
                  <div className="bar-chart">{[24, 40, 32, 46, 59, 36, 18].map((height, index) => <div className="bar-column" key={index}><span style={{ height: `${height}%` }} /><small>{["M", "T", "W", "T", "F", "S", "S"][index]}</small></div>)}</div>
                  <div className="panel-footnote">No external sanctions or PEP screening is performed in this MVP.</div>
                </section>
              </div>

              <div className="command-disclaimer"><ShieldCheck size={15} /><span>SentinelAML is an analyst-assistance prototype. Alerts are heuristic review indicators, not determinations of criminality. Demo metrics and map markers are synthetic and are never presented as bank telemetry.</span></div>
            </section>
          )}

          {page === "sources" && (
            <div className="sources-layout">
              <section className="panel source-workbench">
                <div className="panel-heading source-panel-heading">
                  <div><h3>Choose a data source</h3><p>Start with a one-time file upload or inspect an approved read-only SQL source.</p></div>
                  <span className="step-label">STEP 01</span>
                </div>
                <div className="segmented-tabs">
                  <button className={sourceMode === "file" ? "selected" : ""} onClick={() => { setSourceMode("file"); setPreview(null); setResult(null); }}><FileSpreadsheet size={16} /> File upload</button>
                  <button className={sourceMode === "sql" ? "selected" : ""} onClick={() => { setSourceMode("sql"); setPreview(null); setResult(null); }}><Database size={16} /> SQL database</button>
                </div>

                {sourceMode === "file" ? (
                  <div className="source-form-section">
                    <label className="section-label">TRANSACTION FILE</label>
                    <label className={`dropzone ${file ? "has-file" : ""}`} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); chooseFile(event.dataTransfer.files?.[0] || null); }}>
                      <input type="file" accept=".csv,.xlsx,.xls" onChange={(event) => chooseFile(event.target.files?.[0] || null)} />
                      <div className="drop-icon">{file ? <FileSpreadsheet size={23} /> : <UploadCloud size={23} />}</div>
                      <div className="drop-title">{file ? file.name : "Drop a file here, or browse"}</div>
                      <div className="drop-subtitle">{file ? `${(file.size / (1024 * 1024)).toFixed(2)} MB · selected locally` : "CSV or Excel workbook · Maximum file size 20 MB"}</div>
                      <span className="browse-link">{file ? "Choose a different file" : "Browse files"}</span>
                    </label>
                    {preview?.sheet_names && preview.sheet_names.length > 1 && (
                      <label className="form-field"><span>Workbook sheet</span><select value={sheetName || preview.sheet_names[0]} onChange={(event) => setSheetName(event.target.value)}>{preview.sheet_names.map((sheet) => <option key={sheet} value={sheet}>{sheet}</option>)}</select><small>Preview again after changing the selected sheet.</small></label>
                    )}
                    <div className="source-action-row">
                      <div className="helper-text"><LockKeyhole size={14} /> Uploaded data is not persisted by this prototype.</div>
                      <button className="btn btn-primary" disabled={!file || busy} onClick={previewFile}>{busy ? <RefreshCw className="spin" size={16} /> : <Search size={16} />} Preview columns</button>
                    </div>
                  </div>
                ) : (
                  <div className="source-form-section">
                    <div className="sql-safety-callout"><LockKeyhole size={17} /><div><strong>Read-only connection policy</strong><p>Use a dedicated read-only account. The API uses credentials only for each request and never stores them. Production hosts must be explicitly allowlisted on the server.</p></div></div>
                    <div className="form-grid">
                      <label className="form-field"><span>Database engine</span><select value={sql.engine} onChange={(event) => { updateSql("engine", event.target.value as SqlConnection["engine"]); setSqlConnected(false); setTables([]); }}><option value="postgresql">PostgreSQL</option><option value="mysql">MySQL / MariaDB</option><option value="sqlite">SQLite (local file)</option></select></label>
                      {sql.engine !== "sqlite" ? <>
                        <label className="form-field"><span>Host</span><input value={sql.host} onChange={(event) => updateSql("host", event.target.value)} placeholder="localhost or approved hostname" autoComplete="off" /></label>
                        <label className="form-field"><span>Port</span><input value={sql.port} onChange={(event) => updateSql("port", event.target.value)} placeholder={sql.engine === "postgresql" ? "5432" : "3306"} inputMode="numeric" /></label>
                        <label className="form-field"><span>Database name</span><input value={sql.database} onChange={(event) => updateSql("database", event.target.value)} autoComplete="off" /></label>
                        <label className="form-field"><span>Username</span><input value={sql.username} onChange={(event) => updateSql("username", event.target.value)} autoComplete="off" /></label>
                        <label className="form-field"><span>Password</span><input type="password" value={sql.password} onChange={(event) => updateSql("password", event.target.value)} autoComplete="new-password" /></label>
                      </> : <label className="form-field full-field"><span>Database filename (inside server's approved SQLite directory)</span><input value={sql.sqlite_path} onChange={(event) => updateSql("sqlite_path", event.target.value)} placeholder="sample.db" /><small>SQLite is restricted to files within SENTINELAML_SQLITE_ROOT on the API server.</small></label>}
                    </div>
                    <div className="source-action-row sql-action-row">
                      <button className="text-button" onClick={clearSqlCredentials}>Clear sensitive fields</button>
                      <button className="btn btn-primary" disabled={busy || (sql.engine !== "sqlite" && (!sql.host || !sql.database || !sql.username))} onClick={connectSql}>{busy ? <RefreshCw className="spin" size={16} /> : <Zap size={16} />} Test connection</button>
                    </div>
                    {sqlConnected && (
                      <div className="table-selector-block">
                        <div className="connected-label"><span /> Connected · {tables.length} tables available</div>
                        <label className="form-field"><span>Table</span><select value={selectedTable ? `${selectedSchema || ""}::${selectedTable}` : ""} onChange={(event) => { const chosen = tables.find((item) => `${item.schema || ""}::${item.name}` === event.target.value); setSelectedTable(chosen?.name || ""); setSelectedSchema(chosen?.schema || null); }}><option value="">Select a table</option>{tables.map((table) => <option key={`${table.schema || ""}::${table.name}`} value={`${table.schema || ""}::${table.name}`}>{table.schema ? `${table.schema}.` : ""}{table.name}</option>)}</select></label>
                        <div className="source-action-row"><span className="helper-text">Preview is capped at 500 rows.</span><button className="btn btn-secondary" disabled={!selectedTable || busy} onClick={previewSql}>{busy ? <RefreshCw className="spin" size={16} /> : <Search size={16} />} Preview table</button></div>
                      </div>
                    )}
                  </div>
                )}
              </section>

              <aside className="right-rail">
                <section className="panel">
                  <div className="side-section-title"><div className="rail-icon"><ShieldCheck size={17} /></div><div><h3>Before you import</h3><p>Safe handling checklist</p></div></div>
                  <ul className="check-list">
                    <li><Check size={15} /> Use synthetic or authorized data</li>
                    <li><Check size={15} /> Preserve account IDs as text</li>
                    <li><Check size={15} /> Keep currencies identifiable</li>
                    <li><Check size={15} /> Use a read-only SQL account</li>
                  </ul>
                </section>
                <section className="panel required-fields-panel">
                  <div className="side-section-title"><div className="rail-icon violet-rail"><SlidersHorizontal size={17} /></div><div><h3>Required fields</h3><p>Map these before analysis</p></div></div>
                  {FIELDS.filter((field) => field.required).map((field) => <div className="required-field-row" key={field.key}><span>{field.label}</span>{preview && mapping[field.key] ? <span className="field-mapped"><Check size={13} /> mapped</span> : <span className="field-pending">Required</span>}</div>)}
                  <div className="rule-options-toggle"><strong>Rule thresholds</strong><span>Demo defaults</span></div>
                  <label className="mini-option"><span>High-value threshold</span><input type="number" min="1" value={options.large_amount_threshold} onChange={(event) => setOptions({ ...options, large_amount_threshold: Number(event.target.value) || 1 })} /></label>
                  <label className="mini-option"><span>Velocity count</span><input type="number" min="1" value={options.velocity_count_threshold} onChange={(event) => setOptions({ ...options, velocity_count_threshold: Number(event.target.value) || 1 })} /></label>
                  <div className="threshold-note">Illustrative heuristics only — not regulatory thresholds.</div>
                </section>
              </aside>

              {preview && (
                <section className="panel preview-panel">
                  <div className="panel-heading preview-heading"><div><div className="step-overline">STEP 02 · REVIEW SOURCE SCHEMA</div><h3>Preview & map columns</h3><p>{preview.filename || (preview.table ? `Table: ${preview.schema ? preview.schema + "." : ""}${preview.table}` : "Source schema detected")} · {number(preview.row_count)} rows available for this analysis</p></div><span className="source-format-badge">{preview.format || preview.engine || "SOURCE"}</span></div>
                  {preview.warnings.map((warning, index) => <div className="warning-line" key={index}><CircleHelp size={15} />{warning}</div>)}
                  <MappingEditor preview={preview} mapping={mapping} onChange={setMappingField} />
                  <div className="data-preview-block">
                    <div className="data-preview-heading"><div><h4>Sample records</h4><span>First {preview.preview_rows.length} rows · display only</span></div><span>{preview.columns.length} columns</span></div>
                    <div className="table-wrap preview-table-wrap"><table className="data-table preview-table"><thead><tr>{preview.columns.map((column) => <th key={column.name}>{column.name}<small>{column.inferred_type}</small></th>)}</tr></thead><tbody>{preview.preview_rows.map((row, index) => <tr key={index}>{preview.columns.map((column) => <td key={column.name} title={row[column.name] || ""}>{row[column.name] ?? "—"}</td>)}</tr>)}</tbody></table></div>
                  </div>
                  <div className="analysis-bottom-row">
                    <div className={`mapping-status ${requiredMapped ? "mapping-complete" : ""}`}>{requiredMapped ? <Check size={15} /> : <CircleHelp size={15} />}{requiredMapped ? "Required fields mapped" : "Map all 3 required fields to continue"}</div>
                    <button className="btn btn-primary btn-large" disabled={busy || !requiredMapped} onClick={sourceMode === "file" ? analyzeFile : analyzeSql}>{busy ? <RefreshCw className="spin" size={16} /> : <Sparkles size={16} />} Analyze transactions <ArrowRight size={16} /></button>
                  </div>
                </section>
              )}
            </div>
          )}

          {page === "alerts" && (
            <section className="panel full-panel">
              <div className="panel-heading"><div><h3>Alert explorer</h3><p>Every signal points to measured evidence from the current analysis.</p></div><div className="alert-toolbar"><span className="results-count">{visibleAlerts.length} signals</span>{result && <button className="btn btn-secondary" onClick={exportAlerts}><ArrowDownToLine size={15} /> Export CSV</button>}</div></div>
              {result ? <AlertsTable alerts={visibleAlerts} onInspect={setSelectedAlert} /> : <EmptyPanel title="No analysis loaded" description="Import a file or connect a database to generate review signals." onAction={() => setPage("sources")} />}
            </section>
          )}

          {page === "quality" && (
            <section className="panel full-panel">
              <div className="panel-heading"><div><h3>Data quality findings</h3><p>Quality issues that can affect interpretation and rule coverage.</p></div><span className="results-count">{result?.data_quality.length || 0} findings</span></div>
              {result?.data_quality.length ? <div className="quality-list">{result.data_quality.map((finding) => <div className="quality-item" key={finding.finding_key}><div className={`quality-icon ${severityClass(finding.severity)}`}><Activity size={18} /></div><div className="quality-main"><strong>{ruleLabel(finding.finding_key)}</strong><p>{finding.message}</p><div className="quality-row-refs">Rows affected: <b>{number(finding.affected_rows)}</b>{finding.example_row_numbers.length > 0 && <span> · Examples: {finding.example_row_numbers.join(", ")}</span>}</div></div><span className={`severity-pill ${severityClass(finding.severity)}`}><span />{finding.severity}</span></div>)}</div> : <EmptyPanel title="No quality findings loaded" description="Analyze a dataset to inspect missing fields, invalid values, and source inconsistencies." onAction={() => setPage("sources")} />}
            </section>
          )}

          {page === "investigations" && (
            <div className="investigation-layout">
              <section className="panel full-panel">
                <div className="panel-heading"><div><h3>Investigation workspace</h3><p>Prepare review-ready cases from evidence. Case persistence and AI orchestration are planned next.</p></div><span className="future-badge"><Sparkles size={13} /> Next milestone</span></div>
                <div className="investigation-hero"><div className="investigation-art"><Network size={36} strokeWidth={1.35} /><span /><i /><b /></div><div><h2>From rule signal to evidence-backed case</h2><p>Next we will add transaction timelines, linked-account exploration, sourced investigation summaries, analyst notes, and supervisor approval. Consequential actions will remain human-controlled.</p><button className="btn btn-secondary" onClick={() => setPage("alerts")}>Review current alerts <ArrowRight size={15} /></button></div></div>
                {result ? <div className="panel-heading recent-case-heading"><div><h3>Potential cases from current run</h3><p>These are alerts only — no case has been opened automatically.</p></div></div> : null}
                {result ? <AlertsTable alerts={visibleAlerts.slice(0, 10)} onInspect={setSelectedAlert} /> : null}
              </section>
            </div>
          )}

          <footer className="page-footer">
            <span>© 2026 SentinelAML <span className="footer-divider">·</span> Early-stage prototype</span>
            <span><ShieldCheck size={14} /> Explainable signals. Human-led decisions.</span>
          </footer>
        </div>
      </main>

      {selectedAlert && <AlertDrawer alert={selectedAlert} onClose={() => setSelectedAlert(null)} />}
    </div>
  );
}

function StatCard({ icon, label, value, note, tone }: { icon: ReactNode; label: string; value: string; note: string; tone: string }) {
  return <section className="stat-card"><div className="stat-top"><div className={`stat-icon ${tone}`}>{icon}</div><span className="stat-period">Current run</span></div><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-note">{note}</div></section>;
}

function WorkflowStep({ number: stepNumber, title, description, status }: { number: string; title: string; description: string; status?: string }) {
  return <div className={`workflow-step ${status === "current" ? "workflow-step-current" : ""}`}><div className="workflow-number">{stepNumber}</div><div className="workflow-text"><strong>{title}</strong><span>{description}</span></div>{status === "current" && <span className="current-step-dot" />}</div>;
}

function EmptyPanel({ title, description, onAction }: { title: string; description: string; onAction: () => void }) {
  return <div className="empty-state"><div className="empty-icon"><FileUp size={25} /></div><h3>{title}</h3><p>{description}</p><button className="btn btn-primary" onClick={onAction}><UploadCloud size={16} /> Go to data sources</button></div>;
}

function AlertDrawer({ alert, onClose }: { alert: AlertItem; onClose: () => void }) {
  return (
    <div className="drawer-scrim" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className="alert-drawer" aria-label="Alert details">
        <div className="drawer-header"><div><div className="eyebrow">SIGNAL DETAIL</div><h2>{alert.title}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close alert detail"><X size={19} /></button></div>
        <div className="drawer-status-row"><span className={`severity-pill ${severityClass(alert.severity)}`}><span />{alert.severity} priority</span><span className="rule-tag">{ruleLabel(alert.rule_id)}</span></div>
        <div className="drawer-section"><label>WHY THIS WAS FLAGGED</label><p>{alert.explanation}</p></div>
        <div className="drawer-section"><label>SUBJECT ACCOUNT</label><div className="drawer-metric mono">{alert.subject_reference || "Not available"}</div></div>
        <div className="drawer-section"><label>EVIDENCE ROW REFERENCES</label><div className="evidence-chips">{alert.evidence_row_numbers.map((row) => <span key={row}>Row {row}</span>)}{alert.evidence_count > alert.evidence_row_numbers.length && <span>+{alert.evidence_count - alert.evidence_row_numbers.length} more</span>}</div><p className="muted-paragraph">Row numbers refer to the imported source's data rows. For SQL sources, use a stable source key where available.</p></div>
        <div className="drawer-section"><label>MEASURED VALUES</label><div className="measured-values">{Object.entries(alert.measured_values).map(([key, value]) => <div key={key}><span>{ruleLabel(key)}</span><strong>{typeof value === "object" ? JSON.stringify(value) : String(value)}</strong></div>)}</div></div>
        <div className="drawer-disclaimer"><ShieldCheck size={17} /><p>{alert.interpretation}</p></div>
        <button className="btn btn-secondary drawer-close-btn" onClick={onClose}>Close review panel</button>
      </aside>
    </div>
  );
}

export default App;
