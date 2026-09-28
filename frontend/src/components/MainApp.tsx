'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Sidebar, SidebarTab } from '@/components/Sidebar';
import { Topbar } from '@/components/Topbar';
import { WelcomeHero } from '@/components/WelcomeHero';
import ChatViewport from '@/components/ChatViewport';
import { FloatingPrompt } from '@/components/FloatingPrompt';
import HitlModal from '@/components/Modals/HitlModal';
import CatalogView from '@/components/Views/CatalogView';
import LineageView from '@/components/Views/LineageView';
import BenchmarkView from '@/components/Views/BenchmarkView';
import { useChatStream } from '@/hooks/useChatStream';
import { useAuth } from '@/context/AuthContext';
import { DomainItem } from '@/types/chat';
import { Loader2, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';

interface MainAppProps {
  initialTab?: SidebarTab;
}

export default function MainApp({ initialTab = 'chat' }: MainAppProps) {
  const router = useRouter();
  const { isAuthenticated, isLoading, logout } = useAuth();

  const [activeTab, setActiveTab] = useState<SidebarTab>(initialTab);
  const [activeDomain, setActiveDomain] = useState<string>('real_estate');
  const [domains, setDomains] = useState<DomainItem[]>([]);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(false);
  const [inputQuery, setInputQuery] = useState<string>('');
  const [useStream, setUseStream] = useState<boolean>(true);

  const {
    sessions,
    sessionId,
    messages,
    isStreaming,
    pendingHitl,
    sendMessage,
    submitHitl,
    switchSession,
    deleteSession,
    clearAllSessions,
    newChat,
  } = useChatStream();

  // Route protection & initial load
  useEffect(() => {
    if (!isLoading) {
      if (!isAuthenticated) {
        router.replace('/login');
      } else {
        fetchDomains();
      }
    }

    const savedSidebar = localStorage.getItem('sana_sidebar');
    if (savedSidebar !== null) {
      setIsSidebarCollapsed(savedSidebar === 'true');
    }
  }, [isAuthenticated, isLoading, router]);

  const handleSelectTab = (tab: SidebarTab) => {
    setActiveTab(tab);
    if (typeof window !== 'undefined') {
      document.cookie = `sana_active_tab=${tab}; path=/; max-age=31536000; SameSite=Lax`;
      localStorage.setItem('sana_active_tab', tab);
      if (tab === 'chat') {
        window.history.replaceState(null, '', window.location.pathname);
      } else {
        window.history.replaceState(null, '', `#${tab}`);
      }
    }
  };

  const fetchDomains = async () => {
    try {
      const res = await fetch('/api/domains');
      if (res.ok) {
        const data = await res.json();
        setDomains(data.domains || []);
      }
    } catch (err) {
      console.error('Lỗi tải danh sách domains:', err);
    }
  };

  const handleSend = (text?: string) => {
    const q = text !== undefined ? text : inputQuery;
    if (!q.trim()) return;
    sendMessage(q, activeDomain, useStream);
    setInputQuery('');
  };

  const handleSelectMetric = (sqlExpr: string) => {
    handleSend(`Hãy phân tích chỉ số: ${sqlExpr}`);
  };

  const handleToggleSidebar = () => {
    const nextState = !isSidebarCollapsed;
    setIsSidebarCollapsed(nextState);
    localStorage.setItem('sana_sidebar', String(nextState));
  };

  const handleLogout = () => {
    logout();
  };

  if (isLoading || !isAuthenticated) {
    return (
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-[var(--bg-app)] text-[var(--text-primary)] fade-transition-enter">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-[var(--accent-primary)] text-[var(--accent-primary-text)] flex items-center justify-center font-bold shadow-xs">
            <Sparkles className="w-4 h-4 animate-spin text-[var(--accent-primary-text)]" />
          </div>
          <span className="text-xs font-medium tracking-wide text-[var(--text-secondary)]">Khởi tạo không gian phân tích...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen h-[100dvh] w-full max-w-full overflow-hidden bg-[var(--bg-app)] text-[var(--text-primary)] antialiased font-sans select-none">
      {/* 1. Collapsible Sidebar */}
      <Sidebar
        collapsed={isSidebarCollapsed}
        onToggleCollapse={handleToggleSidebar}
        onNewChat={() => {
          newChat();
          handleSelectTab('chat');
        }}
        onLogout={handleLogout}
        activeDomain={activeDomain}
        activeTab={activeTab}
        onSelectTab={handleSelectTab}
        sessions={sessions}
        currentSessionId={sessionId}
        onSelectSession={(id) => {
          switchSession(id);
          handleSelectTab('chat');
        }}
        onDeleteSession={deleteSession}
        onClearAllSessions={clearAllSessions}
      />

      {/* 2. Main Analytics Workspace */}
      <div className="flex-1 flex flex-col h-full min-w-0 w-full overflow-hidden relative">
        {/* Topbar */}
        <Topbar
          domains={domains}
          activeDomain={activeDomain}
          onSelectDomain={setActiveDomain}
          onClearChat={() => {
            newChat();
            handleSelectTab('chat');
          }}
        />

        {/* Central Content Area with Dedicated Views & Smooth Transitions */}
        <div className="flex-1 relative flex flex-col min-h-0 w-full overflow-hidden">
          {activeTab === 'chat' && (
            <div
              className={cn(
                "flex-1 relative flex flex-col w-full min-h-0 transition-all duration-200",
                messages.length === 0
                  ? "overflow-hidden items-center justify-center p-4 pb-28"
                  : "overflow-y-auto pb-32"
              )}
            >
              {messages.length === 0 ? (
                <WelcomeHero />
              ) : (
                <ChatViewport
                  messages={messages}
                  isStreaming={isStreaming}
                  onOpenSources={() => handleSelectTab('catalog')}
                />
              )}
            </div>
          )}

          {activeTab === 'catalog' && (
            <CatalogView
              domainId={activeDomain}
              onSelectMetric={(metricName) => {
                handleSelectMetric(metricName);
                handleSelectTab('chat');
              }}
              onSwitchToChat={() => handleSelectTab('chat')}
            />
          )}

          {activeTab === 'lineage' && (
            <LineageView domainId={activeDomain} />
          )}

          {activeTab === 'benchmark' && (
            <BenchmarkView />
          )}

          {/* Floating Bottom Prompt Bar (Only shown in Chat & Explore tab) */}
          {activeTab === 'chat' && (
            <FloatingPrompt
              query={inputQuery}
              onChangeQuery={setInputQuery}
              onSend={() => handleSend()}
              disabled={isStreaming || !isAuthenticated}
              isStreaming={useStream}
              onToggleStreaming={setUseStream}
              onOpenSources={() => handleSelectTab('catalog')}
            />
          )}
        </div>
      </div>

      {/* 3. Human-in-the-Loop Modals */}

      <HitlModal
        isOpen={Boolean(pendingHitl)}
        sessionId={pendingHitl?.sessionId || null}
        sqlQuery={pendingHitl?.sqlQuery || null}
        warningText={pendingHitl?.warning || null}
        onDecision={submitHitl}
      />
    </div>
  );
}
