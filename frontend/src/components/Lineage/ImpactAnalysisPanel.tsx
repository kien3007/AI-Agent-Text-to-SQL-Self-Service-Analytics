"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Zap,
  AlertTriangle,
  ShieldAlert,
  ArrowRight,
  TrendingUp,
  Table as TableIcon,
  Bot,
  CheckCircle2,
  Loader2,
  FileWarning,
  Sparkles,
  RefreshCw,
  Info,
  ChevronDown,
  Check,
  Search,
  Columns,
  ShieldCheck,
  X,
} from "lucide-react";
import { ImpactAnalysisResult, TableItem } from "@/types/chat";

interface ImpactAnalysisPanelProps {
  domainId: string;
  tables: TableItem[];
  preselectedTable?: string;
}

export default function ImpactAnalysisPanel({
  domainId,
  tables,
  preselectedTable,
}: ImpactAnalysisPanelProps) {
  // Helper to extract table name safely
  const getTableName = (t?: TableItem): string =>
    t ? (t.table_name || t.name || "") : "";

  const [selectedTable, setSelectedTable] = useState<string>(() => {
    if (preselectedTable) return preselectedTable;
    if (tables && tables.length > 0) return getTableName(tables[0]);
    return "";
  });
  const [selectedColumn, setSelectedColumn] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImpactAnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Dropdown UI states
  const [isTableOpen, setIsTableOpen] = useState(false);
  const [isColumnOpen, setIsColumnOpen] = useState(false);
  const [tableSearch, setTableSearch] = useState("");
  const [columnSearch, setColumnSearch] = useState("");

  const tableDropdownRef = useRef<HTMLDivElement>(null);
  const columnDropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on click outside or escape
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        tableDropdownRef.current &&
        !tableDropdownRef.current.contains(event.target as Node)
      ) {
        setIsTableOpen(false);
      }
      if (
        columnDropdownRef.current &&
        !columnDropdownRef.current.contains(event.target as Node)
      ) {
        setIsColumnOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsTableOpen(false);
        setIsColumnOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  // Sync selectedTable when tables or preselectedTable changes
  useEffect(() => {
    if (preselectedTable && preselectedTable !== selectedTable) {
      setSelectedTable(preselectedTable);
      setSelectedColumn("");
    } else if (tables && tables.length > 0) {
      const isSelectedValid = tables.some(
        (t) => getTableName(t) === selectedTable
      );
      if (!isSelectedValid) {
        setSelectedTable(getTableName(tables[0]));
        setSelectedColumn("");
      }
    }
  }, [preselectedTable, tables, selectedTable]);

  // Current table's columns
  const currentTableObj = tables.find(
    (t) => getTableName(t) === selectedTable
  );
  const availableColumns = currentTableObj?.columns || [];

  const runAnalysis = async (table: string, column?: string) => {
    if (!domainId || !table) return;
    setLoading(true);
    setError(null);

    try {
      let url = `/api/domains/${domainId}/lineage/impact?table=${encodeURIComponent(table)}`;
      if (column && column.trim()) {
        url += `&column=${encodeURIComponent(column.trim())}`;
      }
      const res = await fetch(url);
      if (!res.ok) {
        let msg = `Không thể phân tích tác động (${res.status})`;
        try {
          const errData = await res.json();
          if (errData?.detail) msg = errData.detail;
        } catch (_) {}
        throw new Error(msg);
      }
      const data: ImpactAnalysisResult = await res.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message || "Lỗi khi chạy phân tích tác động");
    } finally {
      setLoading(false);
    }
  };

  // Run initial analysis when selectedTable or domainId changes
  useEffect(() => {
    if (selectedTable && domainId) {
      runAnalysis(selectedTable, selectedColumn || undefined);
    }
  }, [selectedTable, domainId]);

  // Filtering for table dropdown
  const filteredTables = tables.filter((t) => {
    const q = tableSearch.toLowerCase().trim();
    if (!q) return true;
    const name = getTableName(t).toLowerCase();
    const vn = (t.vn_name || "").toLowerCase();
    return name.includes(q) || vn.includes(q);
  });

  // Filtering for column dropdown
  const filteredColumns = availableColumns.filter((c) => {
    const q = columnSearch.toLowerCase().trim();
    if (!q) return true;
    const name = c.name.toLowerCase();
    const vn = (c.vn_name || "").toLowerCase();
    const dt = (c.data_type || "").toLowerCase();
    return name.includes(q) || vn.includes(q) || dt.includes(q);
  });

  return (
    <div className="flex flex-col gap-6">
      {/* Selector & Action Bar */}
      <div className="p-5 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col gap-4">
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-4">
            {/* 1. CUSTOM TABLE SELECTOR DROPDOWN */}
            <div className="relative" ref={tableDropdownRef}>
              <label className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1.5 block">
                Bảng Mục Tiêu (Source Table)
              </label>
              <button
                type="button"
                onClick={() => {
                  setIsTableOpen(!isTableOpen);
                  setIsColumnOpen(false);
                }}
                className={`group h-11 px-3.5 rounded-xl flex items-center justify-between gap-3 text-xs font-medium transition-all duration-200 border cursor-pointer min-w-[240px] max-w-[320px] ${
                  isTableOpen
                    ? "bg-[var(--bg-app)] border-purple-500 ring-2 ring-purple-500/20 text-[var(--text-primary)] shadow-xs"
                    : "bg-[var(--bg-app)] border-[var(--border-subtle)] text-[var(--text-primary)] hover:border-[var(--border-medium)] hover:bg-[var(--bg-sidebar-hover)]"
                }`}
                aria-expanded={isTableOpen}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="w-7 h-7 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center shrink-0 border border-purple-500/20">
                    <TableIcon className="w-3.5 h-3.5" />
                  </div>
                  <div className="flex flex-col text-left truncate">
                    <span className="font-bold text-xs truncate">
                      {selectedTable || "Chọn bảng..."}
                    </span>
                    <span className="text-[10px] text-[var(--text-muted)] truncate">
                      {currentTableObj?.vn_name || "Bảng OLAP"}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0 text-[var(--text-muted)]">
                  {currentTableObj?.columns_count && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[var(--pill-bg)] text-[var(--text-secondary)] border border-[var(--border-subtle)]">
                      {currentTableObj.columns_count} cols
                    </span>
                  )}
                  <ChevronDown
                    className={`w-3.5 h-3.5 text-[var(--text-muted)] transition-transform duration-200 group-hover:text-[var(--text-primary)] ${
                      isTableOpen ? "rotate-180 text-purple-500" : ""
                    }`}
                  />
                </div>
              </button>

              {/* Table Popover Menu */}
              {isTableOpen && (
                <div className="absolute left-0 top-full mt-2 w-80 z-50 rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-card)] backdrop-blur-xl shadow-2xl p-2 animate-in fade-in-0 zoom-in-95 duration-150">
                  <div className="px-2.5 py-1.5 border-b border-[var(--border-subtle)] mb-2 flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      Danh Sách Bảng ({tables.length})
                    </span>
                    <span className="text-[10px] font-mono text-purple-600 dark:text-purple-400 bg-purple-500/10 px-1.5 py-0.5 rounded font-medium">
                      {domainId}
                    </span>
                  </div>

                  {tables.length > 3 && (
                    <div className="relative mb-2 px-1">
                      <Search className="w-3.5 h-3.5 absolute left-3.5 top-2.5 text-[var(--text-muted)]" />
                      <input
                        type="text"
                        placeholder="Tìm kiếm bảng..."
                        value={tableSearch}
                        onChange={(e) => setTableSearch(e.target.value)}
                        className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-[var(--bg-app)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-hidden focus:border-purple-500"
                        autoFocus
                      />
                    </div>
                  )}

                  <div className="max-h-60 overflow-y-auto flex flex-col gap-1 pr-1 no-scrollbar">
                    {filteredTables.map((t) => {
                      const name = getTableName(t);
                      const isSelected = name === selectedTable;
                      return (
                        <button
                          key={name}
                          type="button"
                          onClick={() => {
                            setSelectedTable(name);
                            setSelectedColumn("");
                            setIsTableOpen(false);
                            runAnalysis(name, undefined);
                          }}
                          className={`w-full flex items-center justify-between gap-2 px-3 py-2 rounded-xl text-left transition-all cursor-pointer ${
                            isSelected
                              ? "bg-purple-600/10 text-purple-600 dark:text-purple-400 font-bold border border-purple-500/20"
                              : "hover:bg-[var(--bg-app)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                          }`}
                        >
                          <div className="flex items-center gap-2.5 min-w-0">
                            <TableIcon className="w-4 h-4 shrink-0 text-purple-500" />
                            <div className="flex flex-col min-w-0">
                              <span className="text-xs truncate">{name}</span>
                              <span className="text-[10px] text-[var(--text-muted)] truncate">
                                {t.vn_name || name}
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0">
                            {t.columns_count && (
                              <span className="text-[10px] font-mono text-[var(--text-muted)]">
                                {t.columns_count} cols
                              </span>
                            )}
                            {isSelected && (
                              <Check className="w-4 h-4 text-purple-600 dark:text-purple-400 shrink-0" />
                            )}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* 2. CUSTOM COLUMN SELECTOR DROPDOWN */}
            <div className="relative" ref={columnDropdownRef}>
              <label className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1.5 block">
                Cột Cụ Thể (Column Level - Tùy chọn)
              </label>
              <button
                type="button"
                onClick={() => {
                  setIsColumnOpen(!isColumnOpen);
                  setIsTableOpen(false);
                }}
                className={`group h-11 px-3.5 rounded-xl flex items-center justify-between gap-3 text-xs font-medium transition-all duration-200 border cursor-pointer min-w-[260px] max-w-[360px] ${
                  isColumnOpen
                    ? "bg-[var(--bg-app)] border-purple-500 ring-2 ring-purple-500/20 text-[var(--text-primary)] shadow-xs"
                    : selectedColumn
                    ? "bg-amber-500/5 border-amber-500/30 text-[var(--text-primary)] hover:border-amber-500/50"
                    : "bg-[var(--bg-app)] border-[var(--border-subtle)] text-[var(--text-primary)] hover:border-[var(--border-medium)] hover:bg-[var(--bg-sidebar-hover)]"
                }`}
                aria-expanded={isColumnOpen}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <div
                    className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 border ${
                      selectedColumn
                        ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
                        : "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20"
                    }`}
                  >
                    <Columns className="w-3.5 h-3.5" />
                  </div>

                  <div className="flex flex-col text-left truncate">
                    <span className="font-bold text-xs truncate">
                      {selectedColumn ? selectedColumn : "-- Toàn bộ bảng (Table Level) --"}
                    </span>
                    <span className="text-[10px] text-[var(--text-muted)] truncate">
                      {selectedColumn
                        ? availableColumns.find((c) => c.name === selectedColumn)?.vn_name ||
                          "Phân tích tác động riêng cột"
                        : "Đánh giá toàn diện cả bảng"}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0 text-[var(--text-muted)]">
                  {selectedColumn ? (
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 font-bold">
                      {availableColumns.find((c) => c.name === selectedColumn)?.data_type || "Col"}
                    </span>
                  ) : (
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[var(--pill-bg)] text-[var(--text-muted)] border border-[var(--border-subtle)]">
                      All cols
                    </span>
                  )}
                  <ChevronDown
                    className={`w-3.5 h-3.5 text-[var(--text-muted)] transition-transform duration-200 group-hover:text-[var(--text-primary)] ${
                      isColumnOpen ? "rotate-180 text-purple-500" : ""
                    }`}
                  />
                </div>
              </button>

              {/* Column Popover Menu */}
              {isColumnOpen && (
                <div className="absolute left-0 top-full mt-2 w-88 z-50 rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-card)] backdrop-blur-xl shadow-2xl p-2 animate-in fade-in-0 zoom-in-95 duration-150">
                  <div className="px-2.5 py-1.5 border-b border-[var(--border-subtle)] mb-2 flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      Chọn Cột Cần Giả Lập ({availableColumns.length})
                    </span>
                    <span className="text-[10px] font-mono text-[var(--text-secondary)]">
                      {selectedTable}
                    </span>
                  </div>

                  <div className="relative mb-2 px-1">
                    <Search className="w-3.5 h-3.5 absolute left-3.5 top-2.5 text-[var(--text-muted)]" />
                    <input
                      type="text"
                      placeholder="Tìm kiếm cột theo tên, kiểu dữ liệu..."
                      value={columnSearch}
                      onChange={(e) => setColumnSearch(e.target.value)}
                      className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-[var(--bg-app)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-hidden focus:border-purple-500"
                      autoFocus
                    />
                  </div>

                  <div className="max-h-64 overflow-y-auto flex flex-col gap-1 pr-1 no-scrollbar">
                    {/* Default Option: Table Level */}
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedColumn("");
                        setIsColumnOpen(false);
                        runAnalysis(selectedTable, undefined);
                      }}
                      className={`w-full flex items-center justify-between gap-2 px-3 py-2 rounded-xl text-left transition-all cursor-pointer ${
                        !selectedColumn
                          ? "bg-purple-600/10 text-purple-600 dark:text-purple-400 font-bold border border-purple-500/20"
                          : "hover:bg-[var(--bg-app)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <TableIcon className="w-4 h-4 shrink-0 text-blue-500" />
                        <div className="flex flex-col min-w-0">
                          <span className="text-xs font-semibold truncate">
                            -- Toàn bộ bảng (Table Level) --
                          </span>
                          <span className="text-[10px] text-[var(--text-muted)] truncate">
                            Mô phỏng blast radius toàn bộ bảng
                          </span>
                        </div>
                      </div>
                      {!selectedColumn && (
                        <Check className="w-4 h-4 text-purple-600 dark:text-purple-400 shrink-0" />
                      )}
                    </button>

                    <div className="h-px bg-[var(--border-subtle)] my-1" />

                    {/* Column List */}
                    {filteredColumns.map((col) => {
                      const isSelected = col.name === selectedColumn;
                      return (
                        <button
                          key={col.name}
                          type="button"
                          onClick={() => {
                            setSelectedColumn(col.name);
                            setIsColumnOpen(false);
                            runAnalysis(selectedTable, col.name);
                          }}
                          className={`w-full flex items-center justify-between gap-2 px-3 py-2 rounded-xl text-left transition-all cursor-pointer ${
                            isSelected
                              ? "bg-purple-600/10 text-purple-600 dark:text-purple-400 font-bold border border-purple-500/20"
                              : "hover:bg-[var(--bg-app)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                          }`}
                        >
                          <div className="flex items-center gap-2.5 min-w-0">
                            <Columns className="w-3.5 h-3.5 shrink-0 text-amber-500" />
                            <div className="flex flex-col min-w-0">
                              <div className="flex items-center gap-1.5">
                                <span className="text-xs font-mono font-semibold truncate">
                                  {col.name}
                                </span>
                                {col.is_pk && (
                                  <span className="px-1 py-0.2 rounded text-[9px] font-bold bg-amber-500/20 text-amber-600 dark:text-amber-400">
                                    PK
                                  </span>
                                )}
                                {col.is_fk && (
                                  <span className="px-1 py-0.2 rounded text-[9px] font-bold bg-blue-500/20 text-blue-600 dark:text-blue-400">
                                    FK
                                  </span>
                                )}
                              </div>
                              {col.vn_name && (
                                <span className="text-[10px] text-[var(--text-muted)] truncate">
                                  {col.vn_name}
                                </span>
                              )}
                            </div>
                          </div>

                          <div className="flex items-center gap-1.5 shrink-0">
                            <span className="text-[10px] font-mono text-[var(--text-muted)] px-1.5 py-0.5 rounded bg-[var(--pill-bg)] border border-[var(--border-subtle)]">
                              {col.data_type}
                            </span>
                            {isSelected && (
                              <Check className="w-4 h-4 text-purple-600 dark:text-purple-400 shrink-0" />
                            )}
                          </div>
                        </button>
                      );
                    })}

                    {filteredColumns.length === 0 && (
                      <div className="p-3 text-center text-xs text-[var(--text-muted)]">
                        Không tìm thấy cột phù hợp với từ khóa
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Trigger Analysis Button */}
          <div className="flex items-end">
            <button
              onClick={() => runAnalysis(selectedTable, selectedColumn || undefined)}
              disabled={loading || !selectedTable}
              className="w-full sm:w-auto h-11 flex items-center justify-center gap-2 px-6 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-semibold text-xs transition-all shadow-xs disabled:opacity-60 cursor-pointer shrink-0"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Zap className="w-4 h-4" />
              )}
              <span>Chạy Giả Lập Tác Động</span>
            </button>
          </div>
        </div>

        {/* Current Active Mode Chip */}
        <div className="pt-2 border-t border-[var(--border-subtle)] flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-[var(--text-muted)] text-[11px]">Chế độ phân tích:</span>
            {selectedColumn ? (
              <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-300 font-medium text-xs">
                <Columns className="w-3.5 h-3.5 text-amber-500" />
                <span>
                  Cột: <strong className="font-mono">{selectedTable}.{selectedColumn}</strong>
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedColumn("");
                    runAnalysis(selectedTable, undefined);
                  }}
                  className="hover:bg-amber-500/20 rounded p-0.5 ml-1 transition-colors cursor-pointer text-amber-600 dark:text-amber-400"
                  title="Hủy chọn cột, chuyển về cấp bảng"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-700 dark:text-purple-300 font-medium text-xs">
                <TableIcon className="w-3.5 h-3.5 text-purple-500" />
                <span>
                  Cấp Bảng: <strong className="font-mono">{selectedTable}</strong> (Tất cả cột)
                </span>
              </div>
            )}
          </div>

          <span className="text-[11px] text-[var(--text-muted)]">
            Tự động mô phỏng ngay khi đổi bảng hoặc cột
          </span>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => runAnalysis(selectedTable, selectedColumn || undefined)}
            className="px-3 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-700 dark:text-rose-300 font-semibold text-xs transition-colors shrink-0 flex items-center gap-1.5 cursor-pointer"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Thử lại</span>
          </button>
        </div>
      )}

      {loading && (
        <div className="flex flex-col items-center justify-center py-20 text-[var(--text-muted)] gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-purple-500" />
          <p className="text-xs font-medium">Đang tính toán blast radius và duyệt đồ thị phụ thuộc DAG...</p>
        </div>
      )}

      {!loading && result && (
        <div className="flex flex-col gap-6">
          {/* SAFE ALERT BANNER WHEN RISK IS LOW */}
          {!result.risk_assessment.is_breaking_change && result.target.column_name && (
            <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-start gap-3 text-emerald-600 dark:text-emerald-400">
              <ShieldCheck className="w-5 h-5 flex-shrink-0 mt-0.5 text-emerald-500" />
              <div className="flex-1">
                <h4 className="text-xs font-bold uppercase tracking-wider">
                  Mô Phỏng An Toàn (Safe Column Modification)
                </h4>
                <p className="text-xs mt-1 text-emerald-700 dark:text-emerald-300 leading-relaxed">
                  Cột <code className="font-mono font-bold bg-emerald-500/20 px-1.5 py-0.5 rounded text-emerald-800 dark:text-emerald-200">{result.target.column_name}</code> không nằm trong công thức của bất kỳ chỉ số Semantic Metric nào và không bị ràng buộc bởi khóa ngoại. Có thể sửa đổi hoặc drop mà không gây gãy pipeline báo cáo.
                </p>
              </div>
            </div>
          )}

          {/* BREAKING CHANGE ALERT BANNER */}
          {result.risk_assessment.is_breaking_change && (
            <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 flex items-start gap-3 text-rose-600 dark:text-rose-400">
              <ShieldAlert className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <h4 className="text-xs font-bold uppercase tracking-wider">
                  Cảnh Báo Phá Vỡ Tương Thích (Breaking Change Detected)
                </h4>
                <p className="text-xs mt-1 text-rose-700 dark:text-rose-300 leading-relaxed">
                  {result.target.column_name
                    ? `Sửa đổi hoặc drop cột "${result.target.column_name}" sẽ làm gãy ${result.direct_breaking_metrics?.length || 0} chỉ số nghiệp vụ xuôi dòng.`
                    : "Thay đổi hoặc drop thực thể này sẽ làm hỏng trực tiếp các chỉ số nghiệp vụ và hệ thống báo cáo xuôi dòng."}
                </p>
                {result.direct_breaking_metrics && result.direct_breaking_metrics.length > 0 && (
                  <div className="mt-2.5 flex flex-col gap-1.5 pt-2 border-t border-rose-500/20">
                    <span className="text-[11px] font-bold">Các metric bị phá vỡ công thức trực tiếp:</span>
                    {result.direct_breaking_metrics.map((dbm, idx) => (
                      <div key={idx} className="text-[11px] flex items-center gap-1.5 font-mono">
                        <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                        <span className="font-semibold">{dbm.label || dbm.metric_id}:</span>
                        <span>{dbm.reason}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Assessment KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Risk Level */}
            <div className="p-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                Mức Độ Rủi Ro (Risk Level)
              </span>
              <div className="flex items-center gap-2 mt-2">
                <span
                  className="px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider"
                  style={{
                    backgroundColor: `${result.risk_assessment.risk_color}20`,
                    color: result.risk_assessment.risk_color,
                    border: `1px solid ${result.risk_assessment.risk_color}40`,
                  }}
                >
                  {result.risk_assessment.risk_level}
                </span>
                <span className="text-xs text-[var(--text-secondary)] font-medium">
                  {result.risk_assessment.risk_level === "CRITICAL"
                    ? "Rất Nghiêm Trọng"
                    : result.risk_assessment.risk_level === "HIGH"
                    ? "Rủi Ro Cao"
                    : result.risk_assessment.risk_level === "MEDIUM"
                    ? "Rủi Ro Trung Bình"
                    : "An Toàn (Rủi Ro Thấp)"}
                </span>
              </div>
            </div>

            {/* Blast Radius Score */}
            <div className="p-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                  Blast Radius Score
                </span>
                <span className="font-mono text-xs font-bold text-[var(--text-primary)]">
                  {result.risk_assessment.blast_radius_score}%
                </span>
              </div>
              <div className="w-full bg-[var(--bg-app)] rounded-full h-2.5 mt-3 overflow-hidden border border-[var(--border-subtle)]">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${result.risk_assessment.blast_radius_score}%`,
                    backgroundColor: result.risk_assessment.risk_color,
                  }}
                />
              </div>
            </div>

            {/* Total Impacted Count */}
            <div className="p-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                Tổng Số Thực Thể Bị Ảnh Hưởng
              </span>
              <div className="text-2xl font-bold font-mono text-[var(--text-primary)] mt-1">
                {result.risk_assessment.total_impacted_entities}{" "}
                <span className="text-xs font-normal text-[var(--text-muted)]">
                  {result.target.column_name ? "entities liên quan cột" : "nodes downstream"}
                </span>
              </div>
            </div>
          </div>

          {/* Breakdown by Category */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Impacted Tables */}
            <div className="p-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col gap-3">
              <div className="flex items-center justify-between pb-2 border-b border-[var(--border-subtle)]">
                <div className="flex items-center gap-1.5 text-xs font-bold text-[var(--text-primary)]">
                  <TableIcon className="w-4 h-4 text-purple-500" />
                  <span>Bảng Liên Đới ({result.impact_breakdown.tables.length})</span>
                </div>
              </div>
              <div className="flex flex-col gap-2 max-h-52 overflow-y-auto no-scrollbar">
                {result.impact_breakdown.tables.length === 0 ? (
                  <span className="text-xs text-[var(--text-muted)] italic py-2">
                    {result.target.column_name
                      ? "Không có bảng ngoại khóa (FK) nào phụ thuộc vào cột này"
                      : "Không có bảng phụ thuộc trực tiếp"}
                  </span>
                ) : (
                  result.impact_breakdown.tables.map((t, idx) => (
                    <div
                      key={`impact-tbl-${t.id || t.name}-${idx}`}
                      className="p-2.5 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] flex flex-col gap-0.5"
                    >
                      <span className="font-mono text-xs font-bold text-[var(--text-primary)]">
                        {t.name}
                      </span>
                      <span className="text-[11px] text-[var(--text-secondary)]">
                        {t.vn_name || t.name} • {(t.row_count ?? 0).toLocaleString("vi-VN")} rows
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Impacted Semantic Metrics */}
            <div className="p-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col gap-3">
              <div className="flex items-center justify-between pb-2 border-b border-[var(--border-subtle)]">
                <div className="flex items-center gap-1.5 text-xs font-bold text-[var(--text-primary)]">
                  <TrendingUp className="w-4 h-4 text-emerald-500" />
                  <span>Chỉ Số Nghiệp Vụ ({result.impact_breakdown.metrics.length})</span>
                </div>
              </div>
              <div className="flex flex-col gap-2 max-h-52 overflow-y-auto no-scrollbar">
                {result.impact_breakdown.metrics.length === 0 ? (
                  <span className="text-xs text-[var(--text-muted)] italic py-2">
                    {result.target.column_name
                      ? "Không có metric nào dùng cột này"
                      : "Không có metric bị ảnh hưởng"}
                  </span>
                ) : (
                  result.impact_breakdown.metrics.map((m, idx) => (
                    <div
                      key={`impact-metric-${m.id || m.name}-${idx}`}
                      className={`p-2.5 rounded-xl border flex flex-col gap-1 ${
                        m.is_direct_break
                          ? "bg-rose-500/10 border-rose-500/30 text-rose-600 dark:text-rose-400"
                          : "bg-[var(--bg-app)] border-[var(--border-subtle)]"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-xs text-[var(--text-primary)]">
                          {m.name}
                        </span>
                        {m.is_direct_break && (
                          <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-rose-500 text-white uppercase">
                            Gãy Công Thức
                          </span>
                        )}
                      </div>
                      {m.sql_expression && (
                        <span className="font-mono text-[10px] text-[var(--text-muted)] truncate">
                          SQL: {m.sql_expression}
                        </span>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Impacted Downstream Consumers */}
            <div className="p-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col gap-3">
              <div className="flex items-center justify-between pb-2 border-b border-[var(--border-subtle)]">
                <div className="flex items-center gap-1.5 text-xs font-bold text-[var(--text-primary)]">
                  <Bot className="w-4 h-4 text-rose-500" />
                  <span>Consumers / AI Queries ({result.impact_breakdown.consumers.length})</span>
                </div>
              </div>
              <div className="flex flex-col gap-2 max-h-52 overflow-y-auto no-scrollbar">
                {result.impact_breakdown.consumers.length === 0 ? (
                  <span className="text-xs text-[var(--text-muted)] italic py-2">
                    {result.target.column_name
                      ? "Không có consumer nào bị ảnh hưởng trực tiếp"
                      : "Không có consumer liên quan"}
                  </span>
                ) : (
                  result.impact_breakdown.consumers.map((c, idx) => (
                    <div
                      key={`impact-consumer-${c.id || c.name}-${idx}`}
                      className="p-2.5 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] flex flex-col gap-0.5"
                    >
                      <span className="font-bold text-xs text-[var(--text-primary)]">
                        {c.name}
                      </span>
                      <span className="text-[11px] text-[var(--text-muted)] font-mono">
                        {c.type || "Downstream Service"}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Recommendations List */}
          <div className="p-5 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col gap-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-500" />
              Khuyến Nghị Xử Lý An Toàn (Actionable Mitigation)
            </h3>
            <ul className="flex flex-col gap-2">
              {result.recommendations.map((rec, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2.5 text-xs text-[var(--text-secondary)] leading-relaxed"
                >
                  <ArrowRight className="w-3.5 h-3.5 text-purple-500 flex-shrink-0 mt-0.5" />
                  <span>{rec}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
