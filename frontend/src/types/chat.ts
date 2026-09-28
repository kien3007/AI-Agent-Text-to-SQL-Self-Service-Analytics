export interface ChartConfig {
  type?: 'bar' | 'pie' | 'line' | 'doughnut';
  title?: string;
  x_axis?: string;
  y_axis?: string;
}

export interface ChatMetadata {
  tables_linked?: string[];
  columns_linked?: string[];
  complexity?: string;
  fan_trap_detected?: boolean;
}

export interface ChatResponse {
  session_id: string;
  domain_id?: string;
  user_query: string;
  complexity_level?: string;
  clarification_needed?: boolean;
  clarification_question?: string;
  requires_hitl?: boolean;
  hitl_approved?: boolean;
  sql_query?: string;
  final_response?: string;
  chart_config?: ChartConfig;
  column_names?: string[];
  query_result?: any[];
  execution_time_ms?: number;
  steps_executed?: string[];
  metadata?: ChatMetadata;
}

export interface ThoughtStep {
  step: string;
  session_id?: string;
  domain_id?: string;
  complexity_level?: string;
  sql_query?: string;
  timestamp?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  data?: ChatResponse;
  thoughtSteps?: ThoughtStep[];
  isStreaming?: boolean;
  durationSec?: string;
}

export interface ChatSession {
  id: string;
  title: string;
  domainId: string;
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
}

export interface DomainItem {
  domain_id: string;
  display_name: string;
  description?: string;
  tables_count?: number;
  metrics_count?: number;
  is_active?: boolean;
}

export interface MetricItem {
  metric_id?: string;
  name?: string;
  label?: string;
  description?: string;
  sql_expression?: string;
  vn_terms?: string[];
}

export interface ColumnItem {
  name: string;
  vn_name?: string;
  data_type?: string;
  description?: string;
  is_pk?: boolean;
  is_fk?: boolean;
}

export interface TableItem {
  name?: string;
  table_name?: string;
  vn_name?: string;
  description?: string;
  columns_count?: number;
  columns?: ColumnItem[];
}

export interface DomainDetails {
  domain_id: string;
  display_name?: string;
  domain_name?: string;
  description: string;
  metrics: MetricItem[];
  tables: TableItem[];
}

export interface PIIField {
  table: string;
  column: string;
  vn_name?: string;
  classification: string;
  masking_policy: string;
}

export interface DataContract {
  domain_id?: string;
  display_name?: string;
  owner: string;
  data_steward: string;
  slack_channel: string;
  tables_guaranteed?: string[];
  metrics_guaranteed?: string[];
  pii_governance?: {
    total_pii_fields: number;
    columns: PIIField[];
    encryption: string;
    gdpr_compliance: boolean;
  };
  SLA: {
    freshness: string;
    availability?: string;
    query_latency_p95?: string;
    incident_response_time?: string;
  };
}

export interface LineageGraphNode {
  id: string;
  label: string;
  vn_label?: string;
  layer: "source" | "staging" | "warehouse" | "metric" | "consumer";
  type: string;
  status: string;
  details?: {
    materialization?: string;
    description?: string;
    columns_count?: number;
    table_name?: string;
    vn_name?: string;
    row_count?: number;
    freshness?: string;
    sla?: string;
    owner?: string;
    steward?: string;
    columns?: Array<{
      name: string;
      vn_name?: string;
      type?: string;
      is_pk?: boolean;
      is_fk?: boolean;
      is_pii?: boolean;
    }>;
    metric_id?: string;
    sql_expression?: string;
    vn_terms?: string[];
    consumer_type?: string;
    active_users?: string;
    query_volume?: string;
    criticality?: string;
    [key: string]: any;
  };
}

export interface LineageGraphEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  animated?: boolean;
  type?: string;
  style?: Record<string, any>;
}

export interface LineageGraphData {
  domain_id: string;
  total_nodes: number;
  total_edges: number;
  layers: string[];
  nodes: LineageGraphNode[];
  edges: LineageGraphEdge[];
}

export interface IngestionLineage {
  source: string;
  destination: string;
  total_records: number;
  ingestion_time: string;
  status: string;
}

export interface LineageResponse {
  type: string;
  domain_id: string;
  lineage?: LineageGraphData | IngestionLineage;
}

export interface ImpactAnalysisResult {
  domain_id: string;
  target: {
    table_name: string;
    column_name?: string | null;
    vn_table_name?: string;
  };
  risk_assessment: {
    risk_level: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
    risk_color: string;
    blast_radius_score: number;
    total_impacted_entities: number;
    is_breaking_change: boolean;
  };
  impact_breakdown: {
    tables: Array<{ id: string; name: string; vn_name?: string; row_count: number }>;
    metrics: Array<{ id: string; name: string; sql_expression?: string; is_direct_break?: boolean }>;
    consumers: Array<{ id: string; name: string; type?: string }>;
  };
  direct_breaking_metrics: Array<{
    metric_id: string;
    label: string;
    reason: string;
  }>;
  recommendations: string[];
}

export interface DQTestItem {
  test_id: string;
  table: string;
  rule: string;
  rule_type: string;
  description: string;
  threshold: string;
  actual: string;
  status: "PASS" | "WARN" | "FAIL";
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  executed_at: string;
}

export interface DQTableSummary {
  table_name: string;
  vn_name: string;
  total_checks: number;
  passed: number;
  warnings: number;
  failed: number;
  health_score: number;
  estimated_rows: number;
}

export interface QualityReport {
  domain_id: string;
  overall_score: number;
  sla_compliance_rate: string;
  sla_status: string;
  last_run: string;
  summary: {
    total: number;
    passed: number;
    warnings: number;
    failed: number;
  };
  table_summaries: DQTableSummary[];
  tests: DQTestItem[];
  history: Array<{
    date: string;
    score: number;
    passed_checks: number;
    warnings: number;
  }>;
}

export interface BenchmarkItem {
  id: string;
  query: string;
  complexity: string;
  passed: boolean;
  latency: string;
}
