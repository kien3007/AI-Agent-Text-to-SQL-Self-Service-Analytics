"use client";

import React, { useState, useEffect } from "react";
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Clock,
  Layers,
  Search,
  Filter,
  Loader2,
  ArrowUpRight,
  TrendingUp,
  Activity
} from "lucide-react";
import { QualityReport, DQTestItem } from "@/types/chat";

interface DataQualityDashboardProps {
  domainId: string;
}

export default function DataQualityDashboard({ domainId }: DataQualityDashboardProps) {
  const [report, setReport] = useState<QualityReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [runningTest, setRunningTest] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const fetchQualityReport = async () => {
    if (!domainId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/domains/${domainId}/quality`);
      if (!res.ok) throw new Error(`Lỗi tải dữ liệu chất lượng (${res.status})`);
      const data: QualityReport = await res.json();
      setReport(data);
    } catch (err: any) {
      setError(err.message || "Không thể tải báo cáo chất lượng");
    } finally {
      setLoading(false);
    }
  };

  const runLiveCheck = async () => {
    if (!domainId || runningTest) return;
    setRunningTest(true);
    try {
      const res = await fetch(`/api/domains/${domainId}/quality/run`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Chạy kiểm tra thất bại");
      const resData = await res.json();
      if (resData.report) {
        setReport(resData.report);
      } else {
        await fetchQualityReport();
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setRunningTest(false);
    }
  };

  useEffect(() => {
    fetchQualityReport();
  }, [domainId]);

  const filteredTests = (report?.tests || []).filter((t) => {
    if (statusFilter !== "ALL" && t.status !== statusFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return (
        t.rule.toLowerCase().includes(q) ||
        t.table.toLowerCase().includes(q) ||
        t.description.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="flex flex-col gap-6">
      {/* Top Banner & Control Bar */}
      <div className="p-5 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-[var(--text-primary)]">
              Data Quality & SLA Observability
            </h3>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
              {report?.sla_status || "COMPLIANT"}
            </span>
          </div>
          <p className="text-xs text-[var(--text-secondary)] mt-1">
            Kiểm tra liên tục tỷ lệ Null, tính toàn vẹn khóa ngoại, đột biến volume và độ trễ SLA.
          </p>
        </div>

        <button
          onClick={runLiveCheck}
          disabled={runningTest || loading}
          className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-semibold text-xs transition-colors shadow-xs disabled:opacity-60"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${runningTest ? "animate-spin" : ""}`} />
          <span>{runningTest ? "Đang Chạy Kiểm Tra..." : "Chạy Kiểm Tra Ngay"}</span>
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs">
          {error}
        </div>
      )}

      {loading && !report && (
        <div className="flex flex-col items-center justify-center py-20 text-[var(--text-muted)] gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-purple-500" />
          <p className="text-xs font-medium">Đang tính toán chỉ số Data Health và SLA...</p>
        </div>
      )}

      {report && (
        <>
          {/* KPI Summary Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3.5">
            {/* Overall Score */}
            <div className="p-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col justify-between col-span-2 sm:col-span-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                Health Score
              </span>
              <div className="flex items-baseline gap-1.5 mt-2">
                <span className="text-3xl font-extrabold font-mono text-[var(--text-primary)]">
                  {report.overall_score}%
                </span>
              </div>
              <span className="text-[10px] text-emerald-500 font-medium mt-1">
                Đạt chuẩn Enterprise SLA
              </span>
            </div>

            {/* Total Tests */}
            <div className="p-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                Tổng Số Bài Test
              </span>
              <div className="text-2xl font-bold font-mono text-[var(--text-primary)] mt-2">
                {report.summary.total}
              </div>
              <span className="text-[10px] text-[var(--text-muted)] mt-1">
                Lần chạy: {report.last_run.split(" ")[1]}
              </span>
            </div>

            {/* Passed Tests */}
            <div className="p-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3 text-emerald-500" /> Đạt (Pass)
              </span>
              <div className="text-2xl font-bold font-mono text-emerald-500 mt-2">
                {report.summary.passed}
              </div>
              <span className="text-[10px] text-[var(--text-muted)] mt-1">
                100% tiêu chí chuẩn
              </span>
            </div>

            {/* Warnings */}
            <div className="p-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-1">
                <AlertTriangle className="w-3 h-3 text-amber-500" /> Cảnh Báo
              </span>
              <div className="text-2xl font-bold font-mono text-amber-500 mt-2">
                {report.summary.warnings}
              </div>
              <span className="text-[10px] text-[var(--text-muted)] mt-1">
                Ngưỡng cảnh báo sớm
              </span>
            </div>

            {/* SLA Availability */}
            <div className="p-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-1">
                <Clock className="w-3 h-3 text-purple-500" /> SLA Uptime
              </span>
              <div className="text-2xl font-bold font-mono text-purple-500 mt-2">
                {report.sla_compliance_rate}
              </div>
              <span className="text-[10px] text-[var(--text-muted)] mt-1">
                Target &gt; 99.9%
              </span>
            </div>
          </div>

          {/* Table Summaries Breakdown */}
          <div className="p-5 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col gap-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-2">
              <Layers className="w-4 h-4 text-purple-500" />
              Sức Khỏe Theo Từng Bảng (Table Health Breakdown)
            </h4>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {report.table_summaries.map((tbl) => (
                <div
                  key={tbl.table_name}
                  className="p-3.5 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] flex flex-col justify-between gap-3"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="font-mono text-xs font-bold text-[var(--text-primary)]">
                        {tbl.table_name}
                      </span>
                      <p className="text-[11px] text-[var(--text-secondary)]">
                        {tbl.vn_name}
                      </p>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                      {tbl.health_score}%
                    </span>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <div className="w-full bg-[var(--border-subtle)] rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-emerald-500 h-full rounded-full"
                        style={{ width: `${tbl.health_score}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-between text-[10px] text-[var(--text-muted)] font-mono">
                      <span>{tbl.passed}/{tbl.total_checks} test đạt</span>
                      <span>{tbl.estimated_rows.toLocaleString("vi-VN")} rows</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Detailed Test Logs */}
          <div className="p-5 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col gap-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[var(--border-subtle)]">
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-2">
                  <Activity className="w-4 h-4 text-emerald-500" />
                  Nhật Ký Kiểm Tra Chi Tiết (Detailed Test Logs)
                </h4>
                <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
                  Hiển thị {filteredTests.length} bài kiểm tra thực thi
                </p>
              </div>

              {/* Filters */}
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Tìm theo quy tắc hoặc bảng..."
                    className="pl-8 pr-3 py-1.5 rounded-lg bg-[var(--bg-app)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-hidden focus:border-purple-500 w-52"
                  />
                </div>

                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="px-2.5 py-1.5 rounded-lg bg-[var(--bg-app)] border border-[var(--border-subtle)] text-xs font-semibold text-[var(--text-primary)] focus:outline-hidden focus:border-purple-500"
                >
                  <option value="ALL">Tất cả trạng thái</option>
                  <option value="PASS">Chỉ Đạt (PASS)</option>
                  <option value="WARN">Cảnh báo (WARN)</option>
                  <option value="FAIL">Lỗi (FAIL)</option>
                </select>
              </div>
            </div>

            {/* Test rows table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[var(--border-subtle)] text-[10px] uppercase font-bold text-[var(--text-muted)] tracking-wider">
                    <th className="pb-2.5 font-medium">Trạng Thái</th>
                    <th className="pb-2.5 font-medium">Bảng</th>
                    <th className="pb-2.5 font-medium">Quy Tắc Kiểm Tra</th>
                    <th className="pb-2.5 font-medium">Loại</th>
                    <th className="pb-2.5 font-medium">Tiêu Chuẩn (SLA)</th>
                    <th className="pb-2.5 font-medium">Thực Tế</th>
                    <th className="pb-2.5 font-medium text-right">Thời Gian</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-subtle)]">
                  {filteredTests.map((test) => (
                    <tr
                      key={test.test_id}
                      className="hover:bg-[var(--bg-app)]/50 transition-colors"
                    >
                      <td className="py-2.5">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            test.status === "PASS"
                              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                              : test.status === "WARN"
                              ? "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                              : "bg-rose-500/10 text-rose-600 dark:text-rose-400"
                          }`}
                        >
                          {test.status === "PASS" ? (
                            <CheckCircle2 className="w-3 h-3" />
                          ) : (
                            <AlertTriangle className="w-3 h-3" />
                          )}
                          {test.status}
                        </span>
                      </td>
                      <td className="py-2.5 font-mono font-semibold text-[var(--text-primary)]">
                        {test.table}
                      </td>
                      <td className="py-2.5">
                        <div className="font-semibold text-[var(--text-primary)]">
                          {test.rule}
                        </div>
                        <div className="text-[11px] text-[var(--text-muted)]">
                          {test.description}
                        </div>
                      </td>
                      <td className="py-2.5 font-mono text-[11px] text-[var(--text-secondary)]">
                        {test.rule_type}
                      </td>
                      <td className="py-2.5 font-mono text-[11px] text-[var(--text-muted)]">
                        {test.threshold}
                      </td>
                      <td className="py-2.5 font-mono text-[11px] font-semibold text-[var(--text-primary)]">
                        {test.actual}
                      </td>
                      <td className="py-2.5 font-mono text-[10px] text-[var(--text-muted)] text-right">
                        {test.executed_at.split(" ")[1]}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
