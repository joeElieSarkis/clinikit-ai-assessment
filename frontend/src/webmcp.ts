import type { Session } from './types';

type Context = {
  registerTool(
    tool: {
      name: string;
      title: string;
      description: string;
      inputSchema: object;
      annotations: { readOnlyHint: boolean; untrustedContentHint: boolean };
      execute(input: unknown): unknown;
    },
    options: { signal: AbortSignal },
  ): void | Promise<void>;
};

export function registerReceptionReader(read: () => Session | null) {
  const context = (document as Document & { modelContext?: Context }).modelContext;
  if (!context?.registerTool) return () => {};
  const lifecycle = new AbortController();
  try {
    void Promise.resolve(
      context.registerTool(
        {
          name: 'read_reception_state',
          title: 'Read reception state',
          description:
            'Read the current fictional appointments, pending proposal, and most recent decision. Does not book, confirm, cancel, or send a message.',
          inputSchema: { type: 'object', properties: {}, additionalProperties: false },
          annotations: { readOnlyHint: true, untrustedContentHint: true },
          execute(input) {
            if (
              !input ||
              typeof input !== 'object' ||
              Array.isArray(input) ||
              Object.keys(input).length
            )
              throw new Error('Expected an empty object.');
            const state = read();
            if (!state) throw new Error('The reception session is not ready.');
            return {
              mode: state.mode,
              appointments: state.appointments,
              pending: state.pending,
              latest_decision:
                [...state.messages].reverse().find((message) => message.decision)?.decision ?? null,
            };
          },
        },
        { signal: lifecycle.signal },
      ),
    ).catch(() => {
      /* Registration failure must not interrupt the chat. */
    });
  } catch {
    /* The browser may expose the API without supporting registration. */
  }
  return () => lifecycle.abort();
}
