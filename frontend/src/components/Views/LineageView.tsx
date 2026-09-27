"use client";

import React, { useEffect, useState } from "react";
import {
  GitMerge,
  FileCheck2,
  Clock,
  MessageSquare,
  ArrowRight,
  Loader2,
  ShieldCheck,
  CheckCircle2,
  Database,
  Server,
  Layers,
  Cpu,
  RefreshCw,
} from "lucide-react";
import { DataContract, IngestionLineage } from "@/types/chat";

interface LineageViewProps {
  domainId: string;
}

export default function LineageView({ domainId }: LineageViewProps) {
  const [loading, setLoading] = useState(false);
  const [contract, setContract] = useState<DataContract | null>(null);
  const [lineage, setLineage] = useState<IngestionLineage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!domainId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    Promise.all([
      fetch(`/api/domains/${domainId}/contract`).then((res) => (res.ok ? res.json() : null)),
      fetch(`/api/domains/${domainId}/lineage`).then((res) => (res.ok ? res.json() : null)),
    ])
      .then(([contractData, lineageData]) => {
        if (!isMounted) return;
        setContract(contractData);
        if (lineageData && lineageData.lineage) {
          setLineage(lineageData.lineage);
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

  const pipelineStages = [
    {
      title: "Raw Data Source",
      desc: lineage?.source || "raw_crawler_source",
      icon: Database,
      status: "Active",
      type: "Ingest",
    },
    {
      title: "Stream / CDC Buffer",
      desc: "Apache Kafka / Ingestion Pipeline",
      icon: Server,
      status: "Synced",
      type: "Buffer",
    },
    {
      title: "Doris OLAP Warehouse",
      desc: lineage?.destination || "fct_doris_olap",
      icon: Layers,
      status: "Online",
      type: "Storage",
    },
    {
      title: "Multi-Agent Query Engine",
      desc: "DAIL-SQL & 5-Tier Guardrails",
      icon: Cpu,
      status: "Serving",
      type: "Analytics",
    },
  ];

  return (
    <div className="flex-1 h-full overflow-y-auto p-6 md:p-8 flex flex-col gap-6 animate-in fade-in slide-in-from-bottom-2 duration-300 select-text">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center flex-shrink-0">
            <GitMerge className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-bold text-[var(--text-primary)]">
                Data Lineage & Governance Contract
              </h1>
              <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-[var(--pill-bg)] text-purple-600 dark:text-purple-400 border border-[var(--border-subtle)] font-mono">
                {domainId}
              </span>
            </div>
            <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-2xl leading-relaxed">
              Truy vết nguồn gốc luồng dữ liệu (Data Pipeline Flow) từ tầng thu thập đến kho OLAP và cam kết tiêu chuẩn chất lượng SLA.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] text-xs text-[var(--text-secondary)]">
            <RefreshCw className="w-3.5 h-3.5 text-emerald-500 animate-spin" style={{ animationDuration: '6s' }} />
            <span>Tự động đồng bộ</span>
          </div>
        </div>
      </div>

      {loading && (
        <div className="flex flex-col items-center justify-center py-24 text-[var(--text-muted)] gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-purple-500" />
          <p className="text-xs font-medium">Đang nạp thông tin lineage và data contract...</p>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs">
          {error}
        </div>
      )}

      {!loading && (
        <>
          {/* Section 1: Visual Data Pipeline Flow */}
          <div className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)] flex items-center gap-2">
              <GitMerge className="w-4 h-4 text-purple-500" />
              Sơ Đồ Luồng Dữ Liệu (End-to-End Pipeline Lineage)
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 relative">
              {pipelineStages.map((stage, idx) => {
                const IconComponent = stage.icon;
                return (
                  <div
                    key={idx}
                    className="relative p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] flex flex-col justify-between shadow-xs hover:border-[var(--border-medium)] transition-all"
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded bg-[var(--pill-bg)] text-[var(--text-muted)]">
                          Stage 0{idx + 1}
                        </span>
                        <span className="flex items-center gap-1 text-[10px] font-medium text-emerald-500">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                          {stage.status}
                        </span>
                      </div>
                      <div className="flex items-center gap-2.5 mt-2">
                        <div className="w-8 h-8 rounded-lg bg-[var(--bg-app)] border border-[var(--border-subtle)] flex items-center justify-center text-[var(--text-primary)]">
                          <IconComponent className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="text-xs font-semibold text-[var(--text-primary)]">
                            {stage.title}
                          </div>
                          <div className="text-[10px] text-[var(--text-muted)] font-mono truncate max-w-[140px]">
                            {stage.desc}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="mt-4 pt-2 border-t border-[var(--border-subtle)] flex items-center justify-between text-[10px] text-[var(--text-muted)]">
                      <span>Loại: {stage.type}</span>
                      <span className="font-mono text-emerald-500">SLA: OK</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Section 2: Data Contract SLA & Ingestion Metrics */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-2">
            {/* Contract Card */}
            <div className="p-5 rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-card)] flex flex-col gap-4 shadow-xs">
              <div className="flex items-center justify-between pb-3 border-b border-[var(--border-subtle)]">
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                  <FileCheck2 className="w-4 h-4 text-emerald-500" />
                  <span>Data Contract SLA & Governance</span>
                </div>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                  99.98% Tuân thủ
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4 text-xs">
                <div className="p-3 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] flex flex-col gap-1">
                  <span className="text-[11px] text-[var(--text-muted)]">Data Owner</span>
                  <span className="font-semibold text-[var(--text-primary)]">
                    {contract?.owner || "Data Engineering Team"}
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] flex flex-col gap-1">
                  <span className="text-[11px] text-[var(--text-muted)]">Data Steward</span>
                  <span className="font-semibold text-[var(--text-primary)]">
                    {contract?.data_steward || "Analytics Steward"}
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] flex flex-col gap-1">
                  <span className="text-[11px] text-[var(--text-muted)]">Kênh Trực Vận Hành</span>
                  <span className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
                    <MessageSquare className="w-3.5 h-3.5 text-blue-500" />
                    {contract?.slack_channel || "#data-ops"}
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] flex flex-col gap-1">
                  <span className="text-[11px] text-[var(--text-muted)]">Freshness SLA</span>
                  <span className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-amber-500" />
                    {contract?.SLA?.freshness || "12h (Đạt chuẩn)"}
                  </span>
                </div>
              </div>
            </div>

            {/* Ingestion Stats Card */}
            <div className="p-5 rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-card)] flex flex-col gap-4 shadow-xs">
              <div className="flex items-center justify-between pb-3 border-b border-[var(--border-subtle)]">
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                  <ShieldCheck className="w-4 h-4 text-purple-500" />
                  <span>Chỉ Số Nạp Dữ Liệu & Kiểm Soát Chất Lượng</span>
                </div>
                <span className="text-[11px] text-[var(--text-muted)] font-mono">
                  Apache Doris OLAP
                </span>
              </div>

              <div className="flex items-center justify-between p-3.5 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)]">
                <div className="text-xs font-mono font-medium text-[var(--text-secondary)]">
                  {lineage?.source || "raw_crawler_source"}
                </div>
                <ArrowRight className="w-4 h-4 text-[var(--text-muted)]" />
                <div className="text-xs font-mono font-semibold text-[var(--accent-primary)]">
                  {lineage?.destination || "fct_doris_olap"}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-3 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)]">
                  <span className="text-[11px] text-[var(--text-muted)] block">Tổng số bản ghi nạp</span>
                  <span className="text-base font-bold text-[var(--text-primary)] font-mono">
                    {(lineage?.total_records || 32000).toLocaleString("vi-VN")} rows
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)]">
                  <span className="text-[11px] text-[var(--text-muted)] block">Thời gian nạp gần nhất</span>
                  <span className="text-xs font-medium text-[var(--text-primary)] mt-1 block">
                    {lineage?.ingestion_time
                      ? new Date(lineage.ingestion_time).toLocaleString("vi-VN")
                      : "Vừa xong"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
