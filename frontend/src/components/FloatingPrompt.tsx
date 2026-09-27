"use client";

import React, { useRef, useEffect } from "react";
import { Zap, ArrowUp, Database } from "lucide-react";

interface FloatingPromptProps {
  query: string;
  onChangeQuery: (val: string) => void;
  onSend: () => void;
  disabled: boolean;
  isStreaming: boolean;
  onToggleStreaming: (val: boolean) => void;
  onOpenSources: () => void;
}

export function FloatingPrompt({
  query,
  onChangeQuery,
  onSend,
  disabled,
  isStreaming,
  onToggleStreaming,
  onOpenSources,
}: FloatingPromptProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && query.trim()) {
        onSend();
      }
    }
  };

  return (
    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 w-[calc(100%-48px)] max-w-2xl z-35 flex flex-col gap-2">
      <div className="bg-[var(--bg-card)] border border-[var(--border-medium)] rounded-3xl p-2.5 px-4 shadow-[var(--shadow-float)] flex flex-col gap-1.5 backdrop-blur-md focus-within:border-[var(--border-focus)] focus-within:bg-[var(--bg-input-focus)] transition-all">
        <div className="flex items-center gap-3">
          <Zap className="w-4 h-4 text-[var(--text-muted)] flex-shrink-0" />
          <textarea
            ref={textareaRef}
            value={query}
            onChange={(e) => onChangeQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="What would you like to analyze? (Hỏi về doanh thu, giá bán, top quận...)"
            rows={1}
            disabled={disabled}
            className="flex-1 bg-transparent border-none outline-none text-sm leading-normal text-[var(--text-primary)] placeholder-[var(--text-muted)] resize-none max-h-32 py-0.5"
          />
          <button
            onClick={onSend}
            disabled={disabled || !query.trim()}
            title="Gửi câu hỏi"
            className="w-8 h-8 rounded-full bg-[var(--accent-primary)] text-[var(--accent-primary-text)] flex items-center justify-center flex-shrink-0 disabled:opacity-35 disabled:cursor-not-allowed hover:scale-105 active:scale-95 transition-all"
          >
            <ArrowUp className="w-4 h-4 stroke-[2.5]" />
          </button>
        </div>

        <div className="flex items-center justify-between pt-0.5 text-xs text-[var(--text-muted)]">
          <div className="flex items-center gap-3">
            <button
              onClick={onOpenSources}
              className="inline-flex items-center gap-1.5 text-[11px] font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card-hover)] px-1.5 py-0.5 rounded transition-colors"
            >
              <Database className="w-3 h-3" />
              <span>Sources: 4 Tables</span>
            </button>

            <label className="flex items-center gap-1.5 text-[11px] cursor-pointer">
              <input
                type="checkbox"
                checked={isStreaming}
                onChange={(e) => onToggleStreaming(e.target.checked)}
                className="rounded accent-[var(--accent-primary)] cursor-pointer"
              />
              <span>Streaming</span>
            </label>
          </div>
        </div>
      </div>

      <div className="text-[11px] text-[var(--text-muted)] text-center">
        Sana Analytics can make mistakes. Verify critical business numbers with primary data sources.
      </div>
    </div>
  );
}
