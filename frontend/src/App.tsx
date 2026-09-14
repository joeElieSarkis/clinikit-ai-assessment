import { useEffect, useRef, useState } from 'react';
import {
  ArrowUp,
  ArrowUpRight,
  Check,
  ChevronRight,
  CircleHelp,
  Clock3,
  Code2,
  LoaderCircle,
  MessageCircle,
  Plus,
  RotateCcw,
  ShieldCheck,
  X,
} from 'lucide-react';
import type { Decision, Session } from './types';
import { registerReceptionReader } from './webmcp';

const examples = [
  { title: 'Find an appointment', text: 'Can I see Dr. George tomorrow afternoon?' },
  { title: 'Change my plans', text: 'Move my appointment from Monday to Wednesday.' },
  {
    title: 'Just exploring',
    text: 'I might want to see Dr. George tomorrow at 4, but don’t book anything yet.',
  },
];
const dateLabel = (date: string, short = false) =>
  new Intl.DateTimeFormat('en-GB', {
    weekday: short ? 'short' : 'long',
    day: 'numeric',
    month: short ? 'short' : 'long',
    timeZone: 'UTC',
  }).format(new Date(`${date}T12:00:00Z`));
const timeLabel = (time: string) => {
  const [h, m] = time.split(':').map(Number);
  return `${h % 12 || 12}:${String(m).padStart(2, '0')} ${h >= 12 ? 'pm' : 'am'}`;
};

async function api(path: string, body?: unknown): Promise<Session> {
  const response = await fetch(`/api${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    signal: AbortSignal.timeout(35000),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      typeof error.detail === 'string'
        ? error.detail
        : 'We couldn’t complete that request. Please try again.',
    );
  }
  return response.json();
}

function DecisionDetails({ decision }: { decision: Decision }) {
  return (
    <div className="decision-details">
      <div className="decision-heading">
        <span>{decision.intent.replaceAll('_', ' ')}</span>
        <small>
          {decision.duration_ms} ms · {decision.source}
        </small>
      </div>
      <p>{decision.reason}</p>
      <h3>Structured information</h3>
      <pre>{JSON.stringify(decision.entities, null, 2)}</pre>
      <h3>Policy checks</h3>
      <ul>
        {decision.checks.map((check, i) => (
          <li key={i}>
            <ShieldCheck size={15} />
            {check}
          </li>
        ))}
      </ul>
      <h3>Next action</h3>
      <code>{decision.action}()</code>
      {!!decision.tools.length && (
        <>
          <h3>Mock tool results</h3>
          {decision.tools.map((tool, i) => (
            <p className="tool-result" key={i}>
              <code>{tool.name}()</code>
              <span>{tool.result}</span>
            </p>
          ))}
        </>
      )}
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [dialog, setDialog] = useState<'decisions' | 'about' | 'reset' | null>(null);
  const [selectedDecision, setSelectedDecision] = useState<Decision | null>(null);
  const [mobileAgenda, setMobileAgenda] = useState(false);
  const modal = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const sending = useRef(false);
  const created = useRef(false);
  const lastMessageRequest = useRef<{ message: string; sessionId: string; id: string } | null>(
    null,
  );
  const lastProposalRequest = useRef<{ key: string; id: string } | null>(null);
  const sessionRef = useRef<Session | null>(null);
  useEffect(() => {
    sessionRef.current = session;
  }, [session]);
  useEffect(() => registerReceptionReader(() => sessionRef.current), []);

  async function start() {
    setBusy(true);
    setError('');
    try {
      const fresh = await api('/sessions', {});
      setSession(fresh);
      setDraft('');
      sessionStorage.setItem('reception-session', fresh.id);
    } catch {
      setError('Reception is starting or temporarily unavailable. Please try again in a moment.');
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (created.current) return;
    created.current = true;
    const saved = sessionStorage.getItem('reception-session');
    if (!saved) {
      void start();
      return;
    }
    setBusy(true);
    void api(`/sessions/${saved}`)
      .then(setSession)
      .catch(() => start())
      .finally(() => setBusy(false));
  }, []);
  useEffect(() => {
    if (dialog) modal.current?.showModal();
    else modal.current?.close();
  }, [dialog]);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [session?.messages.length, busy]);

  async function send(text = draft) {
    if (!text.trim() || !session || sending.current) return;
    sending.current = true;
    setBusy(true);
    setError('');
    const normalized = text.trim();
    if (
      lastMessageRequest.current?.message !== normalized ||
      lastMessageRequest.current.sessionId !== session.id
    ) {
      lastMessageRequest.current = {
        message: normalized,
        sessionId: session.id,
        id: crypto.randomUUID(),
      };
    }
    try {
      setSession(
        await api(`/sessions/${session.id}/messages`, {
          message: normalized,
          request_id: lastMessageRequest.current.id,
        }),
      );
      lastMessageRequest.current = null;
      setDraft('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please retry.');
      setDraft(text);
    } finally {
      sending.current = false;
      setBusy(false);
      input.current?.focus();
    }
  }
  async function resolveProposal(confirm: boolean) {
    if (!session?.pending || sending.current) return;
    sending.current = true;
    setBusy(true);
    setError('');
    const key = `${session.id}:${session.pending.id}:${confirm}`;
    if (lastProposalRequest.current?.key !== key)
      lastProposalRequest.current = { key, id: crypto.randomUUID() };
    try {
      setSession(
        await api(`/sessions/${session.id}/${confirm ? 'confirm' : 'dismiss'}`, {
          proposal_id: session.pending.id,
          request_id: lastProposalRequest.current.id,
        }),
      );
      lastProposalRequest.current = null;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Please try again.');
      try {
        setSession(await api(`/sessions/${session.id}`));
      } catch {
        /* Keep visible state until a retry succeeds. */
      }
    } finally {
      sending.current = false;
      setBusy(false);
    }
  }
  const decisions = session?.messages.filter((m) => m.decision) ?? [];
  const failedMessage =
    session?.messages.at(-1)?.decision?.action === 'service_unavailable'
      ? session.messages.at(-2)
      : undefined;
  const today = session?.now.slice(0, 10);
  const hasConversation = (session?.messages.length ?? 0) > 1;
  const liveModel = session?.mode === 'gemini' || session?.mode === 'openai';
  const modeLabel = !session
    ? 'Connecting'
    : session.mode === 'gemini'
      ? 'Gemini'
      : session.mode === 'openai'
        ? 'OpenAI'
        : 'Offline demo';

  return (
    <div className="app-shell">
      <aside className="brand-panel">
        <a className="brand" href="/" aria-label="CliniKit reception home">
          <span className="brand-mark">
            <Plus strokeWidth={1.5} />
          </span>
          clinikit<span className="brand-period">.</span>
        </a>
        <div className="brand-navigation">
          <span className="nav-caption">THE PATIENT DESK</span>
          <div className="nav-current">
            <MessageCircle size={18} />
            Reception<span>01</span>
          </div>
        </div>
        <div className="brand-statement">
          <span className="small-cross">✳</span>
          <p>
            Manage your
            <br />
            appointments.
          </p>
          <div className="brand-rule" />
          <span>
            Book a visit or update an
            <br />
            existing appointment.
          </span>
        </div>
        <button className="brand-about" onClick={() => setDialog('about')}>
          About this demo
          <ArrowUpRight size={16} />
        </button>
      </aside>

      <main className="reception">
        <header className="topbar">
          <div className="breadcrumb">
            CliniKit <span>/</span> Reception
          </div>
          <div className="topbar-actions">
            <span className="mode-badge">{modeLabel}</span>
            <button
              className="icon-button"
              aria-label="About this demo"
              onClick={() => setDialog('about')}
            >
              <CircleHelp size={17} />
            </button>
            <button
              className="icon-button"
              aria-label="Start a new conversation"
              onClick={() => setDialog('reset')}
              disabled={busy || !session}
            >
              <RotateCcw size={17} />
            </button>
          </div>
        </header>
        <div className="workspace">
          <section className="conversation" aria-label="Conversation with reception">
            <div className="conversation-heading">
              <div>
                <div className="eyebrow">VIRTUAL RECEPTION</div>
                <h1>How can we help?</h1>
              </div>
              <span className="reception-symbol" aria-hidden="true">
                ✳
              </span>
            </div>
            <div
              className="conversation-scroll"
              role="log"
              aria-live="polite"
              aria-relevant="additions text"
              aria-label="Messages"
            >
              {!hasConversation && (
                <div className="welcome">
                  <h2>
                    Book or manage
                    <br />
                    an appointment.
                  </h2>
                  <p>
                    Tell us which doctor you’d like to see,
                    <br className="desktop-break" /> or ask about an existing appointment.
                  </p>
                </div>
              )}
              {hasConversation &&
                session?.messages.map((message) => (
                  <article className={`message ${message.role}`} key={message.id}>
                    <div className="message-author">
                      {message.role === 'assistant' ? (
                        <>
                          <span className="mini-mark">+</span> RECEPTION
                        </>
                      ) : (
                        'YOU'
                      )}
                    </div>
                    <p>{message.content}</p>
                    {message.id === session?.messages.at(-1)?.id &&
                      failedMessage?.role === 'user' && (
                        <button
                          className="retry-message"
                          disabled={busy}
                          onClick={() => void send(failedMessage.content)}
                        >
                          <RotateCcw size={14} />
                          Retry message
                        </button>
                      )}
                    {message.decision && (
                      <button
                        className="decision-link"
                        onClick={() => {
                          setSelectedDecision(message.decision!);
                          setDialog('decisions');
                        }}
                      >
                        <ShieldCheck size={13} />
                        View decision
                        <ChevronRight size={12} />
                      </button>
                    )}
                  </article>
                ))}
              {busy && session && (
                <div className="thinking" role="status">
                  <span />
                  <span />
                  <span />
                  <span className="sr-only">Reception is checking your request</span>
                </div>
              )}
              {!!session?.slots.length && !session.pending && (
                <div className="slot-list">
                  <div className="eyebrow">AVAILABLE TIMES · BEIRUT</div>
                  {session.slots.map((slot) => (
                    <button
                      disabled={busy}
                      key={`${slot.doctor}-${slot.date}-${slot.time}`}
                      onClick={() =>
                        void send(`Use Dr. ${slot.doctor} on ${slot.date} at ${slot.time}`)
                      }
                    >
                      <span>
                        <strong>{dateLabel(slot.date, true)}</strong>
                        <small>Dr. {slot.doctor}</small>
                      </span>
                      <span>
                        {timeLabel(slot.time)}
                        <ChevronRight size={16} />
                      </span>
                    </button>
                  ))}
                </div>
              )}
              {session?.pending && (
                <div className="confirmation">
                  <div className="eyebrow">PLEASE REVIEW</div>
                  <h3>
                    {session.pending.kind === 'cancel'
                      ? 'Cancel this visit?'
                      : session.pending.kind === 'reschedule'
                        ? 'Move your visit?'
                        : 'Your visit, almost there.'}
                  </h3>
                  <p>{session.pending.summary}</p>
                  <div className="confirmation-actions">
                    <button
                      className="primary-button"
                      disabled={busy}
                      onClick={() => void resolveProposal(true)}
                    >
                      <Check size={16} />
                      {session.pending.kind === 'cancel'
                        ? 'Confirm cancellation'
                        : session.pending.kind === 'reschedule'
                          ? 'Confirm new time'
                          : 'Confirm appointment'}
                    </button>
                    <button
                      className="text-button"
                      disabled={busy}
                      onClick={() => void resolveProposal(false)}
                    >
                      Keep as is
                    </button>
                  </div>
                  <small>Only this confirmation will change your appointments.</small>
                </div>
              )}
              <div ref={end} />
            </div>
            {!hasConversation && (
              <div className="suggestions">
                <div className="eyebrow">A FEW PLACES TO START</div>
                {examples.map((example, i) => (
                  <button
                    disabled={busy || !session}
                    key={example.title}
                    onClick={() => void send(example.text)}
                  >
                    <span className="suggestion-number">0{i + 1}</span>
                    <span>{example.title}</span>
                    <ArrowUpRight size={18} />
                  </button>
                ))}
              </div>
            )}
            {error && (
              <div className="error-banner" role="alert">
                <span>{error}</span>
                {!session && <button onClick={() => void start()}>Retry connection</button>}
              </div>
            )}
            <form
              className="composer"
              onSubmit={(event) => {
                event.preventDefault();
                void send();
              }}
            >
              <label className="sr-only" htmlFor="patient-message">
                Your message to reception
              </label>
              <textarea
                ref={input}
                id="patient-message"
                placeholder="What can we help you with?"
                value={draft}
                maxLength={2000}
                rows={2}
                disabled={!session}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                    event.preventDefault();
                    void send();
                  }
                }}
              />
              <div className="composer-bottom">
                <span>Appointments change only after you confirm.</span>
                <button
                  className="send-button"
                  type="submit"
                  aria-label="Send message"
                  disabled={busy || !session || !draft.trim()}
                >
                  {busy ? <LoaderCircle size={20} className="spin" /> : <ArrowUp size={21} />}
                </button>
              </div>
            </form>
            <div className="conversation-footnote">
              <span>Fictional clinic · Please use sample information</span>
              <button
                onClick={() => {
                  setSelectedDecision(null);
                  setDialog('decisions');
                }}
              >
                <Code2 size={14} />
                Decision log
              </button>
            </div>
          </section>

          <aside
            className={`agenda ${mobileAgenda ? 'agenda-open' : ''}`}
            aria-label="Your visit details"
          >
            <button
              className="agenda-toggle"
              onClick={() => setMobileAgenda(!mobileAgenda)}
              aria-expanded={mobileAgenda}
            >
              Your visits & clinic details
              <ChevronRight size={16} />
            </button>
            <div className="agenda-content">
              <div className="agenda-date">
                <span className="eyebrow">YOUR CLINIC COMPANION</span>
                <span>{today ? dateLabel(today, true) : 'Beirut, Lebanon'}</span>
              </div>
              <section className="visits">
                <div className="section-label">
                  <h2>Your next visits</h2>
                  <span>
                    {session?.appointments.filter((a) => a.status === 'confirmed').length ?? '—'}
                  </span>
                </div>
                {session?.appointments
                  .filter((a) => a.status === 'confirmed')
                  .map((appointment) => (
                    <div className="visit" key={appointment.id}>
                      <div className="visit-date">
                        <span>{new Date(`${appointment.date}T12:00:00`).getDate()}</span>
                        <small>
                          {new Date(`${appointment.date}T12:00:00`)
                            .toLocaleDateString('en-GB', { month: 'short' })
                            .toUpperCase()}
                        </small>
                      </div>
                      <div className="visit-info">
                        <h3>Dr. {appointment.doctor}</h3>
                        <p>
                          {dateLabel(appointment.date, true).split(',')[0]} ·{' '}
                          {timeLabel(appointment.time)}
                        </p>
                        <small>{appointment.id} · Confirmed</small>
                        <div className="visit-actions">
                          <button
                            disabled={busy}
                            onClick={() => {
                              setDraft(`Reschedule appointment ${appointment.id}`);
                              input.current?.focus();
                            }}
                          >
                            Reschedule
                          </button>
                          <button
                            disabled={busy}
                            onClick={() => void send(`Cancel appointment ${appointment.id}`)}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                {session && !session.appointments.some((a) => a.status === 'confirmed') && (
                  <p className="empty-visits">
                    You have no upcoming appointments.
                    <br />
                    Confirmed visits will appear here.
                  </p>
                )}
                <span className="demo-note">Sample patient · appointments are simulated</span>
              </section>
              <section className="clinic-details">
                <span className="eyebrow">GOOD TO KNOW</span>
                <h2>Opening hours</h2>
                <div className="hours">
                  <Clock3 size={17} />
                  <div>
                    <span>Monday – Friday</span>
                    <strong>9:00 am – 6:00 pm</strong>
                  </div>
                </div>
                <div className="hours weekend">
                  <span />
                  <div>
                    <span>Saturday</span>
                    <strong>9:00 am – 1:00 pm</strong>
                  </div>
                </div>
                <p className="timezone-note">Closed on Sunday · All times in Beirut</p>
                <button
                  className="human-link"
                  disabled={busy || !session}
                  onClick={() => void send('I would like to speak with a human.')}
                >
                  <span>
                    Prefer a person?<strong>Ask the reception team</strong>
                  </span>
                  <ArrowUpRight size={20} />
                </button>
                {!!session?.handoffs && (
                  <p className="handoff-note">
                    Handoff recorded in this demo. No real team has been contacted.
                  </p>
                )}
              </section>
              <div className="agenda-bottom">
                <ShieldCheck size={18} />
                <p>
                  You’re always in control.
                  <br />
                  <span>Review every change before it happens.</span>
                </p>
              </div>
            </div>
          </aside>
        </div>
        <footer className="app-footer">
          <span>RECEPTION / CLINIKIT</span>
          <span>Appointment enquiries</span>
          <span>EXERCISE 01</span>
        </footer>
      </main>
      <dialog
        ref={modal}
        aria-label={
          dialog === 'decisions'
            ? 'Decision log'
            : dialog === 'reset'
              ? 'Start a new conversation'
              : 'About reception'
        }
        className={`modal ${dialog === 'decisions' ? 'log-modal' : ''}`}
        onCancel={() => setDialog(null)}
        onClick={(event) => {
          if (event.target === event.currentTarget) setDialog(null);
        }}
      >
        <div className="modal-top">
          <span className="eyebrow">
            {dialog === 'decisions'
              ? 'BEHIND THE CONVERSATION'
              : dialog === 'reset'
                ? 'START FRESH'
                : 'ABOUT RECEPTION'}
          </span>
          <button className="icon-button" aria-label="Close dialog" onClick={() => setDialog(null)}>
            <X size={20} />
          </button>
        </div>
        {dialog === 'decisions' && (
          <>
            <h2>Every decision, in the open.</h2>
            <p className="modal-intro">
              Structured extraction, policy checks, and actual mock tool results. This is an
              execution record, not the model’s private reasoning.
            </p>
            {selectedDecision ? (
              <>
                <button className="text-button back-link" onClick={() => setSelectedDecision(null)}>
                  ← All decisions
                </button>
                <DecisionDetails decision={selectedDecision} />
              </>
            ) : decisions.length ? (
              decisions.map((message, i) => (
                <details className="log-entry" key={message.id} open={i === decisions.length - 1}>
                  <summary>
                    <span>0{i + 1}</span>
                    {message.decision!.intent.replaceAll('_', ' ')}
                  </summary>
                  <DecisionDetails decision={message.decision!} />
                </details>
              ))
            ) : (
              <p className="empty-log">Send a message to see how reception handles it.</p>
            )}
          </>
        )}
        {dialog === 'about' && (
          <>
            <h2>About this demo</h2>
            <p>
              This is a prototype for Part 1 of the CliniKit AI trainee assessment. All clinic
              details, patient records, and appointments are fictional.
            </p>
            <h3>What reception can do</h3>
            <p>
              Reception can find appointment times, prepare a booking, reschedule or cancel a visit,
              explain opening hours, and record a mock request for a human.
            </p>
            <h3>{modeLabel}</h3>
            <p>
              {liveModel
                ? `Messages are interpreted by ${session?.model}. Python checks the clinic schedule, controls appointment changes, and writes replies from verified results. Sample conversation text is sent to ${session?.mode === 'gemini' ? 'Google Gemini' : 'OpenAI'}. Use fictional patient information only.`
                : 'The offline demo uses a limited rule-based interpreter. It makes no model API calls. Select and configure a live provider to evaluate language understanding.'}
            </p>
            <h3>How appointments are handled</h3>
            <p>
              React + TypeScript · Python + FastAPI. Appointment changes require an explicit
              confirmation tied to the exact proposed visit. Use the decision log to inspect the
              structured output and action.
            </p>
            <p className="demo-note">A scheduling demonstration, not a medical advice service.</p>
          </>
        )}
        {dialog === 'reset' && (
          <>
            <h2>A fresh conversation?</h2>
            <p>
              This opens a new sample patient session with the original fictional appointment. Your
              current conversation will leave this view.
            </p>
            <div className="confirmation-actions">
              <button
                className="primary-button"
                onClick={() => {
                  setDialog(null);
                  void start();
                }}
              >
                Start fresh
              </button>
              <button className="text-button" onClick={() => setDialog(null)}>
                Keep this conversation
              </button>
            </div>
          </>
        )}
      </dialog>
    </div>
  );
}
