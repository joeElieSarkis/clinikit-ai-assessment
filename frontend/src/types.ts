export type Appointment = { id: string; doctor: string; date: string; time: string; status: string };
export type Slot = { doctor: string; date: string; time: string };
export type Decision = {
  intent: string; entities: Record<string, unknown>; action: string; reason: string;
  checks: string[]; tools: { name: string; result: string }[]; source: string; duration_ms: number;
};
export type Message = { id: string; role: 'user' | 'assistant'; content: string; decision?: Decision };
export type Proposal = Slot & { id: string; kind: string; appointment_id: string | null; summary: string };
export type Session = {
  id: string; now: string; mode: string; model: string | null; messages: Message[];
  appointments: Appointment[]; pending: Proposal | null; slots: Slot[]; handoffs: number;
};
