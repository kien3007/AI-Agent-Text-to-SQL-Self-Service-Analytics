"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Building2,
  ShoppingBag,
  HeartPulse,
  Database,
  ChevronDown,
  Check,
  Sparkles,
} from "lucide-react";
import { DomainItem } from "@/types/chat";

interface DomainSelectorProps {
  domains: DomainItem[];
  activeDomain: string;
  onSelectDomain: (domainId: string) => void;
}

const DOMAIN_ICONS: Record<string, React.ReactNode> = {
  real_estate: <Building2 className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400" />,
  ecommerce: <ShoppingBag className="w-3.5 h-3.5 text-amber-500 dark:text-amber-400" />,
  healthcare: <HeartPulse className="w-3.5 h-3.5 text-rose-500 dark:text-rose-400" />,
};

const DOMAIN_BADGE_COLORS: Record<string, string> = {
  real_estate: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-500/20",
  ecommerce: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
  healthcare: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20",
};

export function DomainSelector({
  domains,
  activeDomain,
  onSelectDomain,
}: DomainSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Default fallback domains if list from API is empty
  const defaultDomains: DomainItem[] = [
    {
      domain_id: "real_estate",
      display_name: "Bất Động Sản Việt Nam",
      description: "Thị trường BĐS toàn quốc với hơn 3.5 triệu tin đăng.",
      tables_count: 1,
      metrics_count: 5,
    },
    {
      domain_id: "ecommerce",
      display_name: "Thương Mại Điện Tử",
      description: "Kinh doanh đa kênh, đơn hàng, GMV và tỷ lệ chuyển đổi.",
      tables_count: 5,
      metrics_count: 4,
    },
    {
      domain_id: "healthcare",
      display_name: "Y Tế & Bệnh Viện",
      description: "Quản lý hồ sơ bệnh nhân, lượt khám và viện phí.",
      tables_count: 5,
      metrics_count: 3,
    },
  ];

  const activeList = domains.length > 0 ? domains : defaultDomains;
  const currentDomain = activeList.find((d) => d.domain_id === activeDomain) || activeList[0];

  // Click outside to close
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  const handleSelect = (domainId: string) => {
    onSelectDomain(domainId);
    setIsOpen(false);
  };

  return (
    <div className="relative inline-block text-left" ref={dropdownRef}>
      {/* Trigger Button - Sana AI Aesthetic Pill */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`group h-8 px-3 rounded-full flex items-center gap-2 text-xs font-medium transition-all duration-200 border ${
          isOpen
            ? "bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 shadow-xs"
            : "bg-white/80 dark:bg-zinc-900/80 border-zinc-200/80 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 hover:border-zinc-300 dark:hover:border-zinc-700 hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
        }`}
        aria-haspopup="true"
        aria-expanded={isOpen}
      >
        {/* Pulsing Live Connection Indicator */}
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
        </span>

        {/* Domain Icon */}
        <span className="flex items-center justify-center">
          {DOMAIN_ICONS[currentDomain?.domain_id] || (
            <Database className="w-3.5 h-3.5 text-blue-500" />
          )}
        </span>

        {/* Domain Name */}
        <span className="font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
          {currentDomain?.display_name}
        </span>

        {/* Domain ID subtle badge */}
        <span className="hidden sm:inline-block px-1.5 py-0.2 rounded text-[10px] font-mono text-zinc-400 dark:text-zinc-500 bg-zinc-100 dark:bg-zinc-800">
          {currentDomain?.domain_id}
        </span>

        {/* Animated Chevron */}
        <ChevronDown
          className={`w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 transition-transform duration-200 group-hover:text-zinc-700 dark:group-hover:text-zinc-200 ${
            isOpen ? "rotate-180" : ""
          }`}
        />
      </button>

      {/* Popover Dropdown Menu */}
      {isOpen && (
        <div className="absolute left-0 top-full mt-2 w-80 z-50 rounded-2xl border border-zinc-200/90 dark:border-zinc-800/90 bg-white/95 dark:bg-zinc-900/95 backdrop-blur-xl shadow-2xl shadow-zinc-950/15 dark:shadow-black/70 p-1.5 animate-in fade-in-0 zoom-in-95 duration-150">
          {/* Header */}
          <div className="px-3 py-2 flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800/70 mb-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
              Chọn Kho Dữ Liệu (Domain)
            </span>
            <span className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full font-medium flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              OLAP Sẵn Sàng
            </span>
          </div>

          {/* Domain Options */}
          <div className="flex flex-col gap-1">
            {activeList.map((d) => {
              const isSelected = d.domain_id === activeDomain;
              return (
                <button
                  key={d.domain_id}
                  onClick={() => handleSelect(d.domain_id)}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl text-left transition-all duration-150 ${
                    isSelected
                      ? "bg-zinc-100/90 dark:bg-zinc-800/90 text-zinc-900 dark:text-zinc-100 shadow-xs"
                      : "hover:bg-zinc-50 dark:hover:bg-zinc-800/50 text-zinc-600 dark:text-zinc-400"
                  }`}
                >
                  {/* Icon box */}
                  <div
                    className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border transition-transform ${
                      isSelected
                        ? DOMAIN_BADGE_COLORS[d.domain_id] || "bg-blue-500/10 text-blue-500 border-blue-500/20"
                        : "bg-zinc-100/80 dark:bg-zinc-800/60 border-zinc-200/50 dark:border-zinc-700/40 text-zinc-500"
                    }`}
                  >
                    {DOMAIN_ICONS[d.domain_id] || <Database className="w-4 h-4" />}
                  </div>

                  {/* Title and ID badge */}
                  <div className="flex-1 min-w-0 flex items-center gap-2">
                    <span className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 truncate">
                      {d.display_name}
                    </span>
                    <span className="text-[10px] font-mono text-zinc-400 dark:text-zinc-500 bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">
                      {d.domain_id}
                    </span>
                  </div>

                  {/* Selected checkmark */}
                  {isSelected && (
                    <div className="shrink-0 text-emerald-500">
                      <Check className="w-4 h-4" />
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
