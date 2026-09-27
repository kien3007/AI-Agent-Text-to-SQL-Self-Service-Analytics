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

export interface DataContract {
  owner: string;
  data_steward: string;
  slack_channel: string;
  SLA: {
    freshness: string;
  };
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
  lineage?: IngestionLineage;
}

export interface BenchmarkItem {
  id: string;
  query: string;
  complexity: string;
  passed: boolean;
  latency: string;
}
