"use client";

import React from "react";
import { Sparkles, Zap, ShieldCheck, BarChart3, Database } from "lucide-react";

interface WelcomeHeroProps {
  onSelectPrompt?: (query: string) => void;
}

const CAPABILITIES = [
  {
    icon: Zap,
    title: "Apache Doris OLAP",
    desc: "Truy vấn phân tích dữ liệu siêu tốc trên hàng triệu bản ghi",
  },
  {
    icon: ShieldCheck,
    title: "5-Tier Guardrails",
    desc: "Kiểm soát an toàn dữ liệu, chống SQL Injection & Hallucination",
  },
  {
    icon: BarChart3,
    title: "Auto-Visualization",
    desc: "Tự động trực quan hóa thành biểu đồ cột, tròn, đường & bảng dữ liệu",
  },
  {
    icon: Database,
    title: "Semantic Linking",
    desc: "Liên kết ngữ nghĩa chuẩn xác theo Business Catalog và Data Lineage",
  },
];

export function WelcomeHero({}: WelcomeHeroProps) {
  return (
    <div className="max-w-2xl w-full mx-auto flex flex-col items-center text-center py-2 sm:py-4 px-2 sm:px-4 animate-in fade-in duration-300">
      <div className="w-10 h-10 sm:w-11 sm:h-11 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] flex items-center justify-center text-[var(--accent-primary)] mb-3 shadow-xs">
        <Sparkles className="w-5 h-5 sm:w-5.5 sm:h-5.5" />
      </div>

      <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[var(--text-primary)] mb-1.5">
        What would you like to analyze?
      </h1>
      <p className="text-xs sm:text-sm text-[var(--text-secondary)] mb-4 max-w-md sm:max-w-lg leading-relaxed">
        Hệ thống phân tích dữ liệu tự phục vụ với Multi-Agent LangGraph. Nhập câu hỏi phân tích bằng ngôn ngữ tự nhiên để bắt đầu.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 sm:gap-3 w-full text-left">
        {CAPABILITIES.map((cap, index) => {
          const IconComp = cap.icon;
          return (
            <div
              key={index}
              className="p-3 sm:p-3.5 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] flex items-start gap-2.5 sm:gap-3 shadow-xs hover:border-[var(--border-medium)] transition-all"
            >
              <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-[var(--bg-app)] border border-[var(--border-subtle)] flex items-center justify-center text-[var(--accent-primary)] flex-shrink-0 mt-0.5">
                <IconComp className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              </div>
              <div className="flex flex-col min-w-0">
                <span className="text-xs font-semibold text-[var(--text-primary)] truncate">
                  {cap.title}
                </span>
                <span className="text-[11px] text-[var(--text-muted)] mt-0.5 leading-snug line-clamp-2">
                  {cap.desc}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
