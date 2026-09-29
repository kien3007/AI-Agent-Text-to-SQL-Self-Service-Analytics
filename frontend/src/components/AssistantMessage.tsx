'use client';

import React, { useState, useMemo, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ChevronDown,
  CheckCircle2,
  Loader2,
  Database,
  Zap,
  List,
  BarChart2,
  Table as TableIcon,
  Code,
  Download,
  Copy,
  Check,
  FileText,
  ThumbsUp,
  ThumbsDown,
  HelpCircle,
  AlertCircle
} from 'lucide-react';
import { ChatMessage } from '@/types/chat';
import { normalizeData, formatCellValue, formatStepName, exportDataToCsv } from '@/lib/utils';
import ChartView from './ChartView';

interface AssistantMessageProps {
  message: ChatMessage;
  onOpenSources: (domainId?: string) => void;
}

export default function AssistantMessage({
  message,
  onOpenSources,
}: AssistantMessageProps) {
  const [isReasoningOpen, setIsReasoningOpen] = useState<boolean>(Boolean(message.isStreaming));

  const data = message.data;
  const isStreaming = message.isStreaming;

  // Active SQL query from data or thought steps
  const activeSql = data?.sql_query || message.thoughtSteps?.find(s => s.sql_query)?.sql_query;
  const hasSql = Boolean(activeSql);

  // Normalized table & chart data
  const normalized = useMemo(() => {
    if (!data) return { columns: [], rows: [] };
    return normalizeData(data.column_names, data.query_result);
  }, [data]);

  const hasData = normalized.rows.length > 0;
  const [activeTab, setActiveTab] = useState<'viz' | 'tbl' | 'sql'>('viz');
  const [isCopied, setIsCopied] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);

  // Auto-switch to SQL tab if query has no table rows
  useEffect(() => {
    if (!hasData && hasSql) {
      setActiveTab('sql');
    } else if (hasData) {
      setActiveTab('viz');
    }
  }, [hasData, hasSql]);

  const handleCopyMarkdown = () => {
    const textToCopy = data?.final_response || message.content;
    navigator.clipboard.writeText(textToCopy);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const handleCopySql = () => {
    if (activeSql) {
      navigator.clipboard.writeText(activeSql);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    }
  };

  return (
    <div className="flex flex-col gap-3.5 w-full max-w-4xl py-2">
      {/* 1. Reasoning Accordion */}
      <div className="border border-zinc-200/80 dark:border-zinc-800/80 bg-zinc-50/60 dark:bg-zinc-900/40 rounded-xl overflow-hidden text-xs transition-all">
        <button
          onClick={() => setIsReasoningOpen(!isReasoningOpen)}
          className="w-full flex items-center justify-between px-3.5 py-2.5 hover:bg-zinc-100/50 dark:hover:bg-zinc-800/30 transition-colors"
        >
          <div className="flex items-center gap-2">
            {isStreaming ? (
              <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                Thinking...
              </div>
            ) : (
              <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-zinc-200/60 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 font-medium">
                <CheckCircle2 size={12} className="text-emerald-500" />
                <span>Done {message.durationSec ? `(${message.durationSec}s)` : ''}</span>
              </div>
            )}
          </div>
          <ChevronDown
            size={14}
            className={`text-zinc-400 transition-transform duration-200 ${
              isReasoningOpen ? 'rotate-180' : ''
            }`}
          />
        </button>

        {isReasoningOpen && (
          <div className="px-4 py-3 border-t border-zinc-200/60 dark:border-zinc-800/60 flex flex-col gap-2 bg-white/40 dark:bg-zinc-950/20">
            {message.thoughtSteps && message.thoughtSteps.length > 0 ? (
              message.thoughtSteps.map((step, idx) => (
                <div key={idx} className="flex items-center gap-2 text-zinc-600 dark:text-zinc-400">
                  <CheckCircle2 size={13} className="text-emerald-500 shrink-0" />
                  <span>
                    <strong className="text-zinc-800 dark:text-zinc-200 font-medium">
                      {formatStepName(step.step)}:
                    </strong>{' '}
                    Hoàn tất xử lý
                  </span>
                </div>
              ))
            ) : isStreaming ? (
              <div className="flex items-center gap-2 text-zinc-500 dark:text-zinc-400">
                <Loader2 size={13} className="animate-spin text-blue-500" />
                <span>Đang phân tích cấu trúc câu hỏi & liên kết Schema...</span>
              </div>
            ) : (
              <div className="text-zinc-500 dark:text-zinc-400">
                Truy vấn được xử lý trực tiếp qua tối ưu hóa bộ nhớ đệm hoặc pipeline nhanh.
              </div>
            )}
          </div>
        )}
      </div>

      {/* 2. Clarification Needed Warning */}
      {data?.clarification_needed && data?.clarification_question && (
        <div className="p-4 rounded-xl border border-amber-500/20 bg-amber-500/5 text-sm">
          <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 font-semibold mb-1">
            <HelpCircle size={16} />
            Cần thêm thông tin làm rõ
          </div>
          <p className="text-zinc-700 dark:text-zinc-300">{data.clarification_question}</p>
        </div>
      )}

      {/* 3. Source Badges Row */}
      {data && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-400">
          {data.metadata?.tables_linked?.map((tbl, idx) => (
            <span
              key={idx}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-zinc-100 dark:bg-zinc-800/80 border border-zinc-200/60 dark:border-zinc-700/60 font-mono text-[11px]"
            >
              <Database size={11} className="text-blue-500" />
              TABLE: {tbl}
            </span>
          ))}

          {data.execution_time_ms !== undefined && (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-zinc-100 dark:bg-zinc-800/80 border border-zinc-200/60 dark:border-zinc-700/60 text-[11px]">
              <Zap size={11} className="text-amber-500" />
              EXEC: {Math.round(data.execution_time_ms)}ms
            </span>
          )}

          {hasData && (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-zinc-100 dark:bg-zinc-800/80 border border-zinc-200/60 dark:border-zinc-700/60 text-[11px]">
              <List size={11} className="text-emerald-500" />
              ROWS: {normalized.rows.length}
            </span>
          )}
        </div>
      )}

      {/* 4. Natural Language Editorial Markdown */}
      <div className="prose prose-zinc dark:prose-invert max-w-none text-[15px] leading-relaxed">
        {data?.final_response ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {data.final_response}
          </ReactMarkdown>
        ) : message.content ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        ) : isStreaming ? (
          <div className="flex items-center gap-2 text-zinc-400 py-1">
            <Loader2 size={14} className="animate-spin text-zinc-500" />
            <span className="text-sm">Đang tổng hợp nhận định phân tích...</span>
          </div>
        ) : null}
      </div>

      {/* 5. Results Card (Chart, Table, SQL) */}
      {(hasData || hasSql) && (
        <div className="border border-zinc-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900 rounded-xl overflow-hidden shadow-sm mt-1">
          {/* Tab Navigation Bar */}
          <div className="flex items-center justify-between px-3.5 py-2 border-b border-zinc-200/60 dark:border-zinc-800/60 bg-zinc-50/50 dark:bg-zinc-900/50">
            <div className="flex items-center gap-1">
              {hasData && (
                <>
                  <button
                    onClick={() => setActiveTab('viz')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                      activeTab === 'viz'
                        ? 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 shadow-xs'
                        : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
                    }`}
                  >
                    <BarChart2 size={13} />
                    Biểu đồ
                  </button>
                  <button
                    onClick={() => setActiveTab('tbl')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                      activeTab === 'tbl'
                        ? 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 shadow-xs'
                        : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
                    }`}
                  >
                    <TableIcon size={13} />
                    Bảng dữ liệu
                  </button>
                </>
              )}
              {hasSql && (
                <button
                  onClick={() => setActiveTab('sql')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                    activeTab === 'sql' || !hasData
                      ? 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 shadow-xs'
                      : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
                  }`}
                >
                  <Code size={13} />
                  SQL Query
                </button>
              )}
            </div>

            {hasData && (
              <button
                onClick={() => exportDataToCsv(normalized.columns, normalized.rows, 'sana_query')}
                className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200/50 dark:hover:bg-zinc-800 transition-colors"
                title="Xuất file CSV"
              >
                <Download size={12} />
                CSV
              </button>
            )}
          </div>

          {/* Tab Content */}
          <div className="p-4">
            {activeTab === 'viz' && hasData && (
              <div className="w-full">
                <ChartView
                  columns={normalized.columns}
                  rows={normalized.rows}
                  config={data?.chart_config}
                  height={280}
                />
              </div>
            )}

            {activeTab === 'tbl' && hasData && (
              <div className="w-full">
                <div className="overflow-x-auto rounded-lg border border-zinc-200/60 dark:border-zinc-800/60">
                  <table className="w-full text-xs text-left border-collapse">
                    <thead>
                      <tr className="bg-zinc-100/70 dark:bg-zinc-800/50 border-b border-zinc-200/60 dark:border-zinc-800/60">
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
                    <tbody className="divide-y divide-zinc-200/40 dark:divide-zinc-800/40">
                      {normalized.rows.slice(0, 8).map((row, rIdx) => (
                        <tr
                          key={rIdx}
                          className="hover:bg-zinc-50/50 dark:hover:bg-zinc-800/30 transition-colors"
                        >
                          {row.map((val, cIdx) => (
                            <td
                              key={cIdx}
                              className="px-3.5 py-2 text-zinc-600 dark:text-zinc-400 font-mono text-[11px]"
                            >
                              {formatCellValue(val)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {normalized.rows.length > 8 && (
                  <div className="mt-2 text-center text-xs text-zinc-400 py-1.5 border-t border-zinc-100 dark:border-zinc-800">
                    Hiển thị 8/{normalized.rows.length} dòng dữ liệu phân tích.
                  </div>
                )}
              </div>
            )}

            {activeTab === 'sql' && hasSql && (
              <div className="flex flex-col gap-3">
                <div className="relative">
                  <div className="absolute right-2 top-2 z-10">
                    <button
                      onClick={handleCopySql}
                      className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-md bg-zinc-800 text-zinc-300 hover:bg-zinc-700 border border-zinc-700 transition-colors"
                    >
                      {isCopied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                      <span>{isCopied ? 'Copied' : 'Copy'}</span>
                    </button>
                  </div>
                  <pre className="p-4 rounded-lg bg-zinc-950 text-zinc-200 font-mono text-xs overflow-x-auto border border-zinc-800/80 leading-relaxed whitespace-pre-wrap">
                    <code>{activeSql}</code>
                  </pre>
                </div>
                {!hasData && (
                  <div className="p-3 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-800 text-xs text-zinc-500 dark:text-zinc-400 flex items-center gap-2">
                    <Database size={13} className="text-blue-500 shrink-0" />
                    <span>Data Warehouse đã thực thi thành công câu truy vấn. Không có bản ghi dữ liệu nào khớp với điều kiện lọc.</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 6. Sana AI Bottom Action Bar (Mobbin inspired) */}
      {!isStreaming && (data || hasSql) && (
        <div className="flex items-center justify-between pt-1">
          <div className="flex items-center gap-1.5">
            {hasSql && (
              <button
                onClick={() => setActiveTab('sql')}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  activeTab === 'sql'
                    ? 'bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 border border-zinc-900 dark:border-zinc-100 font-semibold'
                    : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800/80 border border-zinc-200/60 dark:border-zinc-800'
                }`}
                title="Xem câu lệnh SQL Query"
              >
                <Code size={12} />
                SQL Query
              </button>
            )}

            <button
              onClick={() => onOpenSources(data?.domain_id)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800/80 border border-zinc-200/60 dark:border-zinc-800 transition-colors"
            >
              <FileText size={12} />
              Sources
            </button>


          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={handleCopyMarkdown}
              className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
              title="Sao chép câu trả lời"
            >
              {isCopied ? <Check size={14} className="text-emerald-500" /> : <Copy size={14} />}
            </button>
            <button
              onClick={() => setFeedback(feedback === 'up' ? null : 'up')}
              className={`p-1.5 rounded-md transition-colors ${
                feedback === 'up'
                  ? 'text-emerald-500 bg-emerald-500/10'
                  : 'text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800'
              }`}
              title="Hữu ích"
            >
              <ThumbsUp size={14} />
            </button>
            <button
              onClick={() => setFeedback(feedback === 'down' ? null : 'down')}
              className={`p-1.5 rounded-md transition-colors ${
                feedback === 'down'
                  ? 'text-rose-500 bg-rose-500/10'
                  : 'text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800'
              }`}
              title="Chưa chính xác"
            >
              <ThumbsDown size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
