"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { assistantApi } from "@/lib/api/assistant";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import {
  Sparkles,
  Send,
  Plus,
  MessageSquare,
  Trash2,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface Conversation {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

const SUGGESTED_QUERIES = [
  "What's our MRR?",
  "Expenses over $500",
  "Overdue tasks",
  "Q1 OKR progress",
  "Active prospects",
  "Recent meetings",
];

export default function AssistantPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvoId, setActiveConvoId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const loadConversations = useCallback(async () => {
    try {
      const data = await assistantApi.conversations();
      setConversations(data);
    } catch {
      // Silently fail — might be first load
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadConversations(); }, [loadConversations]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadConversation = async (id: string) => {
    try {
      const convo = await assistantApi.getConversation(id);
      setActiveConvoId(id);
      setMessages(convo.messages_json || []);
    } catch {
      toast.error("Failed to load conversation");
    }
  };

  const startNewChat = () => {
    setActiveConvoId(null);
    setMessages([]);
    inputRef.current?.focus();
  };

  const deleteConversation = async (id: string) => {
    try {
      await assistantApi.deleteConversation(id);
      if (activeConvoId === id) startNewChat();
      loadConversations();
      toast.success("Conversation deleted");
    } catch {
      toast.error("Failed to delete conversation");
    }
  };

  const sendMessage = async (text?: string) => {
    const msg = text || input.trim();
    if (!msg || sending) return;

    setInput("");
    setSending(true);

    // Optimistically add user message
    setMessages(prev => [...prev, { role: "user", content: msg }]);

    try {
      const res = await assistantApi.chat(msg, activeConvoId || undefined);
      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let fullText = "";
      let newConvoId = activeConvoId;

      // Add placeholder assistant message
      setMessages(prev => [...prev, { role: "assistant", content: "" }]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ") && line !== "data: [DONE]") {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.conversation_id) newConvoId = data.conversation_id;
              if (data.delta) {
                fullText = data.delta;
                setMessages(prev => {
                  const updated = [...prev];
                  updated[updated.length - 1] = { role: "assistant", content: fullText };
                  return updated;
                });
              }
            } catch {
              // Skip parse errors
            }
          }
        }
      }

      if (newConvoId && newConvoId !== activeConvoId) {
        setActiveConvoId(newConvoId);
      }
      loadConversations();
    } catch {
      toast.error("Failed to get response. Is OpenAI configured?");
      // Remove the empty assistant message
      setMessages(prev => prev.filter(m => m.content !== ""));
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-[calc(100vh-3.5rem)]">
        <div className="w-64 border-r p-4 space-y-3">
          {[1, 2, 3].map(i => <Skeleton key={i} className="h-10 rounded-lg" />)}
        </div>
        <div className="flex-1 p-6">
          <Skeleton className="h-full rounded-xl" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* Sidebar */}
      {sidebarOpen && (
        <div className="w-64 border-r flex flex-col bg-muted/30">
          <div className="p-3 border-b">
            <Button onClick={startNewChat} className="w-full" size="sm">
              <Plus className="h-4 w-4 mr-1" /> New Chat
            </Button>
          </div>
          <ScrollArea className="flex-1 p-2">
            <div className="space-y-1">
              {conversations.map(c => (
                <div
                  key={c.id}
                  className={cn(
                    "group flex items-center gap-2 rounded-lg px-3 py-2 text-sm cursor-pointer transition-colors",
                    activeConvoId === c.id
                      ? "bg-primary/10 text-primary"
                      : "hover:bg-accent text-muted-foreground"
                  )}
                  onClick={() => loadConversation(c.id)}
                >
                  <MessageSquare className="h-4 w-4 shrink-0" />
                  <span className="truncate flex-1">{c.title || "New Chat"}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 opacity-0 group-hover:opacity-100 shrink-0"
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteConversation(c.id);
                    }}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              ))}
              {conversations.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-4">No conversations yet</p>
              )}
            </div>
          </ScrollArea>
        </div>
      )}

      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Messages */}
        <ScrollArea className="flex-1 p-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 mb-4">
                <Sparkles className="h-8 w-8 text-primary" />
              </div>
              <h2 className="text-xl font-semibold mb-2">EVA Assistant</h2>
              <p className="text-muted-foreground mb-6 max-w-md">
                Ask me anything about your business — finances, customers, tasks, prospects, OKRs, and more.
              </p>
              <div className="flex flex-wrap gap-2 justify-center max-w-lg">
                {SUGGESTED_QUERIES.map(q => (
                  <Button
                    key={q}
                    variant="outline"
                    size="sm"
                    className="rounded-full"
                    onClick={() => sendMessage(q)}
                  >
                    {q}
                  </Button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-4 pb-4">
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={cn(
                    "flex gap-3",
                    msg.role === "user" ? "justify-end" : "justify-start"
                  )}
                >
                  {msg.role === "assistant" && (
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 shrink-0 mt-0.5">
                      <Sparkles className="h-4 w-4 text-primary" />
                    </div>
                  )}
                  <div
                    className={cn(
                      "rounded-2xl px-4 py-2.5 max-w-[80%] text-sm",
                      msg.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted"
                    )}
                  >
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </ScrollArea>

        {/* Input */}
        <div className="border-t p-4">
          <div className="max-w-3xl mx-auto flex gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="shrink-0"
              onClick={() => setSidebarOpen(!sidebarOpen)}
            >
              <MessageSquare className="h-4 w-4" />
            </Button>
            <Input
              ref={inputRef}
              placeholder="Ask about your business..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage()}
              disabled={sending}
              className="flex-1"
            />
            <Button
              onClick={() => sendMessage()}
              disabled={!input.trim() || sending}
              size="icon"
            >
              {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
