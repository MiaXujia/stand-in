export type Role = "her" | "him";

export interface Part {
  text: string;
  delay_ms: number;
}

export interface ChatResponse {
  parts: Part[];
  mode: "reply" | "proactive";
  turn_id: string;
  message_id: number;
  fixed: boolean;
}

export interface TurnResponse {
  turn_id: string;
  client_msg_id: string;
  status: "generating" | "committed" | "failed";
  input_message_id: number;
  output_message_id: number | null;
  error_code: string | null;
}

export interface StateResponse {
  app_name: string;
  display_name: string;
  owner_name: string;
  disclosure: string;
  muted: boolean;
  snoozed: boolean;
  latest_id: number;
}

export interface ApiMessage {
  id: number;
  role: Role;
  mode: string;
  text: string;
  parts: string[];
  created_at: string;
  turn_id: string | null;
}

export interface ChatMessage {
  id: string;
  role: Role;
  parts: string[];
  at: number;
}

export interface ControlResponse {
  ok: boolean;
  message: string;
}

export type ControlAction = "mute" | "snooze" | "call_owner" | "why_ai";

export type StreamEvent =
  | { type: "start"; turn_id: string; mode: "reply" | "proactive"; fixed: boolean }
  | { type: "part"; delay_ms: number }
  | { type: "delta"; text: string }
  | { type: "done"; turn_id: string; message_id: number; mode: "reply" | "proactive"; fixed: boolean }
  | { type: "error"; code: string; message: string };
