"use client";

import React from "react";
import {
  Sparkles,
  ChevronDown,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  MessageSquare,
  Layers,
  GitMerge,
  Award,
  Trash2,
  History,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ChatSession } from "@/types/chat";

export type SidebarTab = "chat" | "catalog" | "lineage" | "benchmark";

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  onNewChat: () => void;
  onLogout: () => void;
  activeDomain?: string;
  activeTab: SidebarTab;
  onSelectTab: (tab: SidebarTab) => void;
  sessions?: ChatSession[];
  currentSessionId?: string;
  onSelectSession?: (id: string) => void;
  onDeleteSession?: (id: string) => void;
  onClearAllSessions?: () => void;
  onOpenCatalog?: () => void;
  onOpenLineage?: () => void;
  onOpenBenchmark?: () => void;
}

export function Sidebar({
  collapsed,
  onToggleCollapse,
  onNewChat,
  onLogout,
  activeDomain,
  activeTab,
  onSelectTab,
  sessions = [],
  currentSessionId,
  onSelectSession,
  onDeleteSession,
  onClearAllSessions,
}: SidebarProps) {
  return (
    <aside
      className={cn(
        "h-full border-r border-[var(--border-subtle)] bg-[var(--bg-sidebar)] flex flex-col flex-shrink-0 transition-all duration-200 z-40 select-none",
        collapsed ? "w-16" : "w-64"
      )}
    >
      {/* Header */}
      <div className="p-3.5 flex items-center justify-between border-b border-[var(--border-subtle)] min-h-[56px]">
        {!collapsed ? (
          <div className="flex items-center gap-2.5 px-1 py-0.5 rounded-lg hover:bg-[var(--bg-sidebar-hover)] cursor-pointer">
            <div className="w-7 h-7 rounded-lg bg-[var(--accent-primary)] text-[var(--accent-primary-text)] flex items-center justify-center font-bold text-xs">
              <Sparkles className="w-3.5 h-3.5" />
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-semibold text-[var(--text-primary)] flex items-center gap-1">
                Sana Analytics <ChevronDown className="w-3 h-3 text-[var(--text-muted)]" />
              </span>
              <span className="text-[10px] text-[var(--text-muted)]">Enterprise Core</span>
            </div>
          </div>
        ) : (
          <div className="w-7 h-7 mx-auto rounded-lg bg-[var(--accent-primary)] text-[var(--accent-primary-text)] flex items-center justify-center font-bold text-xs">
            <Sparkles className="w-3.5 h-3.5" />
          </div>
        )}

        <button
          onClick={onToggleCollapse}
          title={collapsed ? "Mở rộng thanh bên" : "Thu gọn thanh bên"}
          className="p-1.5 rounded-md hover:bg-[var(--bg-sidebar-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          {collapsed ? <PanelLeftOpen className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
        </button>
      </div>

      {/* New Query Button */}
      <button
        onClick={() => {
          onNewChat();
          onSelectTab("chat");
        }}
        className={cn(
          "flex items-center gap-2.5 mx-3.5 my-3 py-2 px-3.5 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-card)] text-[var(--text-primary)] hover:bg-[var(--bg-card-hover)] hover:border-[var(--border-medium)] transition-all shadow-sm text-xs font-medium",
          collapsed && "justify-center px-0 mx-2"
        )}
      >
        <Plus className="w-4 h-4 text-[var(--accent-primary)]" />
        {!collapsed && <span>New query</span>}
      </button>

      {/* Nav links with Smooth Transitions */}
      <div className="px-2.5 flex flex-col gap-1">
        {[
          { id: "chat" as const, label: "Chat & Explore", icon: MessageSquare },
          { id: "catalog" as const, label: "Data Catalog", icon: Layers },
          { id: "lineage" as const, label: "Data Lineage", icon: GitMerge },
          { id: "benchmark" as const, label: "Benchmarks", icon: Award },
        ].map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={cn(
                "relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition-all duration-200 text-left w-full group",
                isActive
                  ? "bg-[var(--bg-card)] text-[var(--text-primary)] font-semibold shadow-xs border border-[var(--border-subtle)]"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-sidebar-hover)] border border-transparent"
              )}
            >
              {/* Active Indicator Bar */}
              {isActive && (
                <span className="absolute left-1.5 top-1/2 -translate-y-1/2 w-1 h-4 rounded-full bg-[var(--accent-primary)] animate-in fade-in zoom-in-75 duration-200" />
              )}
              <Icon
                className={cn(
                  "w-4 h-4 flex-shrink-0 transition-transform duration-200 group-hover:scale-105",
                  isActive
                    ? "text-[var(--accent-primary)]"
                    : "text-[var(--text-muted)] group-hover:text-[var(--text-primary)]"
                )}
              />
              {!collapsed && (
                <span className="truncate transition-colors">{item.label}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Scrollable Session History */}
      {!collapsed ? (
        <div className="flex-1 overflow-y-auto px-2.5 py-2 flex flex-col min-h-0">
          <div className="flex items-center justify-between px-3 py-1.5">
            <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              <History className="w-3 h-3 text-[var(--text-muted)]" />
              <span>Lịch Sử Phiên Hỏi</span>
              {sessions.length > 0 && (
                <span className="ml-1 text-[10px] px-1.5 py-0.2 rounded-full bg-[var(--pill-bg)] text-[var(--text-muted)] font-mono">
                  {sessions.length}
                </span>
              )}
            </div>
            {sessions.length > 0 && onClearAllSessions && (
              <button
                onClick={onClearAllSessions}
                className="text-[10px] text-[var(--text-muted)] hover:text-red-500 transition-colors"
                title="Xóa tất cả lịch sử"
              >
                Xóa hết
              </button>
            )}
          </div>

          <div className="flex-1 overflow-y-auto flex flex-col gap-1 pr-0.5 mt-1">
            {sessions.length === 0 ? (
              <div className="px-3 py-6 text-center rounded-lg border border-dashed border-[var(--border-subtle)] bg-[var(--bg-card)]/40 mx-1">
                <History className="w-4 h-4 mx-auto text-[var(--text-muted)] opacity-50 mb-1.5" />
                <p className="text-[11px] font-medium text-[var(--text-secondary)]">
                  Chưa có lịch sử
                </p>
                <p className="text-[10px] text-[var(--text-muted)] mt-0.5 leading-snug">
                  Mỗi câu hỏi phân tích của bạn sẽ được lưu thành một phiên làm việc tại đây.
                </p>
              </div>
            ) : (
              sessions.map((session) => {
                const isActive = session.id === currentSessionId;
                return (
                  <div
                    key={session.id}
                    onClick={() => {
                      onSelectSession?.(session.id);
                      onSelectTab("chat");
                    }}
                    className={cn(
                      "group relative flex items-center justify-between px-2.5 py-2 rounded-lg text-xs cursor-pointer transition-all",
                      isActive
                        ? "bg-[var(--bg-card-hover)] text-[var(--text-primary)] font-medium border border-[var(--border-subtle)] shadow-xs"
                        : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-sidebar-hover)]"
                    )}
                    title={session.title}
                  >
                    <div className="flex items-center gap-2 min-w-0 flex-1 mr-1">
                      <MessageSquare
                        className={cn(
                          "w-3.5 h-3.5 flex-shrink-0 transition-colors",
                          isActive
                            ? "text-[var(--accent-primary)]"
                            : "text-[var(--text-muted)] group-hover:text-[var(--text-secondary)]"
                        )}
                      />
                      <span className="truncate text-xs leading-tight">
                        {session.title || "Phiên phân tích mới"}
                      </span>
                    </div>

                    {onDeleteSession && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteSession(session.id);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-[var(--bg-card)] text-[var(--text-muted)] hover:text-red-500 transition-all flex-shrink-0"
                        title="Xóa phiên này"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      ) : (
        /* Collapsed View: compact history indicator */
        <div className="flex-1 flex flex-col items-center py-4">
          <div
            onClick={onToggleCollapse}
            className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-sidebar-hover)] cursor-pointer transition-colors relative"
            title={`Lịch sử phiên hỏi (${sessions.length})`}
          >
            <History className="w-4 h-4" />
            {sessions.length > 0 && (
              <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-[var(--accent-primary)]" />
            )}
          </div>
        </div>
      )}

      {/* Footer Info & Profile */}
      <div className="p-3 border-t border-[var(--border-subtle)] mt-auto flex flex-col gap-2.5">
        {!collapsed && (
          <div className="p-2.5 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] flex flex-col gap-1.5">
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full bg-[var(--accent-emerald)] shadow-sm animate-pulse" />
              <span className="text-[11px] font-semibold text-[var(--text-primary)]">Multi-Agent Engine</span>
            </div>
            <p className="text-[10px] text-[var(--text-muted)] leading-tight">
              Apache Doris 2.0 OLAP & 5-Tier Zero-Blindness Guardrail.
            </p>
          </div>
        )}

        <div className="flex items-center justify-between p-1 rounded-lg hover:bg-[var(--bg-sidebar-hover)]">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-[var(--pill-bg)] border border-[var(--border-subtle)] flex items-center justify-center text-[11px] font-bold text-[var(--text-primary)]">
              AS
            </div>
            {!collapsed && (
              <div className="flex flex-col">
                <span className="text-xs font-medium text-[var(--text-primary)]">Alex Smith</span>
                <span className="text-[10px] text-[var(--text-muted)]">Enterprise Analyst</span>
              </div>
            )}
          </div>
          <button
            onClick={onLogout}
            title="Đăng xuất"
            className="p-1 rounded-md text-[var(--text-muted)] hover:text-[var(--accent-rose)] transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
}
