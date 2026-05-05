import { create } from "zustand";

type MessageRole = "user" | "assistant" | "status" | "ticket" | "error";

interface TicketData {
  intent: string;
  urgency: string;
  summary: string;
  department: string;
}

interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  ticketData?: TicketData;
  node?: string;
}

interface ChatStore {
  messages: ChatMessage[];
  threadId: string;
  isStreaming: boolean;
  currentStatus: string;

  // -------------------------------------------------------------------------
  // Actions
  // -------------------------------------------------------------------------
  /** Send a user message and stream the agent's response via SSE */
  sendMessage: (content: string) => Promise<void>;
  resetConversation: () => void;
  
  chatHistory: string[];
  fetchHistory: () => Promise<void>;
  loadThread: (threadId: string) => Promise<void>;

  threadTitles: Record<string, string>;
  setThreadTitle: (threadId: string, title: string) => void;
  loadTitles: () => void;
}

const generateId = (): string =>
  `msg-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;

const generateThreadId = (): string =>
  `thread-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  threadId: generateThreadId(),
  isStreaming: false,
  currentStatus: "",
  chatHistory: [],
  threadTitles: {},

  loadTitles: () => {
    try {
      const stored = localStorage.getItem("apex_thread_titles");
      if (stored) {
        set({ threadTitles: JSON.parse(stored) });
      }
    } catch (e) {
      console.error(e);
    }
  },

  setThreadTitle: (threadId: string, title: string) => {
    set((state) => {
      const updated = { ...state.threadTitles, [threadId]: title };
      localStorage.setItem("apex_thread_titles", JSON.stringify(updated));
      return { threadTitles: updated };
    });
  },

  fetchHistory: async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/chat/history`);
      if (res.ok) {
        const data = await res.json();
        set({ chatHistory: data.threads || [] });
      }
    } catch (e) {
      console.error(e);
    }
  },

  loadThread: async (threadId: string) => {
    try {
      set({ isStreaming: true, currentStatus: "Loading history...", threadId });
      const res = await fetch(`${API_BASE_URL}/api/chat/${threadId}`);
      if (res.ok) {
        const data = await res.json();
        set({
          messages: data.messages || [],
          isStreaming: false,
          currentStatus: "",
        });
      } else {
        set({ isStreaming: false, currentStatus: "" });
      }
    } catch (e) {
      console.error(e);
      set({ isStreaming: false, currentStatus: "" });
    }
  },

  sendMessage: async (content: string): Promise<void> => {
    const { threadId } = get();
    const userMessage: ChatMessage = {
      id: generateId(),
      role: "user",
      content,
      timestamp: new Date(),
    };

    set((state) => ({
      messages: [...state.messages, userMessage],
      isStreaming: true,
      currentStatus: "Connecting to agent...",
    }));

    const assistantMessageId = generateId();

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thread_id: threadId, message: content }),
      });

      if (!response.ok) throw new Error(`Server responded with ${response.status}`);
      if (!response.body) throw new Error("Response body is null — SSE not supported");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let assistantContent = "";
      let hasAddedAssistant = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE events are separated by double newlines (handle both \n and \r\n)
        const events = buffer.split(/\r?\n\r?\n/);
        buffer = events.pop() || "";

        for (const eventBlock of events) {
          if (!eventBlock.trim()) continue;

          // Parse SSE format: "event: <type>\ndata: <json>"
          const lines = eventBlock.split("\n");
          let eventType = "";
          let eventData = "";

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              eventType = line.substring(7).trim();
            } else if (line.startsWith("data: ")) {
              eventData = line.substring(6);
            }
          }

          if (!eventData) continue;

          try {
            const parsed = JSON.parse(eventData);
            switch (eventType) {
              case "status": {
                set({ currentStatus: parsed.status || "" });
                const statusMessage: ChatMessage = {
                  id: generateId(),
                  role: "status",
                  content: parsed.status || "Processing...",
                  timestamp: new Date(),
                  node: parsed.node,
                };
                set((state) => ({ messages: [...state.messages, statusMessage] }));
                break;
              }
              case "token": {
                assistantContent += parsed.content || "";
                if (!hasAddedAssistant) {
                  hasAddedAssistant = true;
                  const newMsg: ChatMessage = {
                    id: assistantMessageId,
                    role: "assistant",
                    content: assistantContent,
                    timestamp: new Date(),
                  };
                  set((state) => ({ messages: [...state.messages, newMsg] }));
                } else {
                  set((state) => ({
                    messages: state.messages.map((msg) =>
                      msg.id === assistantMessageId ? { ...msg, content: assistantContent } : msg
                    ),
                  }));
                }
                break;
              }
              case "ticket": {
                const ticketMessage: ChatMessage = {
                  id: generateId(),
                  role: "ticket",
                  content: "Ticket details extracted",
                  timestamp: new Date(),
                  ticketData: parsed.ticket_data,
                };
                set((state) => ({ messages: [...state.messages, ticketMessage] }));
                break;
              }
              case "error": {
                const errorMessage: ChatMessage = {
                  id: generateId(),
                  role: "error",
                  content: parsed.error || "An unexpected error occurred.",
                  timestamp: new Date(),
                };
                set((state) => ({
                  messages: [...state.messages, errorMessage],
                  isStreaming: false,
                  currentStatus: "",
                }));
                break;
              }
              case "done": {
                set({ isStreaming: false, currentStatus: "" });
                break;
              }
            }
          } catch {
            // Skip malformed JSON events
            console.warn("Failed to parse SSE event data:", eventData);
          }
        }
      }

      // Process any remaining valid event in the buffer after stream closes
      if (buffer.trim()) {
        const lines = buffer.split(/\r?\n/);
        let eventType = "";
        let eventData = "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.substring(7).trim();
          } else if (line.startsWith("data: ")) {
            eventData = line.substring(6);
          }
        }

        if (eventData) {
          try {
            const parsed = JSON.parse(eventData);
            if (eventType === "token") {
              assistantContent += parsed.content || "";
              if (!hasAddedAssistant) {
                set((state) => ({
                  messages: [
                    ...state.messages,
                    {
                      id: assistantMessageId,
                      role: "assistant",
                      content: assistantContent,
                      timestamp: new Date(),
                    },
                  ],
                }));
              } else {
                set((state) => ({
                  messages: state.messages.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: assistantContent }
                      : msg
                  ),
                }));
              }
            } else if (eventType === "ticket") {
              set((state) => ({
                messages: [
                  ...state.messages,
                  {
                    id: generateId(),
                    role: "ticket",
                    content: "Ticket details extracted",
                    timestamp: new Date(),
                    ticketData: parsed.ticket_data,
                  },
                ],
              }));
            }
          } catch {
            // Ignore malformed JSON on stream close
          }
        }
      }

      set({ isStreaming: false, currentStatus: "" });
      get().fetchHistory();
    } catch (error) {
      const errorContent =
        error instanceof Error ? error.message : "Connection failed";

      const errorMessage: ChatMessage = {
        id: generateId(),
        role: "error",
        content: `⚠️ ${errorContent}. Please ensure the backend is running on ${API_BASE_URL}.`,
        timestamp: new Date(),
      };

      set((state) => ({
        messages: [...state.messages, errorMessage],
        isStreaming: false,
        currentStatus: "",
      }));
    }
  },

  resetConversation: (): void => {
    set({
      messages: [],
      threadId: generateThreadId(),
      isStreaming: false,
      currentStatus: "",
    });
  },
}));
