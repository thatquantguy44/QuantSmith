// View-model types — mirror src/quantsmith/knowledge_console/model.py::build_model.

export interface RecordView {
  id: string;
  scope: string;
  type: string;
  statement: string;
  confidence: "low" | "medium" | "high" | string;
  corroboration_count: number;
  corroboration_derived: number;
  first_seen: string;
  last_confirmed: string;
  status: "active" | "stale" | "superseded" | "retired" | string;
  pit_scope: string;
  access_level: string;
  author: string | null;
  workflow: string;
  source_file: string;
  days_since_confirmed: number;
  overdue: boolean;
  evidence_runs: string[];
}

export interface Counts {
  total: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  by_confidence: Record<string, number>;
  by_access_level: Record<string, number>;
  by_workflow: Record<string, number>;
}

export interface Trends {
  cumulative_by_date: { date: string; count: number }[];
  confirmations_by_month: { month: string; count: number }[];
  staleness: { fresh: number; overdue: number };
}

export interface GraphNode {
  id: string;
  label: string;
  kind: "record" | "workflow" | "scope" | "run" | string;
  meta: Record<string, string | number>;
}

export interface GraphEdge {
  source: string;
  target: string;
  kind: string;
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface Change {
  hash: string;
  author: string;
  date: string;
  subject: string;
  files: string[];
}

export interface ReviewReason {
  kind: string;
  severity: "error" | "warn" | "info" | string;
  detail: string;
}

export interface ReviewItem {
  record_id: string;
  severity: "error" | "warn" | "info" | string;
  reasons: ReviewReason[];
  scope: string;
  type: string;
  workflow: string;
  last_confirmed: string;
  access_level: string;
}

export interface Finding {
  record_id: string;
  severity: string;
  message: string;
  file: string;
}

export interface Model {
  generated_at: string | null;
  as_of: string;
  freshness_days: number;
  counts: Counts;
  records: RecordView[];
  trends: Trends;
  graph: Graph;
  changes: Change[];
  review_queue: ReviewItem[];
  findings: Finding[];
}

export interface QueryAnswer {
  answer: string;
  citations: string[];
  mode: string;
  matched: boolean;
}

declare global {
  interface Window {
    __KB_MODEL__?: Model;
  }
}
