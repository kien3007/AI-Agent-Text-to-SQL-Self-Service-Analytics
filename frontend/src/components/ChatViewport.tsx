'use client';

import React, { useEffect, useRef } from 'react';
import { Sparkles } from 'lucide-react';
import { ChatMessage } from '@/types/chat';
import AssistantMessage from './AssistantMessage';

interface ChatViewportProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  onOpenSources: (domainId?: string) => void;
}

export default function ChatViewport({
  messages,
  isStreaming,
  onOpenSources,
}: ChatViewportProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex-1 w-full max-w-4xl mx-auto px-4 py-6 flex flex-col gap-6">
      {messages.map((msg) => {
        if (msg.role === 'user') {
          return (
            <div key={msg.id} className="flex justify-end items-start gap-3 w-full">
              <div className="max-w-[80%] rounded-2xl rounded-tr-xs px-4 py-3 bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 text-[14px] leading-relaxed shadow-sm">
                {msg.content}
              </div>
              <div className="w-8 h-8 rounded-full bg-zinc-200 dark:bg-zinc-800 flex items-center justify-center text-xs font-semibold text-zinc-700 dark:text-zinc-300 shrink-0">
                U
              </div>
            </div>
          );
        }

        return (
          <div key={msg.id} className="flex items-start gap-3 w-full">
            <div className="w-8 h-8 rounded-full bg-blue-600/10 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0 border border-blue-500/20 mt-1">
              <Sparkles size={15} />
            </div>
            <div className="flex-1 min-w-0">
              <AssistantMessage
                message={msg}
                onOpenSources={onOpenSources}
              />
            </div>
          </div>
        );
      })}

      <div ref={bottomRef} className="h-4" />
    </div>
  );
}
