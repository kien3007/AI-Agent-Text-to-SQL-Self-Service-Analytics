"use client";

import React from "react";
import {
  X,
  Database,
  Key,
  ShieldAlert,
  ArrowRight,
  TrendingUp,
  Clock,
  User,
  Zap,
  CheckCircle2,
  AlertTriangle
} from "lucide-react";
import { LineageGraphNode } from "@/types/chat";

interface NodeInspectorDrawerProps {
  node: LineageGraphNode | null;
  onClose: () => void;
  onSimulateImpact: (tableName: string) => void;
}

export default function NodeInspectorDrawer({
  node,
  onClose,
  onSimulateImpact,
}: NodeInspectorDrawerProps) {
  if (!node) return null;

  const details = node.details || {};
  const columns = details.columns || [];
  const isTable = node.layer === "warehouse";
  const isMetric = node.layer === "metric";

  return (
    <div className="absolute right-4 top-4 bottom-4 w-96 max-w-[calc(100%-2rem)] rounded-2xl bg-[var(--bg-card)] border border-[var(--border-medium)] shadow-xl z-20 flex flex-col overflow-hidden animate-in slide-in-from-right-4 duration-300">
      {/* Drawer Header */}
      <div className="p-4 border-b border-[var(--border-subtle)] flex items-start justify-between gap-3 bg-[var(--bg-app)]/50">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-[var(--pill-bg)] text-[var(--text-secondary)] border border-[var(--border-subtle)]">
              {node.layer}
            </span>
            <span className="text-xs font-mono text-emerald-500 flex items-center gap-1 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" />
              {node.status}
            </span>
          </div>
          <h2 className="text-base font-bold text-[var(--text-primary)] mt-1.5 break-words">
            {node.label}
          </h2>
          {node.vn_label && node.vn_label !== node.label && (
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">{node.vn_label}</p>
          )}
        </div>

        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--border-subtle)] transition-colors"
          title="Đóng inspector"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Drawer Body */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4 text-xs">
        {/* Description */}
        {details.description && (
          <div className="p-3 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] text-[var(--text-secondary)] leading-relaxed">
            {details.description}
          </div>
        )}

        {/* Quick Impact Action for Tables */}
        {isTable && (details.table_name || node.label) && (
          <button
            onClick={() => onSimulateImpact((details.table_name || node.label)!)}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-semibold text-xs transition-colors shadow-xs"
          >
            <Zap className="w-3.5 h-3.5" />
            <span>Phân Tích Tác Động Bảng Này</span>
            <ArrowRight className="w-3.5 h-3.5 ml-auto" />
          </button>
        )}

        {/* Metrics Formula if Metric */}
        {isMetric && details.sql_expression && (
          <div className="flex flex-col gap-1.5">
            <span className="font-semibold text-[var(--text-secondary)] uppercase tracking-wider text-[10px]">
              Công thức SQL Semantic
            </span>
            <div className="p-2.5 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] font-mono text-[11px] text-[var(--accent-primary)] break-all">
              {details.sql_expression}
            </div>
          </div>
        )}

        {/* Governance & Metadata Stats */}
        <div className="grid grid-cols-2 gap-2 text-[11px]">
          <div className="p-2.5 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] flex flex-col gap-1">
            <span className="text-[var(--text-muted)] flex items-center gap-1">
              <User className="w-3 h-3" /> Owner
            </span>
            <span className="font-semibold text-[var(--text-primary)] truncate">
              {details.owner || "Data Team"}
            </span>
          </div>

          <div className="p-2.5 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] flex flex-col gap-1">
            <span className="text-[var(--text-muted)] flex items-center gap-1">
              <Clock className="w-3 h-3" /> Freshness
            </span>
            <span className="font-semibold text-[var(--text-primary)] truncate">
              {details.freshness || "Real-time"}
            </span>
          </div>
        </div>

        {/* Columns Schema List for Tables */}
        {columns.length > 0 && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-[var(--text-secondary)] uppercase tracking-wider text-[10px]">
                Cấu Trúc Cột ({columns.length})
              </span>
              {columns.some((c) => c.is_pii) && (
                <span className="px-1.5 py-0.5 rounded text-[10px] bg-rose-500/10 text-rose-600 dark:text-rose-400 font-semibold flex items-center gap-1">
                  <ShieldAlert className="w-3 h-3" />
                  Chứa PII
                </span>
              )}
            </div>

            <div className="flex flex-col gap-1.5 max-h-60 overflow-y-auto pr-1">
              {columns.map((col, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2 rounded-lg bg-[var(--bg-app)] border border-[var(--border-subtle)]"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    {col.is_pk ? (
                      <Key className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
                    ) : (
                      <div className="w-1.5 h-1.5 rounded-full bg-[var(--border-medium)] flex-shrink-0" />
                    )}
                    <span className="font-mono text-xs font-semibold text-[var(--text-primary)] truncate">
                      {col.name}
                    </span>
                    {col.is_pii && (
                      <span className="px-1 py-0.2 rounded text-[9px] bg-rose-500/20 text-rose-500 font-semibold uppercase">
                        PII
                      </span>
                    )}
                  </div>
                  <span className="text-[10px] font-mono text-[var(--text-muted)] flex-shrink-0">
                    {col.type || "VARCHAR"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
