"use client";

import React from "react";
import { useTheme } from "@/components/ThemeProvider";
import {
  Trash2,
  Moon,
  Sun,
} from "lucide-react";
import { DomainItem } from "@/types/chat";
import { DomainSelector } from "./DomainSelector";

interface TopbarProps {
  domains: DomainItem[];
  activeDomain: string;
  onSelectDomain: (domainId: string) => void;
  onClearChat: () => void;
}

export function Topbar({
  domains,
  activeDomain,
  onSelectDomain,
  onClearChat,
}: TopbarProps) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <header className="h-14 px-6 border-b border-[var(--border-subtle)] bg-[var(--bg-app)] flex items-center justify-between z-30 flex-shrink-0">
      <div className="flex items-center gap-3">
        <DomainSelector
          domains={domains}
          activeDomain={activeDomain}
          onSelectDomain={onSelectDomain}
        />
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onClearChat}
          className="w-8 h-8 rounded-full border border-[var(--border-subtle)] flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--bg-card)] hover:text-[var(--text-primary)] transition-all"
          title="Xóa lịch sử hội thoại"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>

        {mounted && (
          <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            className="w-8 h-8 rounded-full border border-[var(--border-subtle)] flex items-center justify-center text-[var(--text-secondary)] hover:bg-[var(--bg-card)] hover:text-[var(--text-primary)] transition-all"
            title="Chuyển chế độ Sáng / Tối"
          >
            {theme === "dark" ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
          </button>
        )}
      </div>
    </header>
  );
}
