"use client";

import React, { useEffect, useState } from "react";
import {
  BookOpen,
  Database,
  BarChart3,
  Columns,
  Loader2,
  Sparkles,
  Search,
  ArrowRight,
  Table as TableIcon,
} from "lucide-react";
import { DomainDetails } from "@/types/chat";

interface CatalogViewProps {
  domainId: string;
  onSelectMetric: (metricName: string) => void;
  onSwitchToChat: () => void;
}

export default function CatalogView({
  domainId,
  onSelectMetric,
}: CatalogViewProps) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<DomainDetails | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedTable, setSelectedTable] = useState<string | null>(null);

  useEffect(() => {
    if (!domainId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    fetch(`/api/domains/${domainId}`)
      .then((res) => {
        if (!res.ok) throw new Error("Không thể tải dữ liệu Data Catalog.");
        return res.json();
      })
      .then((json) => {
        if (isMounted) {
          setData(json);
          if (json.tables && json.tables.length > 0) {
            const firstTableName = json.tables[0].table_name || json.tables[0].name || "";
            setSelectedTable(firstTableName);
          }
        }
      })
      .catch((err) => {
        if (isMounted) setError(err.message);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [domainId]);

  const filteredMetrics = data?.metrics?.filter((m) => {
    const title = m.label || m.name || m.metric_id || "";
    const desc = m.description || "";
    const sql = m.sql_expression || "";
    return searchTerm
      ? title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        desc.toLowerCase().includes(searchTerm.toLowerCase()) ||
        sql.toLowerCase().includes(searchTerm.toLowerCase())
      : true;
  });

  const filteredTables = data?.tables?.filter((t) => {
    const tName = t.table_name || t.name || "";
    const vnName = t.vn_name || "";
    return searchTerm
      ? tName.toLowerCase().includes(searchTerm.toLowerCase()) ||
        vnName.toLowerCase().includes(searchTerm.toLowerCase()) ||
        t.columns?.some((c) => c.name.toLowerCase().includes(searchTerm.toLowerCase()))
      : true;
  });

  const currentTableObj =
    data?.tables?.find((t) => (t.table_name || t.name) === selectedTable) ||
    data?.tables?.[0];

  const currentTableName = currentTableObj?.table_name || currentTableObj?.name || "Bảng dữ liệu";

  return (
    <div className="flex-1 h-full overflow-y-auto p-6 md:p-8 flex flex-col gap-6 animate-in fade-in slide-in-from-bottom-2 duration-300 select-text">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] flex items-center justify-center flex-shrink-0">
            <BookOpen className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-bold text-[var(--text-primary)]">
                Enterprise Data Catalog
              </h1>
              <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-[var(--pill-bg)] text-[var(--accent-primary)] border border-[var(--border-subtle)] font-mono">
                {domainId}
              </span>
            </div>
            <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-2xl leading-relaxed">
              {data?.description ||
                "Semantic Layer, Business Metrics & Cấu trúc Schema cơ sở dữ liệu phân tích Data Warehouse."}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative min-w-[220px]">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Tìm bảng, cột hoặc chỉ số..."
              className="w-full pl-9 pr-3 py-1.5 rounded-xl text-xs bg-[var(--bg-app)] border border-[var(--border-subtle)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent-primary)] transition-all"
            />
          </div>
        </div>
      </div>

      {loading && (
        <div className="flex flex-col items-center justify-center py-24 text-[var(--text-muted)] gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-[var(--accent-primary)]" />
          <p className="text-xs font-medium">Đang tải cấu trúc dữ liệu catalog...</p>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs">
          {error}
        </div>
      )}

      {!loading && data && (
        <>
          {/* Section 1: Business Metrics (Semantic Layer) */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-[var(--accent-primary)]" />
                <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                  Chỉ số Nghiệp vụ (Semantic Metrics)
                </h2>
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-[var(--pill-bg)] text-[var(--text-muted)] font-mono">
                  {filteredMetrics?.length || 0}
                </span>
              </div>
              <span className="text-[11px] text-[var(--text-muted)]">
                Nhấp vào bất kỳ chỉ số nào để phân tích ngay trong chat
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {filteredMetrics?.map((m, idx) => {
                const metricTitle = m.label || m.name || m.metric_id || `Chỉ số ${idx + 1}`;
                const metricKey = m.metric_id || `metric_${idx}`;
                return (
                  <div
                    key={metricKey}
                    onClick={() => onSelectMetric(metricTitle)}
                    className="group relative p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] hover:border-[var(--accent-primary)] hover:bg-[var(--bg-card-hover)] cursor-pointer transition-all duration-200 flex flex-col justify-between shadow-xs"
                  >
                    <div>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-semibold text-[var(--text-primary)] group-hover:text-[var(--accent-primary)] transition-colors">
                          {metricTitle}
                        </span>
                        <Sparkles className="w-3.5 h-3.5 text-[var(--text-muted)] group-hover:text-[var(--accent-primary)] transition-colors" />
                      </div>
                      <p className="text-[11px] text-[var(--text-secondary)] line-clamp-2 leading-relaxed">
                        {m.description || m.sql_expression}
                      </p>
                    </div>

                    {m.sql_expression && (
                      <div className="mt-3 pt-2.5 border-t border-[var(--border-subtle)] flex items-center justify-between">
                        <code className="text-[10px] font-mono text-[var(--text-muted)] truncate max-w-[200px]">
                          {m.sql_expression}
                        </code>
                        <span className="text-[10px] font-medium text-[var(--accent-primary)] inline-flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
                          Phân tích <ArrowRight className="w-3 h-3" />
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Section 2: Tables & Schema Explorer */}
          <div className="flex flex-col gap-3 mt-2">
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-emerald-500" />
              <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                Cấu trúc Bảng & Cột Data Warehouse
              </h2>
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-[var(--pill-bg)] text-[var(--text-muted)] font-mono">
                {filteredTables?.length || 0} bảng
              </span>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
              {/* Tables list sidebar */}
              <div className="lg:col-span-1 flex flex-col gap-1.5 p-2 rounded-xl bg-[var(--bg-card)] border border-[var(--border-subtle)]">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] px-2.5 py-1">
                  Danh sách Bảng
                </span>
                {filteredTables?.map((t, idx) => {
                  const tName = t.table_name || t.name || `table_${idx}`;
                  const isSelected = (currentTableObj?.table_name || currentTableObj?.name) === tName;
                  return (
                    <button
                      key={tName}
                      onClick={() => setSelectedTable(tName)}
                      className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs font-mono transition-all text-left ${
                        isSelected
                          ? "bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] font-semibold border border-[var(--accent-primary)]/20"
                          : "text-[var(--text-secondary)] hover:bg-[var(--bg-sidebar-hover)] hover:text-[var(--text-primary)] border border-transparent"
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <TableIcon className="w-3.5 h-3.5 flex-shrink-0" />
                        <span className="truncate">{t.vn_name || tName}</span>
                      </div>
                      <span className="text-[10px] text-[var(--text-muted)] font-sans ml-1">
                        {t.columns?.length || t.columns_count || 0}
                      </span>
                    </button>
                  );
                })}
              </div>

              {/* Table Columns Detail */}
              <div className="lg:col-span-3 rounded-xl bg-[var(--bg-card)] border border-[var(--border-subtle)] overflow-hidden flex flex-col">
                <div className="p-4 border-b border-[var(--border-subtle)] flex items-center justify-between bg-[var(--bg-app)]/50">
                  <div className="flex items-center gap-2.5 font-mono text-xs font-semibold text-[var(--text-primary)]">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-xs" />
                    <span>{currentTableName}</span>
                    {currentTableObj?.vn_name && (
                      <span className="font-sans text-[11px] text-[var(--text-muted)] font-normal">
                        — {currentTableObj.vn_name}
                      </span>
                    )}
                  </div>
                  <span className="text-[11px] text-[var(--text-muted)]">
                    {currentTableObj?.columns?.length || currentTableObj?.columns_count || 0} cột thuộc tính
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead>
                      <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-card)] text-[var(--text-muted)]">
                        <th className="px-4 py-2.5 font-semibold text-[11px] uppercase tracking-wider">Tên Cột</th>
                        <th className="px-4 py-2.5 font-semibold text-[11px] uppercase tracking-wider">Kiểu Dữ Liệu</th>
                        <th className="px-4 py-2.5 font-semibold text-[11px] uppercase tracking-wider">Mô Tả & Ý Nghĩa</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border-subtle)]">
                      {currentTableObj?.columns?.map((col, cIdx) => {
                        const colKey = `${currentTableName}_${col.name}_${cIdx}`;
                        return (
                          <tr
                            key={colKey}
                            className="hover:bg-[var(--bg-card-hover)] transition-colors"
                          >
                            <td className="px-4 py-2.5 font-mono font-medium text-[var(--text-primary)] flex items-center gap-2">
                              <Columns className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                              <span>{col.name}</span>
                              {col.vn_name && (
                                <span className="font-sans text-[11px] text-[var(--text-muted)]">
                                  ({col.vn_name})
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-2.5 font-mono text-[11px] text-[var(--accent-primary)]">
                              {col.data_type || "VARCHAR"}
                            </td>
                            <td className="px-4 py-2.5 text-[var(--text-secondary)] text-[11px]">
                              {col.description || col.vn_name || `Thuộc tính ${col.name} phục vụ phân tích nghiệp vụ.`}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
