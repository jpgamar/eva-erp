import api from "./client";

export const assistantApi = {
  conversations: () => api.get("/assistant/conversations").then(r => r.data),
  getConversation: (id: string) => api.get(`/assistant/conversations/${id}`).then(r => r.data),
  createConversation: () => api.post("/assistant/conversations").then(r => r.data),
  deleteConversation: (id: string) => api.delete(`/assistant/conversations/${id}`).then(r => r.data),
  chat: async (message: string, conversationId?: string) => {
    const baseUrl = api.defaults.baseURL || "";
    const res = await fetch(`${baseUrl}/assistant/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        message,
        conversation_id: conversationId || null,
      }),
    });
    if (!res.ok) throw new Error("Chat request failed");
    return res;
  },
};
