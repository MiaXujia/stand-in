interface Props {
  text: string;
  onDismiss: () => void;
}

export function DisclosureBanner({ text, onDismiss }: Props) {
  return (
    <aside className="disclosure">
      <svg className="disclosure-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.5" />
        <path d="M12 10.5v5M12 7.8h.01" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
      <p>{text}</p>
      <button onClick={onDismiss}>知道了</button>
    </aside>
  );
}
