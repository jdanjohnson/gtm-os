import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import clsx from "clsx";

import { PrimitivesSummary, streamChat } from "../lib/api";

interface Props {
  experimentId: string | null;
  primitives: PrimitivesSummary | null;
  /** Map of experiment IDs to names for display in session tabs. */
  experimentNames?: Record<string, string>;
  /** Called when user clicks a session tab for a different experiment. */
  onSwitchExperiment?: (id: string | null) => void;
}

interface UIMessage {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  tool_name?: string;
  ok?: boolean;
  pending?: boolean;
}

interface ChatSession {
  messages: UIMessage[];
  threadId: string | null;
  agent: string;
  unread: number;
}

const GENERAL_KEY = "__general__";

function sessionKey(experimentId: string | null): string {
  return experimentId ?? GENERAL_KEY;
}

function emptySession(): ChatSession {
  return { messages: [], threadId: null, agent: "orchestrator", unread: 0 };
}

export default function Chat({
  experimentId,
  primitives,
  experimentNames,
  onSwitchExperiment,
}: Props) {
  const sessionsRef = useRef<Map<string, ChatSession>>(new Map());
  const prevExpRef = useRef<string | null>(experimentId);
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [agent, setAgent] = useState<string>("orchestrator");
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [, forceRender] = useState(0);

  // Save current session to the cache.
  const saveCurrentSession = useCallback(() => {
    const key = sessionKey(prevExpRef.current);
    const current = sessionsRef.current.get(key) ?? emptySession();
    sessionsRef.current.set(key, {
      ...current,
      messages,
      threadId,
      agent,
    });
  }, [messages, threadId, agent]);

  // When experiment changes, save current session and restore (or create) the target.
  useEffect(() => {
    if (prevExpRef.current === experimentId) return;

    // Save outgoing session.
    saveCurrentSession();

    // Restore or init incoming session.
    const key = sessionKey(experimentId);
    const cached = sessionsRef.current.get(key);
    if (cached) {
      setMessages(cached.messages);
      setThreadId(cached.threadId);
      setAgent(cached.agent);
      // Clear unread when switching to this session.
      sessionsRef.current.set(key, { ...cached, unread: 0 });
    } else {
      setMessages([]);
      setThreadId(null);
      setAgent("orchestrator");
    }

    prevExpRef.current = experimentId;
    forceRender((n) => n + 1);
  }, [experimentId, saveCurrentSession]);

  // Auto-save session periodically so the ref stays up-to-date.
  useEffect(() => {
    const key = sessionKey(experimentId);
    const current = sessionsRef.current.get(key) ?? emptySession();
    sessionsRef.current.set(key, {
      ...current,
      messages,
      threadId,
      agent,
      unread: current.unread,
    });
  }, [messages, threadId, agent, experimentId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const send = useCallback(async () => {
    if (!input.trim() || streaming) return;
    const userMsg: UIMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: input,
    };
    const placeholder: UIMessage = {
      id: `a-${Date.now()}`,
      role: "assistant",
      content: "",
      pending: true,
    };
    setMessages((m) => [...m, userMsg, placeholder]);
    const userText = input;
    setInput("");
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat(
        {
          message: userText,
          thread_id: threadId,
          experiment_id: experimentId,
          agent,
        },
        {
          onMeta: (meta) => {
            setThreadId(meta.thread_id);
            if (meta.agent) setAgent(meta.agent);
          },
          onToken: (t) => {
            setMessages((curr) => {
              const next = curr.slice();
              const idx = next.findLastIndex(
                (m) => m.role === "assistant" && m.pending,
              );
              if (idx === -1) return next;
              next[idx] = {
                ...next[idx],
                content: next[idx].content + t,
              };
              return next;
            });
          },
          onToolCall: (name, args) => {
            setMessages((curr) => [
              ...curr,
              {
                id: `tc-${Date.now()}-${name}`,
                role: "tool",
                content: JSON.stringify(args, null, 2),
                tool_name: name,
                pending: true,
              },
            ]);
          },
          onToolResult: (name, ok, result) => {
            setMessages((curr) => {
              const next = curr.slice();
              for (let i = next.length - 1; i >= 0; i--) {
                if (next[i].role === "tool" && next[i].tool_name === name && next[i].pending) {
                  next[i] = {
                    ...next[i],
                    content:
                      next[i].content +
                      "\n\n→ " +
                      JSON.stringify(result, null, 2).slice(0, 2000),
                    ok,
                    pending: false,
                  };
                  return next;
                }
              }
              next.push({
                id: `tr-${Date.now()}-${name}`,
                role: "tool",
                content: JSON.stringify(result, null, 2),
                tool_name: name,
                ok,
              });
              return next;
            });
          },
          onFinal: ({ message }) => {
            setMessages((curr) => {
              const next = curr.slice();
              const idx = next.findLastIndex(
                (m) => m.role === "assistant" && m.pending,
              );
              if (idx === -1) return next;
              next[idx] = {
                ...next[idx],
                content: message || next[idx].content,
                pending: false,
              };
              return next;
            });
          },
          onError: (err) => {
            setMessages((curr) => [
              ...curr,
              {
                id: `e-${Date.now()}`,
                role: "system",
                content: "Error: " + err,
              },
            ]);
          },
        },
        controller.signal,
      );
    } catch {
      // already handled in onError
    } finally {
      setStreaming(false);
    }
  }, [input, streaming, threadId, experimentId, agent]);

  const stop = () => {
    abortRef.current?.abort();
    setStreaming(false);
  };

  // Close a session tab.
  const closeSession = (key: string) => {
    sessionsRef.current.delete(key);
    // If closing the currently active session, switch to general.
    if (key === sessionKey(experimentId)) {
      onSwitchExperiment?.(null);
    }
    forceRender((n) => n + 1);
  };

  // Build the list of active session keys for the tab strip.
  const activeSessionKeys = Array.from(sessionsRef.current.keys());
  // Always ensure current session is in the list.
  const currentKey = sessionKey(experimentId);
  if (!activeSessionKeys.includes(currentKey)) {
    activeSessionKeys.unshift(currentKey);
  }

  return (
    <div className="flex h-full w-full flex-col">
      {/* Session tab strip */}
      {activeSessionKeys.length > 0 && (
        <div className="flex items-center gap-0.5 overflow-x-auto border-b border-slate-800 bg-slate-900/60 px-2 py-1">
          {activeSessionKeys.map((key) => {
            const isActive = key === currentKey;
            const session = sessionsRef.current.get(key);
            const unread = session?.unread ?? 0;
            const isGeneral = key === GENERAL_KEY;
            const expName = isGeneral
              ? "General"
              : experimentNames?.[key] ?? `${key.slice(0, 8)}…`;
            return (
              <button
                key={key}
                onClick={() => {
                  if (!isActive) {
                    onSwitchExperiment?.(isGeneral ? null : key);
                  }
                }}
                className={clsx(
                  "group relative flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs transition-all",
                  isActive
                    ? "bg-slate-700/80 text-slate-100"
                    : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200",
                )}
              >
                <span className={clsx(
                  "inline-block h-1.5 w-1.5 rounded-full",
                  isGeneral ? "bg-blue-400" : "bg-emerald-400",
                )} />
                <span className="max-w-[120px] truncate">{expName}</span>
                {unread > 0 && !isActive && (
                  <span className="ml-0.5 rounded-full bg-emerald-500 px-1.5 py-0.5 text-[9px] font-bold leading-none text-white">
                    {unread}
                  </span>
                )}
                {session && session.messages.length > 0 && (
                  <span
                    onClick={(e) => {
                      e.stopPropagation();
                      closeSession(key);
                    }}
                    className="ml-0.5 hidden rounded p-0.5 text-slate-500 hover:bg-slate-600 hover:text-slate-200 group-hover:inline-block"
                  >
                    ✕
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Agent selector + context info */}
      <div className="flex items-center gap-2 border-b border-slate-800 px-4 py-2 text-xs text-slate-400">
        <span>agent:</span>
        <select
          value={agent}
          onChange={(e) => setAgent(e.target.value)}
          className="rounded bg-slate-800 px-2 py-1 text-slate-100"
        >
          {(primitives?.agents.length ? primitives.agents : ["orchestrator"]).map(
            (a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ),
          )}
        </select>
        <span className="ml-3">
          {experimentId ? `experiment: ${experimentId.slice(0, 8)}…` : "no experiment selected"}
        </span>
        <span className="ml-3">
          {threadId ? `thread: ${threadId.slice(0, 12)}…` : ""}
        </span>
      </div>

      {/* Messages area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-6 py-6"
      >
        {messages.length === 0 && (
          <div className="mx-auto max-w-2xl rounded-xl border border-slate-800 bg-slate-900/40 p-6 text-sm text-slate-300">
            <h2 className="mb-2 text-lg font-semibold text-slate-100">
              You're talking to your GTM team.
            </h2>
            <p className="mb-2">
              Describe what you want them to do. Examples:
            </p>
            <ul className="ml-4 list-disc text-slate-400">
              <li>Find 20 e-commerce founders on Apollo who use Shopify and send them my pitch.</li>
              <li>Set up a weekly experiment to email new prospects with the b2b-emailing play.</li>
              <li>Search memory for what worked when we sold to dev tools last month.</li>
            </ul>
          </div>
        )}

        {messages.map((m) => (
          <Message key={m.id} m={m} />
        ))}
      </div>

      {/* Input area */}
      <div className="border-t border-slate-800 bg-slate-900/30 px-6 py-4">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="What should the team do next?"
            rows={2}
            className="flex-1 resize-none rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm outline-none focus:border-emerald-500"
            disabled={streaming}
          />
          {streaming ? (
            <button
              onClick={stop}
              className="rounded-lg bg-rose-700 px-4 py-2 text-sm font-medium hover:bg-rose-600"
            >
              Stop
            </button>
          ) : (
            <button
              onClick={send}
              disabled={!input.trim()}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium hover:bg-emerald-500 disabled:opacity-40"
            >
              Send
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Message({ m }: { m: UIMessage }) {
  if (m.role === "tool") {
    return (
      <div className="mx-auto my-2 max-w-3xl rounded border border-slate-800 bg-slate-900/30 px-3 py-2 text-xs text-slate-400">
        <div className="flex items-center justify-between">
          <span className="font-mono">
            {m.pending ? "→" : m.ok ? "✓" : "✗"} {m.tool_name}
          </span>
        </div>
        <pre className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap font-mono text-[11px]">
          {m.content}
        </pre>
      </div>
    );
  }

  if (m.role === "system") {
    return (
      <div className="mx-auto my-2 max-w-3xl rounded border border-amber-900/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
        {m.content}
      </div>
    );
  }

  return (
    <div
      className={clsx(
        "mx-auto my-3 flex max-w-3xl",
        m.role === "user" ? "justify-end" : "justify-start",
      )}
    >
      <div
        className={clsx(
          "max-w-2xl rounded-xl px-4 py-3",
          m.role === "user"
            ? "bg-emerald-700/60 text-slate-50"
            : "bg-slate-900 text-slate-100",
          m.pending && "opacity-90",
        )}
      >
        <div className="prose-chat">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {m.content || (m.pending ? "…" : "")}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
