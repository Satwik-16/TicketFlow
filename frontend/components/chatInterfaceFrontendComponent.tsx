"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useChatStore } from "@/store/chatStoreService";

function SidebarItem({ id, idx, loadThread, isStreaming, isActive }: any) {
  const { threadTitles, setThreadTitle } = useChatStore();
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState("");

  const defaultTitle = `Archived Session - ${id.substring(id.length - 4).toUpperCase()}`;
  const title = threadTitles[id] || defaultTitle;

  if (isEditing) {
    return (
      <input
        autoFocus
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        onBlur={() => {
           setIsEditing(false);
           if (editValue.trim()) setThreadTitle(id, editValue.trim());
        }}
        onKeyDown={(e) => {
           if (e.key === "Enter") {
             setIsEditing(false);
             if (editValue.trim()) setThreadTitle(id, editValue.trim());
           }
        }}
        className="w-full px-4 py-4 text-[11px] font-medium tracking-wide bg-white/10 outline-none border-l-2 border-neon-cyan text-white shadow-inner"
      />
    );
  }

  return (
    <div 
      className={`group relative w-full flex items-center border-l-2 transition-all animate-fade-in ${isActive ? 'border-neon-emerald bg-white/[0.04] text-white shadow-lg' : 'border-transparent text-slate-500 hover:text-slate-300 hover:bg-white/[0.02]'}`} 
      style={{ animationDelay: `${0.1 + idx * 0.05}s` }}
    >
      <button 
        onClick={() => loadThread(id)} 
        disabled={isStreaming}
        onDoubleClick={() => { setEditValue(title); setIsEditing(true); }}
        className="flex-1 text-left px-4 py-4 text-[11px] font-medium tracking-wide truncate"
        title="Double-click to rename"
      >
        {title}
      </button>
      <button 
        onClick={(e) => { e.stopPropagation(); setEditValue(title); setIsEditing(true); }}
        className="hidden group-hover:block absolute right-2 p-1 text-slate-500 hover:text-neon-cyan transition-colors"
        title="Rename Session"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
      </button>
    </div>
  );
}

function StatusBubble({ content }: { content: string }) {
  return (
    <div className="flex items-center gap-4 py-2 animate-fade-in md:pl-4 pl-2 border-l border-neon-cyan/40">
      <span className="block h-1.5 w-1.5 animate-pulse bg-neon-cyan shadow-[0_0_10px_#00f0ff]" />
      <span className="text-[11px] text-slate-400 font-display uppercase tracking-[0.2em] italic">{content}</span>
    </div>
  );
}

function TicketCard({ ticketData }: { ticketData: any }) {
  const isCritical = ticketData?.urgency === 'critical';
  const borderColor = isCritical ? 'border-red-500' : 'border-neon-emerald';
  const textColor = isCritical ? 'text-red-400' : 'text-neon-emerald';
  const glow = isCritical ? 'shadow-[0_0_15px_red]' : 'shadow-[0_0_15px_#00ff9d]';

  return (
    <div className="my-6 animate-slide-up md:ml-6 ml-2">
      <div className="relative border border-white/10 bg-[#08080a]/95 p-6 md:p-8 shadow-2xl overflow-hidden group hover:border-white/20 transition-colors">
        {/* Asymmetrical bold accent line */}
        <div className={`absolute left-0 top-0 bottom-0 w-1 md:w-1.5 bg-current ${textColor} ${glow}`} />
        
        <div className="flex items-start justify-between mb-8">
          <h4 className="font-display text-xl md:text-2xl font-bold text-white tracking-widest uppercase">
            System Ticket
          </h4>
          <span className={`px-4 py-1.5 text-[10px] md:text-xs font-bold tracking-[0.3em] uppercase border ${borderColor} ${textColor}`}>
            {ticketData?.urgency || 'unknown'}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 text-sm">
          <div className="border-t border-white/10 pt-4">
            <span className="text-[10px] uppercase tracking-[0.25em] text-slate-500 font-bold block mb-2 font-display">Intent</span>
            <span className="text-slate-200 font-medium text-base">{ticketData?.intent || 'N/A'}</span>
          </div>
          <div className="border-t border-white/10 pt-4">
            <span className="text-[10px] uppercase tracking-[0.25em] text-slate-500 font-bold block mb-2 font-display">Routing Dept</span>
            <span className="text-slate-200 font-medium text-base">{ticketData?.department || 'N/A'}</span>
          </div>
          <div className="col-span-1 md:col-span-2 border-t border-white/10 pt-4">
            <span className="text-[10px] uppercase tracking-[0.25em] text-slate-500 font-bold block mb-2 font-display">Summary Logs</span>
            <span className="text-slate-300 font-light leading-relaxed text-base block bg-white/[0.02] p-4 border border-white/5">{ticketData?.summary || 'No summary provided.'}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ role, content }: { role: string; content: string }) {
  const isUser = role === "user";
  const isError = role === "error";

  if (isUser) {
    return (
      <div className="flex w-full animate-fade-in justify-end">
        <div className="relative max-w-[85%] md:max-w-[70%] text-sm md:text-base leading-relaxed bg-white/[0.03] border-r-2 border-neon-cyan text-white p-6 shadow-lg">
          <div className="absolute top-0 right-[-2px] w-2 h-2 bg-neon-cyan shadow-[0_0_8px_#00f0ff]" />
          <div className="whitespace-pre-wrap font-light">{content}</div>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex w-full animate-fade-in justify-start">
        <div className="relative max-w-[85%] border-l-2 border-red-500 bg-red-950/20 text-red-200 p-6 shadow-lg">
          <div className="whitespace-pre-wrap font-mono text-xs">{content}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex w-full animate-fade-in justify-start">
      <div className="relative max-w-[85%] md:max-w-[75%] p-6 text-sm md:text-base leading-relaxed bg-transparent border-t border-white/[0.05] text-slate-300 group hover:bg-white/[0.01] transition-colors">
        <div className="absolute top-0 left-0 w-1.5 h-1.5 bg-neon-emerald -translate-x-[2px] -translate-y-[2px] opacity-50 group-hover:opacity-100 transition-opacity" />
        <div className="whitespace-pre-wrap font-light">{content}</div>
      </div>
    </div>
  );
}


export default function ChatInterfaceFrontendComponent() {
  const { messages, isStreaming, currentStatus, threadId, sendMessage, resetConversation, fetchHistory, chatHistory, loadThread, loadTitles } = useChatStore();
  const [input, setInput] = useState("");
  const [mounted, setMounted] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setMounted(true);
    fetchHistory();
    useChatStore.getState().loadTitles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentStatus]);

  const handleSubmit = useCallback((e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isStreaming) return;
    sendMessage(input.trim());
    setInput("");
  }, [input, isStreaming, sendMessage]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }, [handleSubmit]);

  return (
    <div className="flex h-screen w-full bg-obsidian bg-grain overflow-hidden relative text-slate-300">
      
      {/* Deep Background Ambient Effects */}
      <div className="absolute top-[-15%] left-[-10%] w-[50%] h-[50%] bg-neon-emerald rounded-full blur-[200px] opacity-[0.05] pointer-events-none mix-blend-screen" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-neon-cyan rounded-full blur-[200px] opacity-[0.05] pointer-events-none mix-blend-screen" />

      {/* Sidebar - Chat Archive */}
      <aside className="relative z-20 hidden lg:flex flex-col w-80 m-6 mr-0 bg-white/[0.01] backdrop-blur-2xl border border-white/[0.05] shadow-2xl animate-slide-right flex-shrink-0">
        <div className="p-8 border-b border-white/[0.05]">
          <h1 className="font-display text-4xl font-bold tracking-tighter text-white uppercase">APEX<span className="text-neon-emerald">.</span></h1>
          <p className="text-[10px] font-bold text-slate-500 uppercase tracking-[0.4em] mt-3">IT Operations</p>
        </div>
        
        <div className="p-6">
          <button 
            onClick={resetConversation} 
            className="w-full relative group overflow-hidden border border-neon-cyan/40 bg-neon-cyan/5 px-4 py-4 text-xs font-bold tracking-widest text-neon-cyan uppercase transition-all hover:bg-neon-cyan/15 hover:border-neon-cyan"
          >
            <span className="relative z-10 block text-center">+ Initialize Sector</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 pb-6 space-y-1">
          <div className="px-2 mb-6 mt-2 text-[10px] font-bold text-slate-600 uppercase tracking-[0.25em] font-display">Archived Subroutines</div>
          {chatHistory.length === 0 && (
            <div className="px-2 text-xs text-slate-600 font-light italic">No archives found.</div>
          )}
          {chatHistory.map((id, i) => (
            <SidebarItem 
              key={id} 
              id={id} 
              idx={i} 
              loadThread={loadThread} 
              isStreaming={isStreaming} 
              isActive={threadId === id} 
            />
          ))}
        </div>
      </aside>

      {/* Main Execution Area */}
      <main className="relative z-10 flex-1 flex flex-col h-[calc(100vh-3rem)] m-6 lg:-ml-4 bg-[#08080a]/80 backdrop-blur-3xl border border-white/[0.08] shadow-[0_0_50px_rgba(0,0,0,0.8)] overflow-hidden animate-slide-up [animation-delay:0.2s]">
        
        {/* Mobile Header / Top Bar */}
        <header className="lg:hidden flex items-center justify-between p-6 border-b border-white/[0.05] bg-obsidian">
           <h1 className="font-display text-2xl font-bold text-white tracking-tighter uppercase">APEX<span className="text-neon-emerald">.</span></h1>
           <button onClick={resetConversation} className="text-[10px] bg-neon-cyan/10 px-3 py-2 border border-neon-cyan/30 text-neon-cyan uppercase tracking-widest font-bold">+ New</button>
        </header>

        {/* Thread Info Bar */}
        <div className="absolute top-6 right-8 text-[10px] font-mono text-slate-600 hidden lg:block tracking-widest uppercase">
          CONNECTION // <span className={mounted ? "text-neon-cyan" : ""}>{mounted ? "SECURE UPLINK ESTABLISHED" : 'AWAITING UPLINK'}</span>
        </div>

        <div className="flex-1 overflow-y-auto p-6 md:p-12 lg:p-16 space-y-10">
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-start justify-center max-w-2xl animate-fade-in [animation-delay:0.4s]">
              <div className="w-16 h-1.5 bg-neon-emerald mb-10 shadow-[0_0_10px_#00ff9d]" />
              <h2 className="font-display text-4xl md:text-5xl lg:text-6xl font-normal text-white mb-6 leading-[1.1] tracking-tight">System operational.<br/>Awaiting directive.</h2>
              <p className="text-sm md:text-base text-slate-500 leading-relaxed font-light tracking-wide max-w-xl">
                Diagnostic protocols, rapid incident escalation, and hardware routing services are online. Please detail your operational constraint below.
              </p>
            </div>
          )}

          {messages.map((msg) => {
            switch (msg.role) {
              case "status": return <StatusBubble key={msg.id} content={msg.content} />;
              case "ticket": return msg.ticketData ? <TicketCard key={msg.id} ticketData={msg.ticketData} /> : null;
              default: return <MessageBubble key={msg.id} role={msg.role} content={msg.content} />;
            }
          })}
          {isStreaming && (
            <div className="flex items-center gap-4 py-2 pl-2">
              <span className="block h-2 w-2 bg-neon-emerald shadow-[0_0_12px_#00ff9d] animate-ping" />
              <span className="text-[10px] text-neon-emerald font-display tracking-[0.3em] font-bold uppercase">Processing Directive</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Terminal */}
        <div className="p-6 md:p-8 border-t border-white/[0.05] bg-obsidian/95 backdrop-blur-xl">
          <form onSubmit={handleSubmit} className="relative flex items-end max-w-4xl mx-auto">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Enter directive sequence..."
              rows={1}
              disabled={isStreaming}
              className="w-full resize-none border-b-2 border-white/10 bg-transparent py-4 text-sm md:text-base text-white placeholder:text-slate-600 focus:border-neon-emerald focus:outline-none disabled:opacity-30 transition-colors font-light"
              style={{ maxHeight: "200px" }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement;
                target.style.height = "auto";
                target.style.height = `${Math.min(target.scrollHeight, 200)}px`;
              }}
            />
            <button
              type="submit"
              disabled={!input.trim() || isStreaming}
              className="absolute right-0 bottom-4 text-[10px] md:text-xs font-bold uppercase tracking-widest text-slate-500 hover:text-neon-emerald transition-colors disabled:opacity-20 flex items-center gap-2 font-display"
            >
              Execute
              <svg className="w-3 h-3 md:w-4 md:h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="square" strokeLinejoin="miter" d="M5 12h14M12 5l7 7-7 7" /></svg>
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
