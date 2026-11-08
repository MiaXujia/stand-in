import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api, newId } from "../api/client";
import type { ApiMessage, ChatMessage, ControlAction, StateResponse } from "../api/types";

const PENDING_KEY = "stand-in.pending-turn";

function fromApi(message: ApiMessage): ChatMessage {
  return {
    id: `srv-${message.id}`,
    role: message.role,
    parts: message.parts.length ? message.parts : [message.text],
    at: new Date(message.created_at).getTime()
  };
}

interface PendingTurn {
  text: string;
  clientId: string;
}

interface FailedSend extends PendingTurn {
  appendEcho: boolean;
}

function savedPending(): PendingTurn | null {
  try {
    const raw = sessionStorage.getItem(PENDING_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<PendingTurn>;
    return typeof value.text === "string" && typeof value.clientId === "string"
      ? { text: value.text, clientId: value.clientId }
      : null;
  } catch {
    return null;
  }
}

function savePending(value: PendingTurn | null): void {
  try {
    if (value) sessionStorage.setItem(PENDING_KEY, JSON.stringify(value));
    else sessionStorage.removeItem(PENDING_KEY);
  } catch {
    /* 内存中的 pendingRef 仍可处理当前页面 */
  }
}

export function useChat() {
  const [state, setState] = useState<StateResponse | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [typing, setTyping] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastFailed, setLastFailed] = useState<FailedSend | null>(null);
  const [fatal, setFatal] = useState<string | null>(null);

  const latestId = useRef(0);
  const alive = useRef(true);
  const activeBubble = useRef<string | null>(null);
  const createdThisTurn = useRef<string[]>([]);
  const pendingRef = useRef<PendingTurn | null>(null);
  const streamActive = useRef(false);

  const syncHistory = useCallback(async (discard: string[] = []) => {
    const fresh = await api.messages(latestId.current);
    if (fresh.length) latestId.current = fresh[fresh.length - 1].id;
    setMessages((prev) => {
      const kept = prev.filter((message) => !discard.includes(message.id));
      const seen = new Set(kept.map((message) => message.id));
      return [...kept, ...fresh.map(fromApi).filter((message) => !seen.has(message.id))];
    });
  }, []);

  const settlePending = useCallback(async () => {
    const pending = pendingRef.current;
    if (!pending) return;
    let turn;
    try {
      turn = await api.turnByClient(pending.clientId);
    } catch (err) {
      if (!(err instanceof ApiError) || err.status !== 404) return;
      pendingRef.current = null;
      savePending(null);
      setBusy(false);
      setTyping(false);
      setLastFailed({ ...pending, appendEcho: true });
      setError("上次消息可能没送达，可以重试。");
      return;
    }
    if (turn.status === "generating") return;
    const discard = [...createdThisTurn.current, `her-${pending.clientId}`];
    try {
      await syncHistory(discard);
    } catch {
      return;
    }
    createdThisTurn.current = [];
    pendingRef.current = null;
    savePending(null);
    setBusy(false);
    setTyping(false);
    if (turn.status === "committed") {
      setLastFailed(null);
      setError(null);
    } else {
      setLastFailed({ text: pending.text, clientId: newId(), appendEcho: false });
      setError("这次回复失败了，可以重试。");
    }
  }, [syncHistory]);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const [snapshot, history] = await Promise.all([api.state(), api.messages(0)]);
        if (cancelled) return;
        setState(snapshot);
        latestId.current = history.length ? history[history.length - 1].id : snapshot.latest_id;
        setMessages(history.map(fromApi));
        const pending = savedPending();
        if (pending) {
          pendingRef.current = pending;
          setBusy(true);
          setTyping(true);
          await settlePending();
        }
      } catch (err) {
        if (cancelled) return;
        const status = err instanceof ApiError ? err.status : 0;
        setFatal(status === 401 ? "这个链接不对，或者已经失效了。" : "连不上，稍后再刷新。");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [settlePending]);

  useEffect(() => {
    if (fatal) return;
    const pendingTimer = window.setInterval(() => {
      if (pendingRef.current && !streamActive.current) void settlePending();
    }, 2000);
    const historyTimer = window.setInterval(() => {
      if (!pendingRef.current) void syncHistory().catch(() => {});
    }, 20000);
    return () => {
      window.clearInterval(pendingTimer);
      window.clearInterval(historyTimer);
    };
  }, [fatal, settlePending, syncHistory]);

  const send = useCallback(
    async (raw: string, options: { clientId?: string; appendEcho?: boolean } = {}) => {
      const text = raw.trim();
      if (!text || busy || pendingRef.current) return;
      const clientId = options.clientId ?? newId();
      const pending = { text, clientId };
      pendingRef.current = pending;
      savePending(pending);
      activeBubble.current = null;
      createdThisTurn.current = [];
      setError(null);
      setLastFailed(null);
      if (options.appendEcho !== false) {
        setMessages((prev) => [
          ...prev,
          { id: `her-${clientId}`, role: "her", parts: [text], at: Date.now() }
        ]);
      }
      setTyping(true);
      setBusy(true);
      streamActive.current = true;

      try {
        await api.chatStream(text, clientId, (event) => {
          switch (event.type) {
            case "part":
              activeBubble.current = null;
              break;
            case "delta": {
              if (!alive.current) return;
              const current = activeBubble.current;
              if (!current) {
                const id = `him-${newId()}`;
                activeBubble.current = id;
                createdThisTurn.current.push(id);
                setTyping(false);
                setMessages((prev) => [
                  ...prev,
                  { id, role: "him", parts: [event.text], at: Date.now() }
                ]);
              } else {
                setMessages((prev) =>
                  prev.map((message) =>
                    message.id === current
                      ? { ...message, parts: [message.parts[0] + event.text] }
                      : message
                  )
                );
              }
              break;
            }
            case "done":
              setTyping(false);
              break;
            default:
              break;
          }
        });
      } catch {
        const previews = createdThisTurn.current;
        setMessages((prev) => prev.filter((message) => !previews.includes(message.id)));
        createdThisTurn.current = [];
      } finally {
        streamActive.current = false;
        activeBubble.current = null;
        await settlePending();
      }
    },
    [busy, settlePending]
  );

  const retry = useCallback(() => {
    if (!lastFailed) return;
    void send(lastFailed.text, {
      clientId: lastFailed.clientId,
      appendEcho: lastFailed.appendEcho
    });
  }, [lastFailed, send]);

  const control = useCallback(async (action: ControlAction): Promise<string> => {
    try {
      const response = await api.control(action);
      setState((prev) => {
        if (!prev) return prev;
        if (action === "mute") return { ...prev, muted: true };
        if (action === "snooze") return { ...prev, snoozed: true };
        return prev;
      });
      return response.message;
    } catch {
      setError("操作没成功，稍后再试。");
      return "";
    }
  }, []);

  return {
    state,
    messages,
    typing,
    busy,
    error,
    fatal,
    send: (text: string) => void send(text),
    retry,
    control,
    clearError: () => setError(null)
  };
}
