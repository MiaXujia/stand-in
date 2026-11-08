import { useRef, useState } from "react";

interface Props {
  disabled: boolean;
  onSend: (text: string) => void;
}

export function Composer({ disabled, onSend }: Props) {
  const [text, setText] = useState("");
  const areaRef = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
    if (areaRef.current) areaRef.current.style.height = "auto";
  };

  return (
    <form
      className="composer"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <div className="composer-field">
        <label className="sr-only" htmlFor="message-input">输入消息</label>
        <textarea
          id="message-input"
          ref={areaRef}
          value={text}
          rows={1}
          placeholder="想说什么，就写在这里…"
          onChange={(event) => {
            setText(event.target.value);
            const area = event.currentTarget;
            area.style.height = "auto";
            area.style.height = `${Math.min(area.scrollHeight, 132)}px`;
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              submit();
            }
          }}
        />
      </div>
      <button
        type="submit"
        className="send"
        disabled={disabled || !text.trim()}
        aria-label={disabled ? "正在发送" : "发送消息"}
      >
        <svg viewBox="0 0 24 24" width="21" height="21" fill="none" aria-hidden="true">
          <path d="m4 11.5 15-7-4.8 15-3.1-6.1L4 11.5Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
          <path d="m11.1 13.4 7.9-8.9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      </button>
    </form>
  );
}
