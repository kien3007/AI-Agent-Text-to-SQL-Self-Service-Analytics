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
    <div className="max-w-2xl w-full mx-auto my-auto flex flex-col items-center text-center py-10 px-4 animate-in fade-in duration-300">
      <div className="w-12 h-12 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] flex items-center justify-center text-[var(--accent-primary)] mb-5 shadow-sm">
        <Sparkles className="w-6 h-6" />
      </div>

      <h1 className="text-3xl font-bold tracking-tight text-[var(--text-primary)] mb-2">
        What would you like to analyze?
      </h1>
      <p className="text-sm text-[var(--text-secondary)] mb-8 max-w-lg leading-relaxed">
        Hệ thống phân tích dữ liệu tự phục vụ với Multi-Agent LangGraph. Nhập câu hỏi phân tích bằng ngôn ngữ tự nhiên để bắt đầu.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full text-left">
        {CAPABILITIES.map((cap, index) => {
          const IconComp = cap.icon;
          return (
            <div
              key={index}
              className="p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] flex items-start gap-3 shadow-xs"
            >
              <div className="w-8 h-8 rounded-lg bg-[var(--bg-app)] border border-[var(--border-subtle)] flex items-center justify-center text-[var(--accent-primary)] flex-shrink-0 mt-0.5">
                <IconComp className="w-4 h-4" />
              </div>
              <div className="flex flex-col">
                <span className="text-xs font-semibold text-[var(--text-primary)]">
                  {cap.title}
                </span>
                <span className="text-[11px] text-[var(--text-muted)] mt-0.5 leading-snug">
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
