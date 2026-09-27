'use client';

import React, { useEffect, useState } from 'react';
import { X, BookOpen, Database, BarChart3, Columns, Loader2, Sparkles } from 'lucide-react';
import { DomainDetails } from '@/types/chat';

interface CatalogModalProps {
  isOpen: boolean;
  domainId: string;
  onClose: () => void;
  onSelectMetric: (metricName: string) => void;
}

export default function CatalogModal({
  isOpen,
  domainId,
  onClose,
  onSelectMetric,
}: CatalogModalProps) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<DomainDetails | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !domainId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    fetch(`/api/domains/${domainId}`)
      .then(res => {
        if (!res.ok) throw new Error('Không thể tải dữ liệu Data Catalog.');
        return res.json();
      })
      .then(json => {
        if (isMounted) setData(json);
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
      <div className="w-full max-w-2xl max-h-[85vh] rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-2xl flex flex-col overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 dark:border-zinc-800">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center">
              <BookOpen size={18} />
            </div>
            <div>
              <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
                Enterprise Data Catalog
              </h3>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                Semantic Layer, Metrics & Schema cho Domain: <code className="font-mono text-zinc-700 dark:text-zinc-300">{domainId}</code>
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

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6">
          {loading && (
            <div className="flex flex-col items-center justify-center py-16 text-zinc-400 gap-2">
              <Loader2 size={24} className="animate-spin text-blue-500" />
              <p className="text-xs">Đang tải cấu trúc dữ liệu catalog...</p>
            </div>
          )}

          {error && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs">
              {error}
            </div>
          )}

          {!loading && data && (
            <>
              {/* Domain Description */}
              <div className="p-4 rounded-xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-800">
                <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-1">
                  {data.domain_name}
                </h4>
                <p className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">
                  {data.description}
                </p>
              </div>

              {/* Metrics Section */}
              <div>
                <div className="flex items-center gap-1.5 mb-3">
                  <BarChart3 size={15} className="text-blue-500" />
                  <h5 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    Chỉ số Nghiệp vụ (Semantic Metrics)
                  </h5>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {data.metrics?.map((m, idx) => (
                    <button
                      key={idx}
                      onClick={() => onSelectMetric(m.name || m.label || m.metric_id || '')}
                      className="text-left p-3 rounded-xl border border-zinc-200 dark:border-zinc-800 hover:border-blue-500/40 hover:bg-blue-50/30 dark:hover:bg-blue-900/10 transition-colors group flex flex-col gap-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 group-hover:text-blue-600 dark:group-hover:text-blue-400">
                          {m.name || m.label || m.metric_id}
                        </span>
                        <Sparkles size={12} className="text-zinc-400 group-hover:text-blue-500" />
                      </div>
                      <p className="text-[11px] text-zinc-500 dark:text-zinc-400 line-clamp-2">
                        {m.description || m.sql_expression}
                      </p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Tables Section */}
              <div>
                <div className="flex items-center gap-1.5 mb-3">
                  <Database size={15} className="text-emerald-500" />
                  <h5 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    Bảng & Cột Doris OLAP
                  </h5>
                </div>

                <div className="flex flex-col gap-3">
                  {data.tables?.map((t, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900"
                    >
                      <div className="flex items-center gap-2 mb-2 font-mono text-xs font-semibold text-zinc-800 dark:text-zinc-200">
                        <span className="w-2 h-2 rounded-full bg-emerald-500" />
                        {t.table_name || t.name}
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {t.columns?.map((c, cIdx) => (
                          <span
                            key={cIdx}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-zinc-100 dark:bg-zinc-800 text-[11px] font-mono text-zinc-600 dark:text-zinc-400"
                          >
                            <Columns size={10} className="text-zinc-400" />
                            {c.name}
                            {c.data_type && (
                              <span className="text-[10px] text-zinc-400 dark:text-zinc-500">
                                ({c.data_type})
                              </span>
                            )}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
