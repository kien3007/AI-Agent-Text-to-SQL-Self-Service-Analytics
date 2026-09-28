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
  Zap,
  Activity,
  Layers3
} from "lucide-react";
import {
  DataContract,
  LineageGraphData,
  LineageGraphNode,
  TableItem
} from "@/types/chat";
import LineageFlowCanvas from "../Lineage/LineageFlowCanvas";
import NodeInspectorDrawer from "../Lineage/NodeInspectorDrawer";
import ImpactAnalysisPanel from "../Lineage/ImpactAnalysisPanel";
import DataQualityDashboard from "../Lineage/DataQualityDashboard";
import DataContractGovernance from "../Lineage/DataContractGovernance";

interface LineageViewProps {
  domainId: string;
}

type LineageSubTab = "pipeline" | "impact" | "quality" | "governance";

export default function LineageView({ domainId }: LineageViewProps) {
  const [activeTab, setActiveTab] = useState<LineageSubTab>("pipeline");
  const [loading, setLoading] = useState(false);
  const [contract, setContract] = useState<DataContract | null>(null);
  const [lineageGraph, setLineageGraph] = useState<LineageGraphData | null>(null);
  const [domainTables, setDomainTables] = useState<TableItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Inspector & Impact state
  const [selectedNode, setSelectedNode] = useState<LineageGraphNode | null>(null);
  const [preselectedImpactTable, setPreselectedImpactTable] = useState<string>("");

  useEffect(() => {
    if (!domainId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);
    setSelectedNode(null);

    Promise.all([
      fetch(`/api/domains/${domainId}/contract`).then((res) => (res.ok ? res.json() : null)),
      fetch(`/api/domains/${domainId}/lineage`).then((res) => (res.ok ? res.json() : null)),
      fetch(`/api/domains/${domainId}`).then((res) => (res.ok ? res.json() : null)),
    ])
      .then(([contractData, lineageData, domainDetails]) => {
        if (!isMounted) return;
        setContract(contractData);
        if (lineageData && lineageData.lineage) {
          setLineageGraph(lineageData.lineage as LineageGraphData);
        }
        if (domainDetails && domainDetails.tables) {
          const normalizedTables = domainDetails.tables.map((t: any) => ({
            ...t,
            name: t.name || t.table_name || "",
            table_name: t.table_name || t.name || "",
          }));
          setDomainTables(normalizedTables);
          if (normalizedTables.length > 0) {
            const firstTable = normalizedTables[0].name || normalizedTables[0].table_name || "";
            setPreselectedImpactTable((prev) => {
              const alreadyValid = normalizedTables.some(
                (item: any) => (item.name || item.table_name) === prev
              );
              return alreadyValid && prev ? prev : firstTable;
            });
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

  const pipelineStages = [
    {
      title: "Raw Data Source",
      desc: "Kafka CDC / MySQL 8.0",
      icon: Database,
      status: "Active",
      type: "Ingest",
    },
    {
      title: "Stream / CDC Buffer",
      desc: "Apache Kafka Event Hub",
      icon: Server,
      status: "Synced",
      type: "Buffer",
    },
    {
      title: "Doris OLAP Warehouse",
      desc: "Marts & Aggregation",
      icon: Layers,
      status: "Online",
      type: "Storage",
    },
    {
      title: "Multi-Agent Query Engine",
      desc: "DAIL-SQL & Semantic Layer",
      icon: Cpu,
      status: "Serving",
      type: "Analytics",
    },
  ];

  return (
    <div className="flex-1 h-full overflow-y-auto p-6 md:p-8 flex flex-col gap-6 animate-in fade-in slide-in-from-bottom-2 duration-300 select-text">
      {/* Header Banner */}
      <div className="shrink-0 flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center flex-shrink-0">
            <GitMerge className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-bold text-[var(--text-primary)]">
                Data Lineage & Governance Hub
              </h1>
              <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-[var(--pill-bg)] text-purple-600 dark:text-purple-400 border border-[var(--border-subtle)] font-mono">
                {domainId}
              </span>
            </div>
            <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-2xl leading-relaxed">
              Truy vết nguồn gốc luồng dữ liệu tương tác (Interactive DAG), quan sát chất lượng dữ liệu SLA tự động và mô phỏng tác động thay đổi schema.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] text-xs text-[var(--text-secondary)]">
            <RefreshCw className="w-3.5 h-3.5 text-emerald-500 animate-spin" style={{ animationDuration: "6s" }} />
            <span>Tự động đồng bộ</span>
          </div>
        </div>
      </div>

      {/* Sub-tab Navigation Bar with increased height & full text display */}
      <div className="shrink-0 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-2.5 p-2 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs w-full">
        {[
          {
            id: "pipeline",
            title: "Sơ Đồ Luồng Dữ Liệu",
            subtitle: "DAG Pipeline & Architecture",
            icon: GitMerge,
            badge: lineageGraph ? `${lineageGraph.nodes.length} nodes` : undefined,
            activeColor: "bg-purple-600",
          },
          {
            id: "impact",
            title: "Phân Tích Tác Động",
            subtitle: "Impact Simulator & Blast Radius",
            icon: Zap,
            badge: "Blast Radius",
            activeColor: "bg-purple-600",
          },
          {
            id: "quality",
            title: "Chất Lượng Dữ Liệu & SLA",
            subtitle: "Observability & Anomaly Checks",
            icon: ShieldCheck,
            badge: "97.5% Health",
            activeColor: "bg-purple-600",
          },
          {
            id: "governance",
            title: "Data Contract & Tuân Thủ",
            subtitle: "Data Mesh Governance & PII",
            icon: FileCheck2,
            badge: "Data Mesh",
            activeColor: "bg-purple-600",
          },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as LineageSubTab)}
              className={`flex items-center gap-3 p-3 rounded-xl transition-all cursor-pointer text-left w-full ${
                isActive
                  ? "bg-purple-600 text-white shadow-sm ring-1 ring-purple-500/30"
                  : "bg-[var(--bg-app)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-sidebar-hover)] border border-[var(--border-subtle)]"
              }`}
            >
              <div
                className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 transition-colors ${
                  isActive
                    ? "bg-white/20 text-white"
                    : "bg-purple-500/10 text-purple-600 dark:text-purple-400"
                }`}
              >
                <Icon className="w-4 h-4" />
              </div>

              <div className="flex flex-col min-w-0 flex-1">
                <div className="flex items-center justify-between gap-1.5 flex-wrap">
                  <span className="text-xs font-bold leading-snug">
                    {tab.title}
                  </span>
                  {tab.badge && (
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-medium shrink-0 ${
                        isActive
                          ? "bg-white/25 text-white"
                          : "bg-[var(--pill-bg)] text-[var(--text-muted)] border border-[var(--border-subtle)]"
                      }`}
                    >
                      {tab.badge}
                    </span>
                  )}
                </div>
                <span
                  className={`text-[11px] leading-tight mt-0.5 ${
                    isActive ? "text-purple-100" : "text-[var(--text-muted)]"
                  }`}
                >
                  {tab.subtitle}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {loading && (
        <div className="flex flex-col items-center justify-center py-20 text-[var(--text-muted)] gap-3 shrink-0">
          <Loader2 className="w-6 h-6 animate-spin text-purple-500" />
          <p className="text-xs font-medium">Đang nạp đồ thị Lineage và hợp đồng Data Governance...</p>
        </div>
      )}

      {error && (
        <div className="shrink-0 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs">
          {error}
        </div>
      )}

      {!loading && (
        <>
          {/* TAB 1: INTERACTIVE DAG PIPELINE */}
          {activeTab === "pipeline" && (
            <div className="relative flex flex-col gap-6 shrink-0">
              {/* Interactive React Flow Canvas */}
              <div className="relative shrink-0">
                <LineageFlowCanvas
                  graphData={lineageGraph}
                  onSelectNode={setSelectedNode}
                  selectedNodeId={selectedNode?.id}
                />

                {/* Node Inspector Drawer */}
                <NodeInspectorDrawer
                  node={selectedNode}
                  onClose={() => setSelectedNode(null)}
                  onSimulateImpact={(tblName) => {
                    setPreselectedImpactTable(tblName);
                    setSelectedNode(null);
                    setActiveTab("impact");
                  }}
                />
              </div>

              {/* End-to-End Pipeline Stages Overview */}
              <div className="flex flex-col gap-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] flex items-center gap-2">
                  <Layers3 className="w-4 h-4 text-purple-500" />
                  Tổng Quan Các Tầng Xử Lý (End-to-End Pipeline Stages)
                </h3>

                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                  {pipelineStages.map((stage, idx) => {
                    const IconComponent = stage.icon;
                    return (
                      <div
                        key={idx}
                        className="p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] flex flex-col justify-between shadow-xs hover:border-[var(--border-medium)] transition-all"
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
            </div>
          )}

          {/* TAB 2: IMPACT ANALYSIS SIMULATOR */}
          {activeTab === "impact" && (
            <ImpactAnalysisPanel
              domainId={domainId}
              tables={domainTables}
              preselectedTable={preselectedImpactTable}
            />
          )}

          {/* TAB 3: DATA QUALITY & SLA OBSERVABILITY */}
          {activeTab === "quality" && (
            <DataQualityDashboard domainId={domainId} />
          )}

          {/* TAB 4: DATA CONTRACT & GOVERNANCE */}
          {activeTab === "governance" && (
            <DataContractGovernance domainId={domainId} contract={contract} />
          )}
        </>
      )}
    </div>
  );
}
