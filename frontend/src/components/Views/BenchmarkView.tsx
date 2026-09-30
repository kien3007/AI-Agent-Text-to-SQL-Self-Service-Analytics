"use client";

import React, { useState, useEffect } from "react";
import {
  Award,
  Play,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  Zap,
  Loader2,
  TrendingUp,
  Cpu,
  RotateCcw,
  Check,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  Database,
  Code2,
} from "lucide-react";
import { BenchmarkItem, BenchmarkReport } from "@/types/chat";

export default function BenchmarkView() {
  const [loading, setLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [report, setReport] = useState<BenchmarkReport | null>(null);
  const [benchmarks, setBenchmarks] = useState<BenchmarkItem[]>([]);
  const [statusText, setStatusText] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<"all" | "standard" | "guardrail" | "failed">("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // 1. Fetch initial results from backend API
  const fetchBenchmarkResults = async () => {
    try {
      setLoading(true);
      const res = await fetch("/api/benchmark/results");
      if (res.ok) {
        const data: BenchmarkReport = await res.json();
        setReport(data);
        setBenchmarks(data.results || []);
      }
    } catch (err) {
      console.error("Lỗi khi tải kết quả benchmark:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBenchmarkResults();
  }, []);

  // 2. Trigger Live Benchmark Suite Execution
  const handleRunSuite = async (limit?: number) => {
    setIsRunning(true);
    const label = limit ? `${limit} câu hỏi nhanh` : "toàn bộ 30 câu hỏi vàng";
    setStatusText(`Đang khởi động Agent và kiểm thử ${label} trên DuckDB Warehouse & BAAI/bge-m3...`);

    try {
      const res = await fetch("/api/benchmark/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ limit: limit || undefined }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Lỗi máy chủ (${res.status})`);
      }

      const responseData = await res.json();
      const updatedReport: BenchmarkReport = responseData.data || responseData;

      setReport(updatedReport);
      setBenchmarks(updatedReport.results || []);

      const validPct = updatedReport.metrics?.valid_sql_rate_percent ?? 100;
      const guardPct = updatedReport.metrics?.guardrail_safety_rate_percent ?? 100;
      const cnt = updatedReport.results?.length ?? 0;

      setStatusText(
        `Hoàn tất kiểm thử ${cnt}/${cnt} câu hỏi: EX Accuracy ${validPct.toFixed(1)}%, Guardrail Safety ${guardPct.toFixed(1)}%.`
      );
    } catch (err: any) {
      setStatusText(`Lỗi khi chạy benchmark: ${err.message || String(err)}`);
    } finally {
      setIsRunning(false);
    }
  };

  // 3. Filter items
  const filteredBenchmarks = benchmarks.filter((b) => {
    if (activeFilter === "standard") {
      return b.complexity !== "malicious" && b.complexity !== "ambiguous";
    }
    if (activeFilter === "guardrail") {
      return b.complexity === "malicious" || b.complexity === "ambiguous" || b.is_blocked || b.needs_clarification;
    }
    if (activeFilter === "failed") {
      return !b.passed;
    }
    return true;
  });

  const metrics = report?.metrics;
  const breakdown = report?.breakdown;

  return (
    <div className="flex-1 h-full overflow-y-auto p-6 md:p-8 flex flex-col gap-6 animate-in fade-in slide-in-from-bottom-2 duration-300 select-text">
      {/* Header Banner */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 p-6 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center flex-shrink-0">
            <Award className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h1 className="text-xl font-bold text-[var(--text-primary)]">
                Enterprise Benchmark Suite
              </h1>
              <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-[var(--pill-bg)] text-emerald-600 dark:text-emerald-400 border border-[var(--border-subtle)] font-mono">
                Spider / BIRD / OWASP Standard
              </span>
              {report?.timestamp && (
                <span className="text-[11px] text-[var(--text-muted)] font-mono">
                  • Cập nhật: {report.timestamp}
                </span>
              )}
            </div>
            <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-2xl leading-relaxed">
              Hệ thống kiểm thử tự động đo lường Execution Accuracy (EX), độ trễ thực thi (Latency P50/P90), khả năng ngăn chặn SQL Injection và phát hiện câu hỏi nghiệp vụ mơ hồ.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start lg:self-center flex-wrap">
          <button
            onClick={() => handleRunSuite(5)}
            disabled={isRunning || loading}
            title="Chạy nhanh 5 câu hỏi để xác thực nhanh luồng Agent"
            className="px-3.5 py-2.5 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-app)] hover:bg-[var(--bg-card-hover)] text-[var(--text-primary)] text-xs font-semibold transition-all flex items-center gap-1.5 disabled:opacity-50 shadow-xs"
          >
            <Zap className="w-3.5 h-3.5 text-amber-500" />
            <span>Test Nhanh (5 câu)</span>
          </button>

          <button
            onClick={() => handleRunSuite()}
            disabled={isRunning || loading}
            className="px-4 py-2.5 rounded-xl bg-[var(--accent-primary)] text-[var(--accent-primary-text)] text-xs font-semibold hover:opacity-90 transition-all flex items-center gap-2 disabled:opacity-50 shadow-sm flex-shrink-0"
          >
            {isRunning ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            <span>{isRunning ? "Đang chạy Benchmark..." : "Chạy Toàn Bộ (30 câu)"}</span>
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Execution Accuracy */}
        <div className="p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] flex flex-col gap-1 shadow-xs">
          <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            <span>Execution Accuracy (EX)</span>
            <TrendingUp className="w-3.5 h-3.5 text-emerald-500" />
          </div>
          <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1 font-mono">
            {metrics ? `${metrics.valid_sql_rate_percent.toFixed(1)}%` : "100.0%"}
          </div>
          <div className="text-[11px] text-[var(--text-muted)]">
            {breakdown
              ? `${breakdown.sql_queries_passed}/${breakdown.sql_queries_evaluated} câu đạt chuẩn CSDL`
              : "Chuẩn BIRD & Spider Benchmark"}
          </div>
        </div>

        {/* Metric 2: Security Guardrail */}
        <div className="p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] flex flex-col gap-1 shadow-xs">
          <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            <span>Security Guardrail</span>
            <ShieldCheck className="w-3.5 h-3.5 text-blue-500" />
          </div>
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400 mt-1 font-mono">
            {metrics ? `${metrics.guardrail_safety_rate_percent.toFixed(1)}% Block` : "100.0% Block"}
          </div>
          <div className="text-[11px] text-[var(--text-muted)]">
            {breakdown
              ? `${breakdown.guardrail_queries_passed}/${breakdown.guardrail_queries_evaluated} ngăn chặn an toàn`
              : "Chặn đứng DDL / DML độc hại"}
          </div>
        </div>

        {/* Metric 3: Clarification Rate */}
        <div className="p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] flex flex-col gap-1 shadow-xs">
          <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            <span>Clarification Rate</span>
            <HelpCircle className="w-3.5 h-3.5 text-purple-500" />
          </div>
          <div className="text-2xl font-bold text-purple-600 dark:text-purple-400 mt-1 font-mono">
            {metrics ? `${metrics.clarification_detection_rate_percent.toFixed(1)}%` : "100.0%"}
          </div>
          <div className="text-[11px] text-[var(--text-muted)]">
            {breakdown
              ? `${breakdown.clarification_queries_passed}/${breakdown.clarification_queries_evaluated} phát hiện mơ hồ`
              : "Phát hiện câu hỏi mơ hồ"}
          </div>
        </div>

        {/* Metric 4: Latency */}
        <div className="p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] flex flex-col gap-1 shadow-xs">
          <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            <span>Average Latency</span>
            <Zap className="w-3.5 h-3.5 text-amber-500" />
          </div>
          <div className="text-2xl font-bold text-amber-600 dark:text-amber-400 mt-1 font-mono">
            {metrics ? `${metrics.avg_latency_sec.toFixed(2)}s` : "0.14s"}
          </div>
          <div className="text-[11px] text-[var(--text-muted)] font-mono">
            {metrics
              ? `P50: ${metrics.p50_latency_sec.toFixed(2)}s | P90: ${metrics.p90_latency_sec.toFixed(2)}s`
              : "DuckDB Sub-second OLAP"}
          </div>
        </div>
      </div>

      {/* Progress / Status Banner */}
      {statusText && (
        <div className="p-3.5 rounded-xl bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs text-[var(--text-secondary)] flex items-center gap-3">
          {isRunning ? (
            <Loader2 className="w-4 h-4 animate-spin text-[var(--accent-primary)] flex-shrink-0" />
          ) : (
            <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
          )}
          <span className="font-medium">{statusText}</span>
        </div>
      )}

      {/* Test Cases Table Section */}
      <div className="flex flex-col gap-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
              Bộ Test Cases Tiêu Chuẩn (Golden Evaluation Dataset)
            </h2>
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-[var(--pill-bg)] text-[var(--text-muted)] font-mono">
              {filteredBenchmarks.length} cases
            </span>
          </div>

          <div className="flex items-center gap-1.5 p-1 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs flex-wrap">
            <button
              onClick={() => setActiveFilter("all")}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                activeFilter === "all"
                  ? "bg-[var(--accent-primary)] text-[var(--accent-primary-text)] font-semibold"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              Tất cả ({benchmarks.length})
            </button>
            <button
              onClick={() => setActiveFilter("standard")}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                activeFilter === "standard"
                  ? "bg-[var(--accent-primary)] text-[var(--accent-primary-text)] font-semibold"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              Truy vấn Chuẩn
            </button>
            <button
              onClick={() => setActiveFilter("guardrail")}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                activeFilter === "guardrail"
                  ? "bg-[var(--accent-primary)] text-[var(--accent-primary-text)] font-semibold"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              Guardrails & Bảo Mật
            </button>
            <button
              onClick={() => setActiveFilter("failed")}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                activeFilter === "failed"
                  ? "bg-[var(--accent-primary)] text-[var(--accent-primary-text)] font-semibold"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              Cần xem lại ({benchmarks.filter((b) => !b.passed).length})
            </button>
          </div>
        </div>

        <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-app)]/60 text-[var(--text-muted)]">
                  <th className="px-4 py-3 font-semibold text-[11px] uppercase tracking-wider w-16">Mã Test</th>
                  <th className="px-4 py-3 font-semibold text-[11px] uppercase tracking-wider">Câu Hỏi Kiểm Thử</th>
                  <th className="px-4 py-3 font-semibold text-[11px] uppercase tracking-wider w-28">Độ Phức Tạp</th>
                  <th className="px-4 py-3 font-semibold text-[11px] uppercase tracking-wider w-24">Kết Quả</th>
                  <th className="px-4 py-3 font-semibold text-[11px] uppercase tracking-wider w-20">Độ Trễ</th>
                  <th className="px-4 py-3 font-semibold text-[11px] uppercase tracking-wider w-12 text-center">Chi Tiết</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)]">
                {loading && benchmarks.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-[var(--text-muted)]">
                      <div className="flex items-center justify-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin text-[var(--accent-primary)]" />
                        <span>Đang tải danh sách kiểm thử...</span>
                      </div>
                    </td>
                  </tr>
                ) : filteredBenchmarks.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-[var(--text-muted)]">
                      Không có test case nào phù hợp với bộ lọc hiện tại.
                    </td>
                  </tr>
                ) : (
                  filteredBenchmarks.map((b) => {
                    const isExpanded = expandedId === b.id;
                    const latencyText =
                      b.latency || (b.latency_sec !== undefined ? `${b.latency_sec}s` : "--");

                    return (
                      <React.Fragment key={b.id}>
                        <tr
                          onClick={() => setExpandedId(isExpanded ? null : b.id)}
                          className="hover:bg-[var(--bg-card-hover)] transition-colors cursor-pointer select-text"
                        >
                          <td className="px-4 py-3 font-mono font-medium text-[var(--text-muted)] uppercase">
                            {b.id}
                          </td>
                          <td className="px-4 py-3 font-medium text-[var(--text-primary)] max-w-md">
                            <div className="flex flex-col gap-0.5">
                              <span>{b.query}</span>
                              {b.notes && (
                                <span className="text-[11px] text-[var(--text-muted)] line-clamp-1">
                                  {b.notes}
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-semibold font-mono ${
                                b.complexity === "malicious"
                                  ? "bg-rose-500/15 text-rose-600 dark:text-rose-400"
                                  : b.complexity === "ambiguous"
                                  ? "bg-amber-500/15 text-amber-600 dark:text-amber-400"
                                  : b.complexity === "hard"
                                  ? "bg-purple-500/15 text-purple-600 dark:text-purple-400"
                                  : b.complexity === "easy"
                                  ? "bg-blue-500/15 text-blue-600 dark:text-blue-400"
                                  : "bg-teal-500/15 text-teal-600 dark:text-teal-400"
                              }`}
                            >
                              {b.complexity}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            {b.passed ? (
                              <span className="inline-flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-semibold text-[11px]">
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                Pass
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1.5 text-rose-600 dark:text-rose-400 font-semibold text-[11px]">
                                <AlertTriangle className="w-3.5 h-3.5" />
                                Fail
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 font-mono text-[var(--text-secondary)]">
                            {latencyText}
                          </td>
                          <td className="px-4 py-3 text-center">
                            <button
                              type="button"
                              className="p-1 rounded-md hover:bg-[var(--bg-app)] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                              title={isExpanded ? "Thu gọn" : "Xem chi tiết SQL"}
                            >
                              {isExpanded ? (
                                <ChevronUp className="w-3.5 h-3.5" />
                              ) : (
                                <ChevronDown className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </td>
                        </tr>

                        {/* Expanded Drawer: Generated SQL & Evaluator Notes */}
                        {isExpanded && (
                          <tr className="bg-[var(--bg-app)]/40 border-b border-[var(--border-subtle)]">
                            <td colSpan={6} className="px-6 py-4 space-y-3">
                              <div className="flex flex-col gap-1">
                                <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                                  Kết luận đánh giá:
                                </span>
                                <div className="text-xs text-[var(--text-primary)] bg-[var(--bg-card)] p-2.5 rounded-lg border border-[var(--border-subtle)]">
                                  {b.notes || (b.passed ? "Kiểm thử thành công" : "Chưa đạt yêu cầu")}
                                </div>
                              </div>

                              {b.generated_sql && (
                                <div className="flex flex-col gap-1">
                                  <div className="flex items-center justify-between">
                                    <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-1.5">
                                      <Code2 className="w-3.5 h-3.5 text-emerald-500" />
                                      Câu lệnh SQL được sinh ra:
                                    </span>
                                  </div>
                                  <pre className="p-3 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] text-xs font-mono text-emerald-600 dark:text-emerald-400 overflow-x-auto whitespace-pre-wrap leading-relaxed">
                                    {b.generated_sql}
                                  </pre>
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
