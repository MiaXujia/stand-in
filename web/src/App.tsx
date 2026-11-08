import { useEffect, useState } from "react";

import type { ControlAction } from "./api/types";
import { ChatView } from "./components/ChatView";
import { Composer } from "./components/Composer";
import { DisclosureBanner } from "./components/DisclosureBanner";
import { SettingsSheet } from "./components/SettingsSheet";
import { useChat } from "./hooks/useChat";

const DISCLOSURE_KEY = "standin.disclosure.v1";

export default function App() {
  const chat = useChat();
  const [sheetOpen, setSheetOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [showBanner, setShowBanner] = useState(
    () => window.localStorage.getItem(DISCLOSURE_KEY) !== "seen"
  );

  const displayName = chat.state
    ? chat.state.display_name || chat.state.app_name
    : "聊天";

  useEffect(() => {
    document.title = displayName;
  }, [displayName]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const act = async (action: ControlAction) => {
    setSheetOpen(false);
    const message = await chat.control(action);
    if (message) setToast(message);
  };

  if (chat.fatal) {
    return (
      <div className="screen">
        <p className="screen-title">{chat.fatal}</p>
        <p className="screen-hint">向他要一个新的链接。</p>
      </div>
    );
  }

  if (!chat.state) {
    return (
      <div className="screen">
        <span className="spinner" aria-label="加载中" />
      </div>
    );
  }

  const dismiss = () => {
    window.localStorage.setItem(DISCLOSURE_KEY, "seen");
    setShowBanner(false);
  };

  const status = chat.state.muted ? "今天已静音" : chat.state.snoozed ? "稍后回你" : chat.busy ? "正在回复…" : "在这里";

  return (
    <div className="shell">
      <aside className="intro-panel" aria-label="对话空间">
        <div className="brand">
          <span className="brand-icon" aria-hidden="true">
            <svg viewBox="0 0 48 48" fill="none">
              <path d="M24 8c4 6 4 12 0 16-4-4-4-10 0-16ZM40 24c-6 4-12 4-16 0 4-4 10-4 16 0ZM24 40c-4-6-4-12 0-16 4 4 4 10 0 16ZM8 24c6-4 12-4 16 0-4 4-10 4-16 0Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
              <circle cx="24" cy="24" r="2.5" fill="currentColor" />
            </svg>
          </span>
          <span className="brand-name">{chat.state.app_name}</span>
        </div>

        <div className="intro-copy">
          <span className="intro-eyebrow">A QUIET PLACE TO TALK</span>
          <h2>想说的话，<br />慢慢说。</h2>
          <p>在这里，和 {displayName} 留一段只属于这场对话的时间。</p>
          <div className="intro-flower" aria-hidden="true">
            <svg viewBox="0 0 320 320" fill="none">
              <path d="M160 160C99 131 89 68 160 28c71 40 61 103 0 132ZM160 160c29-61 92-71 132 0-40 71-103 61-132 0ZM160 160c61 29 71 92 0 132-71-40-61-103 0-132ZM160 160c-29 61-92 71-132 0 40-71 103-61 132 0Z" stroke="currentColor" strokeWidth="1.2" />
              <circle cx="160" cy="160" r="20" stroke="currentColor" strokeWidth="1.2" />
            </svg>
          </div>
        </div>

        <div className="intro-foot">
          <span className="intro-foot-line" />
          <p>愿每一次开口，都轻松一点。</p>
        </div>
      </aside>

      <div className="app">
        <header className="topbar">
          <div className="who">
            <span className="avatar" aria-hidden="true">{displayName.slice(0, 1)}</span>
            <div className="who-text">
              <h1>{displayName}</h1>
              <p><span className={`presence ${chat.state.muted ? "presence-off" : ""}`} />{status}</p>
            </div>
          </div>
          <button
            className="icon-btn"
            onClick={() => setSheetOpen(true)}
            aria-label="对话设置"
            aria-expanded={sheetOpen}
            aria-controls={sheetOpen ? "settings-sheet" : undefined}
          >
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true">
              <circle cx="5" cy="12" r="1.4" fill="currentColor" />
              <circle cx="12" cy="12" r="1.4" fill="currentColor" />
              <circle cx="19" cy="12" r="1.4" fill="currentColor" />
            </svg>
          </button>
        </header>

        {showBanner && (
          <DisclosureBanner text={chat.state.disclosure} onDismiss={dismiss} />
        )}

        <ChatView messages={chat.messages} typing={chat.typing} />

        {chat.error && (
          <div className="notice" role="alert">
            <span className="notice-text">{chat.error}</span>
            <button className="notice-retry" onClick={chat.retry}>重发</button>
            <button className="notice-close" onClick={chat.clearError} aria-label="关闭提示">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true"><path d="M5 5l14 14M19 5 5 19" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
            </button>
          </div>
        )}

        <Composer disabled={chat.busy} onSend={chat.send} />

        {toast && <div className="toast" role="status">{toast}</div>}

        <SettingsSheet
          open={sheetOpen}
          state={chat.state}
          onClose={() => setSheetOpen(false)}
          onAction={act}
        />
      </div>
    </div>
  );
}
