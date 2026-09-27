'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { ChatMessage, ChatResponse, ThoughtStep, ChatSession } from '@/types/chat';

const SESSIONS_STORAGE_KEY = 'sana_chat_sessions';

function loadStoredSessions(): ChatSession[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(SESSIONS_STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.error('Failed to load chat sessions:', e);
    return [];
  }
}

function persistSessions(sessions: ChatSession[]) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(SESSIONS_STORAGE_KEY, JSON.stringify(sessions));
  } catch (e) {
    console.error('Failed to persist chat sessions:', e);
  }
}

export function useChatStream() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [sessionId, setSessionId] = useState<string>(() => 'sess_' + Math.random().toString(36).substring(2, 9));
  const [pendingHitl, setPendingHitl] = useState<{
    sessionId: string;
    sqlQuery: string;
    warning: string;
  } | null>(null);

  const activeMsgIdRef = useRef<string | null>(null);
  const messagesRef = useRef<ChatMessage[]>(messages);
  messagesRef.current = messages;

  // Load sessions from localStorage on mount
  useEffect(() => {
    const saved = loadStoredSessions();
    if (saved && saved.length > 0) {
      setSessions(saved);
    }
  }, []);

  // Helper to persist session
  const saveCurrentSession = useCallback((sessId: string, currentMsgs: ChatMessage[], domainId: string) => {
    if (!currentMsgs || currentMsgs.length === 0) return;

    setSessions(prev => {
      const firstUserMsg = currentMsgs.find(m => m.role === 'user');
      const title = firstUserMsg
        ? firstUserMsg.content.slice(0, 45) + (firstUserMsg.content.length > 45 ? '...' : '')
        : 'Phiên phân tích mới';

      const existingIdx = prev.findIndex(s => s.id === sessId);
      let updated: ChatSession[];
      if (existingIdx >= 0) {
        updated = prev.map((s, idx) =>
          idx === existingIdx
            ? { ...s, messages: currentMsgs, updatedAt: Date.now(), title: s.title || title }
            : s
        );
      } else {
        const newSession: ChatSession = {
          id: sessId,
          title,
          domainId,
          createdAt: Date.now(),
          updatedAt: Date.now(),
          messages: currentMsgs,
        };
        updated = [newSession, ...prev];
      }
      persistSessions(updated);
      return updated;
    });
  }, []);

  const newChat = useCallback(() => {
    const newId = 'sess_' + Math.random().toString(36).substring(2, 9);
    setSessionId(newId);
    setMessages([]);
    setIsStreaming(false);
    setPendingHitl(null);
  }, []);

  const switchSession = useCallback((targetSessionId: string) => {
    setSessions(prev => {
      const target = prev.find(s => s.id === targetSessionId);
      if (target) {
        setSessionId(target.id);
        setMessages(target.messages || []);
        setIsStreaming(false);
        setPendingHitl(null);
      }
      return prev;
    });
  }, []);

  const deleteSession = useCallback((targetId: string) => {
    setSessions(prev => {
      const updated = prev.filter(s => s.id !== targetId);
      persistSessions(updated);
      return updated;
    });

    if (sessionId === targetId) {
      newChat();
    }
  }, [sessionId, newChat]);

  const clearAllSessions = useCallback(() => {
    setSessions([]);
    persistSessions([]);
    newChat();
  }, [newChat]);

  const sendMessage = useCallback(
    async (query: string, domainId: string, streamMode: boolean = true) => {
      const trimmed = query.trim();
      if (!trimmed || isStreaming) return;

      const userMsgId = 'user_' + Date.now();
      const assistantMsgId = 'asst_' + Date.now();
      activeMsgIdRef.current = assistantMsgId;

      const userMsg: ChatMessage = {
        id: userMsgId,
        role: 'user',
        content: trimmed,
        timestamp: Date.now(),
      };

      const initialAssistantMsg: ChatMessage = {
        id: assistantMsgId,
        role: 'assistant',
        content: '',
        timestamp: Date.now(),
        isStreaming: true,
        thoughtSteps: [],
      };

      const updatedMsgs = [...messagesRef.current, userMsg, initialAssistantMsg];
      setMessages(updatedMsgs);
      saveCurrentSession(sessionId, updatedMsgs, domainId);
      setIsStreaming(true);

      const startTime = Date.now();
      const token = typeof window !== 'undefined' ? localStorage.getItem('jwt_token') : null;
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      if (streamMode) {
        try {
          const res = await fetch('/api/chat/stream', {
            method: 'POST',
            headers,
            body: JSON.stringify({
              query: trimmed,
              domain_id: domainId,
              session_id: sessionId,
            }),
          });

          if (!res.ok) {
            throw new Error(`Máy chủ trả về mã HTTP ${res.status}`);
          }

          const reader = res.body?.getReader();
          if (!reader) throw new Error('Không thể đọc stream từ máy chủ.');

          const decoder = new TextDecoder('utf-8');
          let buffer = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            let currentEvent: string | null = null;
            for (const line of lines) {
              const lineTrim = line.trim();
              if (lineTrim.startsWith('event:')) {
                currentEvent = lineTrim.replace('event:', '').trim();
              } else if (lineTrim.startsWith('data:') && currentEvent) {
                const rawData = lineTrim.replace('data:', '').trim();
                try {
                  const payload = JSON.parse(rawData);

                  if (currentEvent === 'step') {
                    setMessages(prev => {
                      const next = prev.map(m => {
                        if (m.id === assistantMsgId) {
                          const existing = m.thoughtSteps || [];
                          const updatedData = payload.sql_query
                            ? { ...(m.data || { session_id: sessionId, user_query: trimmed }), sql_query: payload.sql_query }
                            : m.data;
                          return {
                            ...m,
                            data: updatedData,
                            thoughtSteps: [
                              ...existing,
                              {
                                step: payload.step,
                                session_id: payload.session_id,
                                domain_id: payload.domain_id,
                                complexity_level: payload.complexity_level,
                                sql_query: payload.sql_query,
                                timestamp: Date.now(),
                              },
                            ],
                          };
                        }
                        return m;
                      });
                      saveCurrentSession(sessionId, next, domainId);
                      return next;
                    });
                  } else if (currentEvent === 'clarification') {
                    const dur = ((Date.now() - startTime) / 1000).toFixed(1);
                    setMessages(prev => {
                      const next = prev.map(m => {
                        if (m.id === assistantMsgId) {
                          return {
                            ...m,
                            isStreaming: false,
                            durationSec: dur,
                            content: payload.question || 'Cần thêm thông tin làm rõ.',
                            data: {
                              session_id: sessionId,
                              user_query: trimmed,
                              clarification_needed: true,
                              clarification_question: payload.question,
                            },
                          };
                        }
                        return m;
                      });
                      saveCurrentSession(sessionId, next, domainId);
                      return next;
                    });
                  } else if (currentEvent === 'hitl_required') {
                    setPendingHitl({
                      sessionId: payload.session_id || sessionId,
                      sqlQuery: payload.sql_query,
                      warning: payload.warning,
                    });
                    setIsStreaming(false);
                  } else if (currentEvent === 'complete') {
                    const dur = ((Date.now() - startTime) / 1000).toFixed(1);
                    const respData: ChatResponse = payload;

                    setMessages(prev => {
                      const next = prev.map(m => {
                        if (m.id === assistantMsgId) {
                          return {
                            ...m,
                            isStreaming: false,
                            durationSec: dur,
                            content: respData.final_response || '',
                            data: respData,
                          };
                        }
                        return m;
                      });
                      saveCurrentSession(sessionId, next, domainId);
                      return next;
                    });
                  } else if (currentEvent === 'error') {
                    setMessages(prev => {
                      const next = prev.map(m => {
                        if (m.id === assistantMsgId) {
                          return {
                            ...m,
                            isStreaming: false,
                            content: `Đã xảy ra lỗi: ${payload.error}`,
                          };
                        }
                        return m;
                      });
                      saveCurrentSession(sessionId, next, domainId);
                      return next;
                    });
                  }
                } catch (e) {
                  console.error('SSE parse error:', rawData, e);
                }
                currentEvent = null;
              }
            }
          }
        } catch (err: any) {
          setMessages(prev => {
            const next = prev.map(m => {
              if (m.id === assistantMsgId) {
                return {
                  ...m,
                  isStreaming: false,
                  content: `Lỗi kết nối stream: ${err.message}`,
                };
              }
              return m;
            });
            saveCurrentSession(sessionId, next, domainId);
            return next;
          });
        } finally {
          setIsStreaming(false);
        }
      } else {
        // Sync Fallback
        try {
          const res = await fetch('/api/chat', {
            method: 'POST',
            headers,
            body: JSON.stringify({
              query: trimmed,
              domain_id: domainId,
              session_id: sessionId,
            }),
          });
          const respData: ChatResponse = await res.json();
          const dur = ((Date.now() - startTime) / 1000).toFixed(1);

          if (respData.requires_hitl && !respData.hitl_approved) {
            setPendingHitl({
              sessionId: respData.session_id,
              sqlQuery: respData.sql_query || '',
              warning: 'Truy vấn có chi phí quét lớn.',
            });
            setIsStreaming(false);
            return;
          }

          setMessages(prev => {
            const next = prev.map(m => {
              if (m.id === assistantMsgId) {
                return {
                  ...m,
                  isStreaming: false,
                  durationSec: dur,
                  content: respData.final_response || '',
                  data: respData,
                };
              }
              return m;
            });
            saveCurrentSession(sessionId, next, domainId);
            return next;
          });
        } catch (err: any) {
          setMessages(prev => {
            const next = prev.map(m => {
              if (m.id === assistantMsgId) {
                return {
                  ...m,
                  isStreaming: false,
                  content: `Lỗi thực thi: ${err.message}`,
                };
              }
              return m;
            });
            saveCurrentSession(sessionId, next, domainId);
            return next;
          });
        } finally {
          setIsStreaming(false);
        }
      }
    },
    [isStreaming, sessionId, saveCurrentSession]
  );

  const submitHitl = useCallback(
    async (approved: boolean) => {
      if (!pendingHitl) return;
      const targetSessionId = pendingHitl.sessionId;
      setPendingHitl(null);

      const assistantMsgId = 'hitl_res_' + Date.now();
      const placeholderMsg: ChatMessage = {
        id: assistantMsgId,
        role: 'assistant',
        content: '',
        timestamp: Date.now(),
        isStreaming: true,
      };

      setMessages(prev => [...prev, placeholderMsg]);
      setIsStreaming(true);

      const token = typeof window !== 'undefined' ? localStorage.getItem('jwt_token') : null;
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      try {
        const res = await fetch('/api/chat/hitl', {
          method: 'POST',
          headers,
          body: JSON.stringify({
            session_id: targetSessionId,
            approved: approved,
          }),
        });

        const respData: ChatResponse = await res.json();

        setMessages(prev => {
          const next = prev.map(m => {
            if (m.id === assistantMsgId) {
              return {
                ...m,
                isStreaming: false,
                content: respData.final_response || '',
                data: respData,
              };
            }
            return m;
          });
          saveCurrentSession(sessionId, next, respData.domain_id || 'real_estate');
          return next;
        });
      } catch (err: any) {
        setMessages(prev => {
          const next = prev.map(m => {
            if (m.id === assistantMsgId) {
              return {
                ...m,
                isStreaming: false,
                content: `Lỗi xử lý HITL: ${err.message}`,
              };
            }
            return m;
          });
          return next;
        });
      } finally {
        setIsStreaming(false);
      }
    },
    [pendingHitl, sessionId, saveCurrentSession]
  );

  return {
    sessions,
    sessionId,
    messages,
    isStreaming,
    pendingHitl,
    sendMessage,
    submitHitl,
    switchSession,
    newChat,
    deleteSession,
    clearAllSessions,
    resetChat: newChat,
  };
}
