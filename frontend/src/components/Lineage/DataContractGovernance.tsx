"use client";

import React, { useState } from "react";
import {
  FileCheck2,
  ShieldCheck,
  Lock,
  Download,
  MessageSquare,
  Clock,
  User,
  CheckCircle2,
  ShieldAlert,
  FileCode,
  Check,
  Copy
} from "lucide-react";
import { DataContract } from "@/types/chat";

interface DataContractGovernanceProps {
  domainId: string;
  contract: DataContract | null;
}

export default function DataContractGovernance({
  domainId,
  contract,
}: DataContractGovernanceProps) {
  const [copied, setCopied] = useState(false);

  if (!contract) {
    return (
      <div className="p-8 text-center text-xs text-[var(--text-muted)]">
        Chưa có thông tin Data Contract cho domain này.
      </div>
    );
  }

  const piiFields = contract.pii_governance?.columns || [];

  const handleExportJson = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(contract, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `data_contract_${domainId}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handleCopyYaml = () => {
    const yamlText = `# Data Mesh Contract: ${domainId}
domain: ${domainId}
owner: "${contract.owner}"
data_steward: "${contract.data_steward}"
slack_channel: "${contract.slack_channel}"
sla:
  freshness: "${contract.SLA.freshness}"
  availability: "${contract.SLA.availability || "99.98%"}"
  latency_p95: "${contract.SLA.query_latency_p95 || "< 1.5s"}"
guaranteed_tables:
${(contract.tables_guaranteed || []).map((t) => `  - ${t}`).join("\n")}
guaranteed_metrics:
${(contract.metrics_guaranteed || []).map((m) => `  - ${m}`).join("\n")}
pii_governance:
  encryption: "AES-256"
  total_pii_fields: ${piiFields.length}
`;
    navigator.clipboard.writeText(yamlText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Top Banner */}
      <div className="p-6 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center flex-shrink-0">
            <FileCheck2 className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-[var(--text-primary)]">
                Enterprise Data Contract & Compliance
              </h3>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                Hiệu Lực
              </span>
            </div>
            <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-xl">
              Cam kết chất lượng dữ liệu giữa Producer (Data Engineering) và Consumer (AI Agent / BI Analysts) theo chuẩn Data Mesh.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleCopyYaml}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-[var(--bg-app)] hover:bg-[var(--border-subtle)] border border-[var(--border-subtle)] text-xs font-semibold text-[var(--text-primary)] transition-colors"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? "Đã sao chép YAML" : "Sao chép YAML"}</span>
          </button>
          <button
            onClick={handleExportJson}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white text-xs font-semibold transition-colors shadow-xs"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Tải Contract (JSON)</span>
          </button>
        </div>
      </div>

      {/* Stakeholders & SLA Specs Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Ownership Card */}
        <div className="p-5 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col gap-4">
          <div className="flex items-center justify-between pb-3 border-b border-[var(--border-subtle)]">
            <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-2">
              <User className="w-4 h-4 text-purple-500" />
              Chủ Thể Quản Trị (Ownership & Stewards)
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] flex flex-col gap-1">
              <span className="text-[11px] text-[var(--text-muted)]">Data Owner</span>
              <span className="font-semibold text-[var(--text-primary)]">
                {contract.owner}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] flex flex-col gap-1">
              <span className="text-[11px] text-[var(--text-muted)]">Data Steward</span>
              <span className="font-semibold text-[var(--text-primary)]">
                {contract.data_steward}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] flex flex-col gap-1 col-span-2">
              <span className="text-[11px] text-[var(--text-muted)]">Kênh Trực Vận Hành & Khẩn Cấp</span>
              <span className="font-semibold text-[var(--text-primary)] flex items-center gap-2">
                <MessageSquare className="w-3.5 h-3.5 text-blue-500" />
                {contract.slack_channel}
              </span>
            </div>
          </div>
        </div>

        {/* SLA Commitments */}
        <div className="p-5 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col gap-4">
          <div className="flex items-center justify-between pb-3 border-b border-[var(--border-subtle)]">
            <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-2">
              <Clock className="w-4 h-4 text-emerald-500" />
              Cam Kết Dịch Vụ (SLA Commitments)
            </span>
            <span className="text-[11px] font-mono text-emerald-500 font-bold">
              99.98% Uptime
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] flex flex-col gap-1">
              <span className="text-[11px] text-[var(--text-muted)]">Freshness SLA</span>
              <span className="font-semibold text-[var(--text-primary)]">
                {contract.SLA.freshness}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] flex flex-col gap-1">
              <span className="text-[11px] text-[var(--text-muted)]">Độ Sẵn Sàng (Availability)</span>
              <span className="font-semibold text-[var(--text-primary)]">
                {contract.SLA.availability || "99.98%"}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] flex flex-col gap-1">
              <span className="text-[11px] text-[var(--text-muted)]">Query Latency (P95)</span>
              <span className="font-semibold text-[var(--text-primary)]">
                {contract.SLA.query_latency_p95 || "< 1.5s"}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-[var(--bg-app)] border border-[var(--border-subtle)] flex flex-col gap-1">
              <span className="text-[11px] text-[var(--text-muted)]">Phản Hồi Sự Cố</span>
              <span className="font-semibold text-[var(--text-primary)]">
                {contract.SLA.incident_response_time || "< 30 phút"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* PII & Data Privacy Inventory */}
      <div className="p-5 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col gap-4">
        <div className="flex items-center justify-between pb-3 border-b border-[var(--border-subtle)]">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-2">
              <Lock className="w-4 h-4 text-rose-500" />
              Bảo Mật Dữ Liệu & Danh Mục PII (Data Privacy & Masking)
            </span>
            <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
              Tất cả trường dữ liệu nhạy cảm được gắn thẻ bảo mật và tự động che giấu (redaction) đối với truy vấn người dùng cuối.
            </p>
          </div>
          <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
            {piiFields.length} Trường PII
          </span>
        </div>

        {piiFields.length === 0 ? (
          <div className="text-xs text-[var(--text-muted)] italic py-2">
            Không phát hiện trường thông tin nhạy cảm PII trong domain này.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[var(--border-subtle)] text-[10px] uppercase font-bold text-[var(--text-muted)] tracking-wider">
                  <th className="pb-2 font-medium">Bảng</th>
                  <th className="pb-2 font-medium">Tên Cột</th>
                  <th className="pb-2 font-medium">Phân Loại Dữ Liệu</th>
                  <th className="pb-2 font-medium">Chính Sách Che Giấu (Masking Policy)</th>
                  <th className="pb-2 font-medium text-right">Mã Hóa Lưu Trữ</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)]">
                {piiFields.map((field, idx) => (
                  <tr key={idx} className="hover:bg-[var(--bg-app)]/50 transition-colors">
                    <td className="py-2.5 font-mono font-semibold text-[var(--text-primary)]">
                      {field.table}
                    </td>
                    <td className="py-2.5 font-mono font-bold text-rose-600 dark:text-rose-400">
                      {field.column}
                    </td>
                    <td className="py-2.5 font-medium text-[var(--text-secondary)]">
                      {field.classification}
                    </td>
                    <td className="py-2.5 text-[var(--text-muted)] font-mono text-[11px]">
                      {field.masking_policy}
                    </td>
                    <td className="py-2.5 text-right font-mono text-[11px] text-emerald-500 font-semibold">
                      AES-256 Encrypted
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Guaranteed Tables & Metrics Checklist */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Tables */}
        <div className="p-5 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col gap-3">
          <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
            Danh Mục Bảng Được Bảo Đảm Schema ({contract.tables_guaranteed?.length || 0})
          </span>
          <div className="flex flex-wrap gap-2">
            {(contract.tables_guaranteed || []).map((t) => (
              <span
                key={t}
                className="px-2.5 py-1 rounded-lg bg-[var(--bg-app)] border border-[var(--border-subtle)] text-xs font-mono font-medium text-[var(--text-primary)] flex items-center gap-1.5"
              >
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                {t}
              </span>
            ))}
          </div>
        </div>

        {/* Metrics */}
        <div className="p-5 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xs flex flex-col gap-3">
          <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
            Danh Mục Chỉ Số Được Cam Kết Tính Toán ({contract.metrics_guaranteed?.length || 0})
          </span>
          <div className="flex flex-wrap gap-2">
            {(contract.metrics_guaranteed || []).map((m) => (
              <span
                key={m}
                className="px-2.5 py-1 rounded-lg bg-[var(--bg-app)] border border-[var(--border-subtle)] text-xs font-mono font-medium text-[var(--text-primary)] flex items-center gap-1.5"
              >
                <CheckCircle2 className="w-3.5 h-3.5 text-purple-500" />
                {m}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
