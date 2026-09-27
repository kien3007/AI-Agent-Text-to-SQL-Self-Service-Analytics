'use client';

import React, { useEffect, useState } from 'react';
import { X, GitMerge, FileCheck2, Clock, Users, MessageSquare, ArrowRight, Loader2 } from 'lucide-react';
import { DataContract, IngestionLineage } from '@/types/chat';

interface LineageModalProps {
  isOpen: boolean;
  domainId: string;
  onClose: () => void;
}

export default function LineageModal({ isOpen, domainId, onClose }: LineageModalProps) {
  const [loading, setLoading] = useState(false);
  const [contract, setContract] = useState<DataContract | null>(null);
  const [lineage, setLineage] = useState<IngestionLineage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !domainId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    Promise.all([
      fetch(`/api/domains/${domainId}/contract`).then(res => (res.ok ? res.json() : null)),
      fetch(`/api/domains/${domainId}/lineage`).then(res => (res.ok ? res.json() : null)),
    ])
      .then(([contractData, lineageData]) => {
        if (!isMounted) return;
        setContract(contractData);
        if (lineageData && lineageData.lineage) {
          setLineage(lineageData.lineage);
        }
      })
      .catch(err => {
        if (isMounted) setError(err.message);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, domainId]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div className="w-full max-w-xl rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 dark:border-zinc-800">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center">
              <GitMerge size={18} />
            </div>
            <div>
              <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
                Data Lineage & Governance Contract
              </h3>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                Theo dõi nguồn gốc nạp dữ liệu và cam kết SLA cho domain <code className="font-mono text-zinc-700 dark:text-zinc-300">{domainId}</code>
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 flex flex-col gap-5 overflow-y-auto max-h-[75vh]">
          {loading && (
            <div className="flex flex-col items-center justify-center py-12 text-zinc-400 gap-2">
              <Loader2 size={24} className="animate-spin text-purple-500" />
              <p className="text-xs">Đang nạp thông tin lineage và data contract...</p>
            </div>
          )}

          {error && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs">
              {error}
            </div>
          )}

          {!loading && (
            <>
              {/* Data Contract */}
              <div className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/50">
                <div className="flex items-center gap-2 mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                  <FileCheck2 size={15} className="text-emerald-500" />
                  <span>Data Contract SLA</span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="flex flex-col gap-0.5">
                    <span className="text-zinc-400 text-[11px]">Data Owner</span>
                    <span className="font-medium text-zinc-800 dark:text-zinc-200">
                      {contract?.owner || 'Data Engineering Team'}
                    </span>
                  </div>

                  <div className="flex flex-col gap-0.5">
                    <span className="text-zinc-400 text-[11px]">Data Steward</span>
                    <span className="font-medium text-zinc-800 dark:text-zinc-200">
                      {contract?.data_steward || 'Analytics Steward'}
                    </span>
                  </div>

                  <div className="flex flex-col gap-0.5">
                    <span className="text-zinc-400 text-[11px]">Slack Channel</span>
                    <span className="font-medium text-zinc-800 dark:text-zinc-200 flex items-center gap-1">
                      <MessageSquare size={11} className="text-blue-500" />
                      {contract?.slack_channel || '#data-ops'}
                    </span>
                  </div>

                  <div className="flex flex-col gap-0.5">
                    <span className="text-zinc-400 text-[11px]">Freshness SLA</span>
                    <span className="font-medium text-zinc-800 dark:text-zinc-200 flex items-center gap-1">
                      <Clock size={11} className="text-amber-500" />
                      {contract?.SLA?.freshness || '12h'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Ingestion Lineage */}
              <div className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/50">
                <div className="flex items-center gap-2 mb-4 text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                  <GitMerge size={15} className="text-purple-500" />
                  <span>Pipeline Lineage</span>
                </div>

                <div className="flex items-center justify-between p-3.5 rounded-lg bg-white dark:bg-zinc-800/60 border border-zinc-200/60 dark:border-zinc-700/60 mb-3">
                  <div className="text-xs font-mono font-medium text-zinc-700 dark:text-zinc-300">
                    {lineage?.source || 'raw_crawler_source'}
                  </div>
                  <ArrowRight size={14} className="text-zinc-400" />
                  <div className="text-xs font-mono font-semibold text-blue-600 dark:text-blue-400">
                    {lineage?.destination || 'fct_doris_olap'}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-zinc-400 text-[11px] block">Tổng số bản ghi nạp</span>
                    <span className="font-medium text-zinc-800 dark:text-zinc-200 font-mono">
                      {(lineage?.total_records || 32000).toLocaleString('vi-VN')} rows
                    </span>
                  </div>
                  <div>
                    <span className="text-zinc-400 text-[11px] block">Thời gian nạp gần nhất</span>
                    <span className="font-medium text-zinc-800 dark:text-zinc-200">
                      {lineage?.ingestion_time
                        ? new Date(lineage.ingestion_time).toLocaleString('vi-VN')
                        : 'Vừa xong'}
                    </span>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
