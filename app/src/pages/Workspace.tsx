import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { useRetryingEffect } from "../lib/useRetryingEffect";
import type { AgentView, ChatMessage, ConversationView } from "../lib/types";
import AgentBadge from "../components/agents/AgentBadge";
import MessageBubble from "../components/workspace/MessageBubble";

export default function Workspace() {
  const [agents, setAgents] = useState<AgentView[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationView[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const loadAgents = useCallback(() => {
    return api.get<{ agents: AgentView[] }>("/agents").then((res) => {
      setAgents(res.agents);
      if (res.agents.length > 0) setSelectedAgentId((prev) => prev ?? res.agents[0].id);
    });
  }, []);

  useRetryingEffect(loadAgents, [loadAgents]);

  useEffect(() => {
    if (!selectedAgentId) return;
    setActiveConvId(null);
    setMessages([]);
  }, [selectedAgentId]);

  const loadConversations = useCallback(() => {
    if (!selectedAgentId) return Promise.resolve();
    return api
      .get<{ conversations: ConversationView[] }>(`/conversations?agent_id=${selectedAgentId}`)
      .then((res) => setConversations(res.conversations));
  }, [selectedAgentId]);

  useRetryingEffect(loadConversations, [loadConversations]);

  const loadMessages = useCallback(() => {
    if (!activeConvId) return Promise.resolve();
    return api
      .get<{ messages: ChatMessage[] }>(`/conversations/${activeConvId}`)
      .then((res) => setMessages(res.messages));
  }, [activeConvId]);

  useRetryingEffect(loadMessages, [loadMessages]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function startConversation() {
    if (!selectedAgentId) return;
    const conv = await api.post<ConversationView>("/conversations", { agent_id: selectedAgentId });
    setConversations((prev) => [conv, ...prev]);
    setActiveConvId(conv.id);
    setMessages([]);
  }

  async function send() {
    if (!draft.trim()) return;
    let convId = activeConvId;
    if (!convId) {
      if (!selectedAgentId) return;
      const conv = await api.post<ConversationView>("/conversations", { agent_id: selectedAgentId });
      setConversations((prev) => [conv, ...prev]);
      setActiveConvId(conv.id);
      convId = conv.id;
    }
    const content = draft;
    setDraft("");
    setMessages((prev) => [
      ...prev,
      { id: "temp-" + Date.now(), conversation_id: convId!, role: "user", content, citations: [], governance_notes: [], memories_used: [], created_at: null },
    ]);
    setSending(true);
    try {
      const assistantMsg = await api.post<ChatMessage>(`/conversations/${convId}/messages`, { content });
      const full = await api.get<{ messages: ChatMessage[] }>(`/conversations/${convId}`);
      setMessages(full.messages);
      void assistantMsg;
    } finally {
      setSending(false);
    }
  }

  const selectedAgent = agents.find((a) => a.id === selectedAgentId) ?? null;

  return (
    <div className="flex h-full gap-4">
      <div className="w-64 shrink-0 space-y-3 overflow-y-auto">
        <h2 className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
          Agents
        </h2>
        {agents.map((agent) => (
          <AgentBadge key={agent.id} agent={agent} compact selected={agent.id === selectedAgentId} onClick={() => setSelectedAgentId(agent.id)} />
        ))}

        <div className="pt-3">
          <button
            className="w-full rounded-md border px-3 py-1.5 text-xs font-medium"
            style={{ borderColor: "var(--color-border)" }}
            onClick={startConversation}
          >
            + New conversation
          </button>
        </div>

        <div className="space-y-1 pt-2">
          {conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => setActiveConvId(c.id)}
              className="block w-full truncate rounded-md px-2 py-1.5 text-left text-xs"
              style={{
                background: c.id === activeConvId ? "color-mix(in srgb, var(--color-primary) 10%, transparent)" : "transparent",
                color: c.id === activeConvId ? "var(--color-primary)" : "var(--color-text-muted)",
              }}
            >
              {c.title}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-1 flex-col rounded-lg border" style={{ borderColor: "var(--color-border)", background: "var(--color-bg)" }}>
        {selectedAgent && (
          <div className="border-b px-4 py-2.5 text-xs" style={{ borderColor: "var(--color-border)", color: "var(--color-text-muted)" }}>
            Talking to <strong style={{ color: "var(--color-text)" }}>{selectedAgent.name}</strong> — {selectedAgent.purpose}
          </div>
        )}

        <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
          {messages.length === 0 && (
            <div className="py-12 text-center text-sm" style={{ color: "var(--color-text-muted)" }}>
              Ask {selectedAgent?.name ?? "an agent"} a question about the imported repository.
            </div>
          )}
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}
          {sending && (
            <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {selectedAgent?.name} is thinking...
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 border-t p-3" style={{ borderColor: "var(--color-border)" }}>
          <input
            className="flex-1 rounded-md border px-3 py-2 text-sm"
            style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}
            placeholder="Ask a question..."
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !sending && send()}
            disabled={sending}
          />
          <button
            className="rounded-md px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            style={{ background: "var(--color-primary)" }}
            onClick={send}
            disabled={sending || !draft.trim()}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
