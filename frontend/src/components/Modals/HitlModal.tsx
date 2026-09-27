'use client';

import React, { useState } from 'react';
import { AlertTriangle, ShieldAlert, Check, Copy, CheckCircle2, XCircle, Loader2 } from 'lucide-react';

interface HitlModalProps {
  isOpen: boolean;
  sessionId: string | null;
  sqlQuery: string | null;
  warningText: string | null;
  onDecision: (approved: boolean) => Promise<void>;
}

export default function HitlModal({
  isOpen,
  sessionId,
  sqlQuery,
  warningText,
  onDecision,
}: HitlModalProps) {
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const handleCopy = () => {
    if (sqlQuery) {
      navigator.clipboard.writeText(sqlQuery);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleAction = async (approved: boolean) => {
    setLoading(true);
    try {
      await onDecision(approved);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div className="w-full max-w-lg rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-2xl p-6 overflow-hidden">
        <div className="flex items-start gap-3.5 mb-4">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0">
            <ShieldAlert size={20} />
          </div>
          <div>
            <h3 className="text-base font-bold text-zinc-900 dark:text-zinc-100">
              Yêu cầu Phê duyệt Con người (HITL Gate)
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
              Hệ thống phát hiện truy vấn có mức độ phức tạp cao hoặc tiềm ẩn chi phí quét tài nguyên lớn trên Doris OLAP.
            </p>
          </div>
        </div>

        {/* Warning text */}
        <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-800 dark:text-amber-300 mb-4 flex items-start gap-2">
          <AlertTriangle size={15} className="shrink-0 mt-0.5" />
          <span>{warningText || 'Truy vấn vượt ngưỡng chi phí quét tài nguyên mặc định.'}</span>
        </div>

        {/* SQL Code Box */}
        <div className="mb-5">
          <div className="flex items-center justify-between mb-1.5 text-xs text-zinc-500 dark:text-zinc-400 font-medium">
            <span>Doris SQL được sinh:</span>
            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-1 text-[11px] text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
            >
              {copied ? <Check size={11} className="text-emerald-500" /> : <Copy size={11} />}
              <span>{copied ? 'Đã sao chép' : 'Sao chép'}</span>
            </button>
          </div>
          <pre className="p-3.5 rounded-xl bg-zinc-950 text-zinc-200 font-mono text-xs max-h-48 overflow-y-auto border border-zinc-800 leading-relaxed">
            <code>{sqlQuery || '-- Không có nội dung SQL'}</code>
          </pre>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-zinc-200 dark:border-zinc-800">
          <button
            onClick={() => handleAction(false)}
            disabled={loading}
            className="px-4 py-2 text-xs font-semibold rounded-xl text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors flex items-center gap-1.5"
          >
            <XCircle size={14} className="text-zinc-400" />
            <span>Từ chối & Hủy</span>
          </button>

          <button
            onClick={() => handleAction(true)}
            disabled={loading}
            className="px-4 py-2 text-xs font-semibold rounded-xl bg-amber-600 hover:bg-amber-700 text-white transition-colors flex items-center gap-1.5 shadow-sm"
          >
            {loading ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <CheckCircle2 size={14} />
            )}
            <span>Phê duyệt & Thực thi</span>
          </button>
        </div>
      </div>
    </div>
  );
}
