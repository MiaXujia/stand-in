import type { ChatMessage } from "../api/types";

interface Props {
  message: ChatMessage;
}

export function MessageRow({ message }: Props) {
  const mine = message.role === "her";
  return (
    <div className={`row ${mine ? "row-her" : "row-him"}`}>
      <div className={`bubbles ${mine ? "bubbles-her" : "bubbles-him"}`}>
        {message.parts.map((part, index) => (
          <p className="bubble" key={`${message.id}-${index}`}>
            {part}
          </p>
        ))}
      </div>
    </div>
  );
}
