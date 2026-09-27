'use client';

import React, { useState, useEffect } from 'react';
import { Sidebar, SidebarTab } from '@/components/Sidebar';
import { Topbar } from '@/components/Topbar';
import { WelcomeHero } from '@/components/WelcomeHero';
import ChatViewport from '@/components/ChatViewport';
import { FloatingPrompt } from '@/components/FloatingPrompt';
import LoginModal from '@/components/Modals/LoginModal';
import HitlModal from '@/components/Modals/HitlModal';
import CatalogView from '@/components/Views/CatalogView';
import LineageView from '@/components/Views/LineageView';
import BenchmarkView from '@/components/Views/BenchmarkView';
import { useChatStream } from '@/hooks/useChatStream';
import { DomainItem } from '@/types/chat';

export default function Home() {
  const [activeTab, setActiveTab] = useState<SidebarTab>('chat');
  const [activeDomain, setActiveDomain] = useState<string>('real_estate');
  const [domains, setDomains] = useState<DomainItem[]>([]);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(false);
  const [inputQuery, setInputQuery] = useState<string>('');
  const [useStream, setUseStream] = useState<boolean>(true);
  const [activeModal, setActiveModal] = useState<'login' | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(true);

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
    resetChat,
  } = useChatStream();

  // Load local auth state & domains on mount
  useEffect(() => {
    const token = localStorage.getItem('jwt_token');
    if (!token) {
      setIsAuthenticated(false);
    } else {
      setIsAuthenticated(true);
      fetchDomains();
    }

    const savedSidebar = localStorage.getItem('sana_sidebar');
    if (savedSidebar !== null) {
      setIsSidebarCollapsed(savedSidebar === 'true');
    }
  }, []);

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
    setActiveModal(null);
  };

  const handleToggleSidebar = () => {
    const nextState = !isSidebarCollapsed;
    setIsSidebarCollapsed(nextState);
    localStorage.setItem('sana_sidebar', String(nextState));
  };

  const handleLogout = () => {
    localStorage.removeItem('jwt_token');
    setIsAuthenticated(false);
    setActiveModal('login');
  };

  const handleLoginSuccess = () => {
    setIsAuthenticated(true);
    setActiveModal(null);
    fetchDomains();
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[var(--bg-app)] text-[var(--text-primary)] antialiased font-sans select-none">
      {/* 1. Collapsible Sidebar */}
      <Sidebar
        collapsed={isSidebarCollapsed}
        onToggleCollapse={handleToggleSidebar}
        onNewChat={() => {
          newChat();
          setActiveTab('chat');
        }}
        onLogout={handleLogout}
        activeDomain={activeDomain}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        sessions={sessions}
        currentSessionId={sessionId}
        onSelectSession={(id) => {
          switchSession(id);
          setActiveTab('chat');
        }}
        onDeleteSession={deleteSession}
        onClearAllSessions={clearAllSessions}
      />

      {/* 2. Main Analytics Workspace */}
      <div className="flex-1 flex flex-col h-full min-w-0 relative">
        {/* Topbar */}
        <Topbar
          domains={domains}
          activeDomain={activeDomain}
          onSelectDomain={setActiveDomain}
          onClearChat={() => {
            newChat();
            setActiveTab('chat');
          }}
        />

        {/* Central Content Area with Dedicated Views & Smooth Transitions */}
        <div className="flex-1 relative flex flex-col min-h-0 overflow-hidden">
          {activeTab === 'chat' && (
            <div className="flex-1 overflow-y-auto relative pb-32 flex flex-col animate-in fade-in duration-200">
              {messages.length === 0 ? (
                <WelcomeHero />
              ) : (
                <ChatViewport
                  messages={messages}
                  isStreaming={isStreaming}
                  onOpenSources={() => setActiveTab('catalog')}
                />
              )}
            </div>
          )}

          {activeTab === 'catalog' && (
            <CatalogView
              domainId={activeDomain}
              onSelectMetric={(metricName) => {
                handleSelectMetric(metricName);
                setActiveTab('chat');
              }}
              onSwitchToChat={() => setActiveTab('chat')}
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
              onOpenSources={() => setActiveTab('catalog')}
            />
          )}
        </div>
      </div>

      {/* 3. Enterprise Auth & Human-in-the-Loop Modals */}
      <LoginModal
        isOpen={!isAuthenticated || activeModal === 'login'}
        onSuccess={handleLoginSuccess}
      />

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
