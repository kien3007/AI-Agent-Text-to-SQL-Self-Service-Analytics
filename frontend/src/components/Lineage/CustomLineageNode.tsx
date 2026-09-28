"use client";

import React, { memo } from "react";
import { Handle, Position, NodeProps } from "@xyflow/react";
import {
  Database,
  Layers,
  Server,
  TrendingUp,
  Bot,
  LayoutDashboard,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  HardDrive
} from "lucide-react";
import { LineageGraphNode } from "@/types/chat";

export interface CustomNodeData {
  node: LineageGraphNode;
  isSelected?: boolean;
}

const LAYER_CONFIGS: Record<
  string,
  {
    icon: React.ComponentType<{ className?: string }>;
    accentColor: string;
    badgeBg: string;
    borderActive: string;
    title: string;
  }
> = {
  source: {
    icon: Database,
    accentColor: "text-amber-500",
    badgeBg: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
    borderActive: "border-amber-500 ring-2 ring-amber-500/20",
    title: "Raw Ingestion",
  },
  staging: {
    icon: Layers,
    accentColor: "text-sky-500",
    badgeBg: "bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20",
    borderActive: "border-sky-500 ring-2 ring-sky-500/20",
    title: "dbt Staging",
  },
  warehouse: {
    icon: HardDrive,
    accentColor: "text-purple-500",
    badgeBg: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20",
    borderActive: "border-purple-500 ring-2 ring-purple-500/20",
    title: "Doris Warehouse",
  },
  metric: {
    icon: TrendingUp,
    accentColor: "text-emerald-500",
    badgeBg: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
    borderActive: "border-emerald-500 ring-2 ring-emerald-500/20",
    title: "Semantic Metric",
  },
  consumer: {
    icon: Bot,
    accentColor: "text-rose-500",
    badgeBg: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20",
    borderActive: "border-rose-500 ring-2 ring-rose-500/20",
    title: "Downstream Consumer",
  },
};

function CustomLineageNodeComponent({ data, selected }: NodeProps) {
  const nodeData = (data as unknown as CustomNodeData)?.node;
  if (!nodeData) return null;

  const layer = nodeData.layer || "warehouse";
  const cfg = LAYER_CONFIGS[layer] || LAYER_CONFIGS.warehouse;
  const Icon = cfg.icon;

  const rowCount = nodeData.details?.row_count;
  const columnsCount = nodeData.details?.columns?.length || nodeData.details?.columns_count;

  return (
    <div
      className={`relative min-w-[210px] max-w-[260px] rounded-2xl bg-[var(--bg-card)] border transition-all duration-200 shadow-sm hover:shadow-md cursor-pointer select-none p-3.5 ${
        selected ? cfg.borderActive : "border-[var(--border-subtle)] hover:border-[var(--border-medium)]"
      }`}
    >
      {/* Input Handle (Left) */}
      <Handle
        type="target"
        position={Position.Left}
        className="!w-2.5 !h-2.5 !bg-[var(--border-medium)] hover:!bg-purple-500 !border-2 !border-[var(--bg-card)] transition-colors"
      />

      {/* Header bar */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <span
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${cfg.badgeBg}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
          {cfg.title}
        </span>
        <span className="text-[10px] text-[var(--text-muted)] font-mono uppercase tracking-wider">
          {nodeData.type}
        </span>
      </div>

      {/* Main Node Content */}
      <div className="flex items-start gap-2.5">
        <div
          className={`w-8 h-8 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] flex items-center justify-center flex-shrink-0 ${cfg.accentColor}`}
        >
          <Icon className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xs font-bold text-[var(--text-primary)] truncate" title={nodeData.label}>
            {nodeData.label}
          </div>
          {nodeData.vn_label && nodeData.vn_label !== nodeData.label && (
            <div className="text-[11px] text-[var(--text-secondary)] truncate">
              {nodeData.vn_label}
            </div>
          )}
        </div>
      </div>

      {/* Node stats / meta info */}
      <div className="mt-3 pt-2 border-t border-[var(--border-subtle)] flex items-center justify-between text-[10px] text-[var(--text-muted)]">
        {rowCount !== undefined ? (
          <span className="font-mono font-medium text-[var(--text-primary)]">
            {rowCount.toLocaleString("vi-VN")} rows
          </span>
        ) : columnsCount !== undefined ? (
          <span className="font-mono">{columnsCount} cột</span>
        ) : (
          <span className="capitalize">{nodeData.status || "Active"}</span>
        )}

        <span className="text-emerald-500 font-medium flex items-center gap-0.5">
          <CheckCircle2 className="w-3 h-3" />
          SLA OK
        </span>
      </div>

      {/* Output Handle (Right) */}
      <Handle
        type="source"
        position={Position.Right}
        className="!w-2.5 !h-2.5 !bg-[var(--border-medium)] hover:!bg-purple-500 !border-2 !border-[var(--bg-card)] transition-colors"
      />
    </div>
  );
}

export default memo(CustomLineageNodeComponent);
