import { useEffect, useRef } from "react";

import type { ChatMessage } from "../api/types";
import { MessageRow } from "./MessageRow";
import { TypingDots } from "./TypingDots";

interface Props {
  messages: ChatMessage[];
  typing: boolean;
}

const GAP_MS = 5 * 60 * 1000;

function clock(at: number): string {
  return new Date(at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

export function ChatView({ messages, typing }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
  }, [messages, typing]);

  let lastAt = 0;

  return (
    <main className="chat" aria-live="polite" aria-label="聊天记录">
      {messages.length === 0 && !typing && (
        <div className="empty">
          <span className="empty-mark" aria-hidden="true">
            <svg viewBox="0 0 48 48" fill="none">
              <path d="M24 7c5 7 5 13 0 17-5-4-5-10 0-17ZM41 24c-7 5-13 5-17 0 4-5 10-5 17 0ZM24 41c-5-7-5-13 0-17 5 4 5 10 0 17ZM7 24c7-5 13-5 17 0-4 5-10 5-17 0Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
              <circle cx="24" cy="24" r="2" fill="currentColor" />
            </svg>
          </span>
          <h2>今天想聊些什么？</h2>
          <p>写下第一句话，对话就从这里开始。</p>
        </div>
      )}

      {messages.map((message) => {
        const showTime = message.at - lastAt > GAP_MS;
        lastAt = message.at;
        return (
          <div key={message.id} className="turn">
            {showTime && <p className="time">{clock(message.at)}</p>}
            <MessageRow message={message} />
          </div>
        );
      })}

      {typing && (
        <div className="row row-him">
          <div className="bubbles bubbles-him">
            <p className="bubble bubble-typing">
              <TypingDots />
            </p>
          </div>
        </div>
      )}

      <div ref={endRef} />
    </main>
  );
}
