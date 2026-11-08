import { useEffect, useRef } from "react";

import type { ControlAction, StateResponse } from "../api/types";

interface Props {
  open: boolean;
  state: StateResponse;
  onClose: () => void;
  onAction: (action: ControlAction) => void;
}

export function SettingsSheet({ open, state, onClose, onAction }: Props) {
  const sheetRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    sheetRef.current?.focus();
    return () => opener?.focus();
  }, [open]);

  if (!open) return null;

  return (
    <div className="sheet-backdrop" role="presentation" onClick={onClose}>
      <section
        id="settings-sheet"
        ref={sheetRef}
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            onClose();
            return;
          }
          if (event.key !== "Tab") return;
          const buttons = Array.from(sheetRef.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? []);
          if (!buttons.length) return;
          const first = buttons[0];
          const last = buttons[buttons.length - 1];
          if (event.shiftKey && (document.activeElement === first || document.activeElement === sheetRef.current)) {
            event.preventDefault();
            last.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
          }
        }}
      >
        <div className="sheet-handle" />
        <div className="sheet-head">
          <h2 id="settings-title">对话设置</h2>
          <p>按你舒服的节奏，决定怎样继续。</p>
        </div>

        <button className="sheet-item" onClick={() => onAction("mute")} disabled={state.muted}>
          <span className="sheet-item-text"><span>静音今天</span><small>{state.muted ? "已静音" : "今天不再主动发消息"}</small></span>
          <Chevron />
        </button>

        <button
          className="sheet-item"
          onClick={() => onAction("snooze")}
          disabled={state.snoozed}
        >
          <span className="sheet-item-text"><span>我在忙</span><small>{state.snoozed ? "已暂停 3 小时" : "3 小时内不打扰"}</small></span>
          <Chevron />
        </button>

        <button className="sheet-item" onClick={() => onAction("call_owner")}>
          <span className="sheet-item-text"><span>叫他本人</span><small>让他直接来找你</small></span>
          <Chevron />
        </button>

        <button className="sheet-item" onClick={() => onAction("why_ai")}>
          <span className="sheet-item-text"><span>关于这段对话</span><small>这不是他本人在打字</small></span>
          <Chevron />
        </button>

        <button className="sheet-close" onClick={onClose}>
          收起
        </button>
      </section>
    </div>
  );
}

function Chevron() {
  return (
    <svg className="sheet-chevron" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="m9 5 7 7-7 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
