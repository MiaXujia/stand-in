import type {
  ApiMessage,
  ChatResponse,
  ControlAction,
  ControlResponse,
  StateResponse,
  StreamEvent,
  TurnResponse
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function headers(): Record<string, string> {
  return { "Content-Type": "application/json", "X-Stand-In": "1" };
}

async function errorFrom(response: Response): Promise<ApiError> {
  let message = response.status === 401 ? "unauthorized" : `HTTP ${response.status}`;
  try {
    const body = (await response.json()) as { error?: { message?: string } };
    if (body?.error?.message) message = body.error.message;
  } catch {
    /* 非 JSON 错误体，用默认文案 */
  }
  return new ApiError(message, response.status);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    credentials: "include",
    ...init,
    headers: { ...headers(), ...(init.headers ?? {}) }
  });

  if (!response.ok) throw await errorFrom(response);
  return (await response.json()) as T;
}

export const api = {
  state: () => request<StateResponse>("/api/state"),
  messages: (afterId = 0) =>
    request<ApiMessage[]>(`/api/messages?after_id=${encodeURIComponent(afterId)}`),
  turnByClient: (clientMsgId: string) =>
    request<TurnResponse>(`/api/turns/by-client/${encodeURIComponent(clientMsgId)}`),
  chat: (text: string, clientMsgId: string) =>
    request<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ text, client_msg_id: clientMsgId })
    }),
  control: (action: ControlAction) =>
    request<ControlResponse>("/api/control", {
      method: "POST",
      body: JSON.stringify({ action })
    }),

  /** 读取已提交回复的 SSE 分条事件，必须收到 done 才算完整。 */
  async chatStream(
    text: string,
    clientMsgId: string,
    onEvent: (event: StreamEvent) => void
  ): Promise<Extract<StreamEvent, { type: "done" }>> {
    const response = await fetch(`${BASE}/api/chat/stream`, {
      method: "POST",
      credentials: "include",
      headers: headers(),
      body: JSON.stringify({ text, client_msg_id: clientMsgId })
    });

    if (!response.ok || !response.body) throw await errorFrom(response);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let doneEvent: Extract<StreamEvent, { type: "done" }> | null = null;

    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        for (const line of frame.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          let event: StreamEvent;
          try {
            event = JSON.parse(line.slice(6)) as StreamEvent;
          } catch {
            continue;
          }
          onEvent(event);
          if (event.type === "done") doneEvent = event;
          if (event.type === "error") throw new ApiError(event.message, 503);
        }
        boundary = buffer.indexOf("\n\n");
      }
    }
    if (!doneEvent) throw new ApiError("stream_incomplete", 0);
    return doneEvent;
  }
};

export function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `m-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}
