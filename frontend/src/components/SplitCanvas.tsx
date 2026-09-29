'use client';

import React, { useState, useMemo } from 'react';
import {
  X,
  Download,
  Table as TableIcon,
  BarChart2,
  Code,
  Search,
  ExternalLink,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import { ChatResponse } from '@/types/chat';
import { normalizeData, formatCellValue, exportDataToCsv } from '@/lib/utils';
import ChartView from './ChartView';

interface SplitCanvasProps {
  isOpen: boolean;
  onClose: () => void;
  data: ChatResponse | null;
}

export default function SplitCanvas({ isOpen, onClose, data }: SplitCanvasProps) {
  const [activeTab, setActiveTab] = useState<'tbl' | 'viz' | 'sql'>('tbl');
  const [filterQuery, setFilterQuery] = useState('');

  const normalized = useMemo(() => {
    if (!data) return { columns: [], rows: [] };
    return normalizeData(data.column_names, data.query_result);
  }, [data]);

  const filteredRows = useMemo(() => {
    if (!filterQuery.trim()) return normalized.rows;
    const lower = filterQuery.toLowerCase();
    return normalized.rows.filter(r =>
      r.some(val => String(val ?? '').toLowerCase().includes(lower))
    );
  }, [normalized.rows, filterQuery]);

  if (!isOpen) return null;

  return (
    <aside
      className="fixed inset-y-0 right-0 z-40 w-full sm:w-[500px] md:w-[600px] lg:w-[680px] bg-white dark:bg-zinc-900 border-l border-zinc-200 dark:border-zinc-800 shadow-2xl flex flex-col transform transition-transform duration-300 ease-in-out"
      aria-label="Analytics Canvas"
    >
      {/* Canvas Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-200/80 dark:border-zinc-800/80 bg-zinc-50/50 dark:bg-zinc-900/50">
        <div>
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
            <span>Data & Insights Canvas</span>
          </h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
            {normalized.columns.length} Cột · {normalized.rows.length} Dòng dữ liệu Warehouse OLAP
          </p>
        </div>

        <div className="flex items-center gap-2">
          {normalized.rows.length > 0 && (
            <button
              onClick={() => exportDataToCsv(normalized.columns, normalized.rows, 'canvas_export')}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 text-zinc-700 dark:text-zinc-300 transition-colors"
              title="Xuất file CSV"
            >
              <Download size={13} />
              CSV
            </button>
          )}

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
            title="Đóng Canvas"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {/* Tabs Bar */}
      <div className="flex items-center justify-between px-5 py-2.5 border-b border-zinc-200/60 dark:border-zinc-800/60 bg-white dark:bg-zinc-900">
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setActiveTab('tbl')}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              activeTab === 'tbl'
                ? 'bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 font-semibold'
                : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-300'
            }`}
          >
            <TableIcon size={13} />
            Full Table
          </button>
          <button
            onClick={() => setActiveTab('viz')}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              activeTab === 'viz'
                ? 'bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 font-semibold'
                : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-300'
            }`}
          >
            <BarChart2 size={13} />
            Expanded Chart
          </button>
          <button
            onClick={() => setActiveTab('sql')}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              activeTab === 'sql'
                ? 'bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 font-semibold'
                : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-300'
            }`}
          >
            <Code size={13} />
            SQL & Plan
          </button>
        </div>

        {activeTab === 'tbl' && (
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-2.5 text-zinc-400" />
            <input
              type="text"
              placeholder="Lọc dữ liệu..."
              value={filterQuery}
              onChange={e => setFilterQuery(e.target.value)}
              className="pl-8 pr-3 py-1 text-xs rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800/60 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-1 focus:ring-blue-500 w-36 sm:w-44"
            />
          </div>
        )}
      </div>

      {/* Canvas Body */}
      <div className="flex-1 overflow-y-auto p-5">
        {activeTab === 'tbl' && (
          <div className="flex flex-col gap-2">
            <div className="text-xs text-zinc-500 dark:text-zinc-400 flex items-center justify-between">
              <span>Hiển thị {filteredRows.length} / {normalized.rows.length} dòng</span>
              {filterQuery && (
                <button
                  onClick={() => setFilterQuery('')}
                  className="text-blue-500 hover:underline"
                >
                  Xóa lọc
                </button>
              )}
            </div>

            {normalized.rows.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-center text-zinc-400 gap-3">
                <div className="w-12 h-12 rounded-2xl bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center text-zinc-500">
                  <TableIcon size={22} />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Chưa có bảng dữ liệu truy vấn</h4>
                  <p className="text-xs text-zinc-400 mt-1 max-w-xs leading-relaxed">
                    Hãy gửi một câu hỏi phân tích ở khung chat hoặc click vào một câu hỏi mẫu để hiển thị bảng dữ liệu và biểu đồ chi tiết tại đây.
                  </p>
                </div>
              </div>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800 shadow-xs max-h-[70vh]">
                <table className="w-full text-xs text-left border-collapse">
                  <thead className="sticky top-0 bg-zinc-100 dark:bg-zinc-800 z-10 border-b border-zinc-200 dark:border-zinc-700">
                    <tr>
                      {normalized.columns.map((col, idx) => (
                        <th
                          key={idx}
                          className="px-3.5 py-2.5 font-semibold text-zinc-700 dark:text-zinc-300 uppercase tracking-wider text-[11px]"
                        >
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200/40 dark:divide-zinc-800/40 bg-white dark:bg-zinc-900">
                    {filteredRows.map((row, rIdx) => (
                      <tr
                        key={rIdx}
                        className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors"
                      >
                        {row.map((val, cIdx) => (
                          <td
                            key={cIdx}
                            className="px-3.5 py-2.5 text-zinc-700 dark:text-zinc-300 font-mono text-[11px]"
                          >
                            {formatCellValue(val)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {activeTab === 'viz' && (
          <div className="flex flex-col gap-4">
            <div className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/50">
              <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
                Trực quan hóa dữ liệu Warehouse
              </h3>
              <ChartView
                columns={normalized.columns}
                rows={normalized.rows}
                config={data?.chart_config}
                height={420}
              />
            </div>
          </div>
        )}

        {activeTab === 'sql' && (
          <div className="flex flex-col gap-4">
            {/* Metadata Card */}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60">
                <div className="flex items-center gap-1.5 text-zinc-500 mb-1">
                  <ShieldCheck size={14} className="text-emerald-500" />
                  <span>5-Tier Guardrail</span>
                </div>
                <div className="font-semibold text-zinc-800 dark:text-zinc-200">
                  AST Validated & Passed
                </div>
              </div>

              <div className="p-3 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60">
                <div className="flex items-center gap-1.5 text-zinc-500 mb-1">
                  <Zap size={14} className="text-amber-500" />
                  <span>Warehouse Latency</span>
                </div>
                <div className="font-semibold text-zinc-800 dark:text-zinc-200">
                  {data?.execution_time_ms ? `${Math.round(data.execution_time_ms)}ms` : 'Cached / Fast'}
                </div>
              </div>
            </div>

            {/* SQL Block */}
            <div className="rounded-lg overflow-hidden border border-zinc-800 bg-zinc-950">
              <div className="px-4 py-2 border-b border-zinc-800 text-xs text-zinc-400 font-mono">
                DuckDB / Warehouse SQL
              </div>
              <pre className="p-4 text-xs font-mono text-zinc-200 overflow-x-auto leading-relaxed">
                <code>{data?.sql_query || '-- No SQL available'}</code>
              </pre>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
