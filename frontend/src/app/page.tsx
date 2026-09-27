'use client';

import React, { useState, useEffect } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { Topbar } from '@/components/Topbar';
import { WelcomeHero } from '@/components/WelcomeHero';
import ChatViewport from '@/components/ChatViewport';
import { FloatingPrompt } from '@/components/FloatingPrompt';
import LoginModal from '@/components/Modals/LoginModal';
import HitlModal from '@/components/Modals/HitlModal';
import CatalogModal from '@/components/Modals/CatalogModal';
import LineageModal from '@/components/Modals/LineageModal';
import BenchmarkModal from '@/components/Modals/BenchmarkModal';
import { useChatStream } from '@/hooks/useChatStream';
import { DomainItem } from '@/types/chat';

export default function Home() {
  const [activeDomain, setActiveDomain] = useState<string>('real_estate');
  const [domains, setDomains] = useState<DomainItem[]>([]);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(false);
  const [inputQuery, setInputQuery] = useState<string>('');
  const [useStream, setUseStream] = useState<boolean>(true);
  const [activeModal, setActiveModal] = useState<
    'login' | 'catalog' | 'lineage' | 'benchmark' | null
  >(null);
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
        onNewChat={newChat}
        onOpenCatalog={() => setActiveModal('catalog')}
        onOpenLineage={() => setActiveModal('lineage')}
        onOpenBenchmark={() => setActiveModal('benchmark')}
        onLogout={handleLogout}
        activeDomain={activeDomain}
        sessions={sessions}
        currentSessionId={sessionId}
        onSelectSession={switchSession}
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
          onClearChat={newChat}
        />

        {/* Central Content Area */}
        <div className="flex-1 overflow-y-auto relative pb-32 flex flex-col">
          {messages.length === 0 ? (
            <WelcomeHero />
          ) : (
            <ChatViewport
              messages={messages}
              isStreaming={isStreaming}
              onOpenSources={() => setActiveModal('catalog')}
            />
          )}
        </div>

        {/* Floating Bottom Prompt Bar */}
        <FloatingPrompt
          query={inputQuery}
          onChangeQuery={setInputQuery}
          onSend={() => handleSend()}
          disabled={isStreaming || !isAuthenticated}
          isStreaming={useStream}
          onToggleStreaming={setUseStream}
          onOpenSources={() => setActiveModal('catalog')}
        />
      </div>

      {/* 3. Enterprise Modals */}
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

      <CatalogModal
        isOpen={activeModal === 'catalog'}
        domainId={activeDomain}
        onClose={() => setActiveModal(null)}
        onSelectMetric={handleSelectMetric}
      />

      <LineageModal
        isOpen={activeModal === 'lineage'}
        domainId={activeDomain}
        onClose={() => setActiveModal(null)}
      />

      <BenchmarkModal
        isOpen={activeModal === 'benchmark'}
        onClose={() => setActiveModal(null)}
      />
    </div>
  );
}
