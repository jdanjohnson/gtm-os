import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import clsx from "clsx";

import { PrimitivesSummary, streamChat } from "../lib/api";

interface Props {
  experimentId: string | null;
  primitives: PrimitivesSummary | null;
  experimentNames?: Record<string, string>;
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

  useEffect(() => {
    if (prevExpRef.current === experimentId) return;
    saveCurrentSession();
    const key = sessionKey(experimentId);
    const cached = sessionsRef.current.get(key);
    if (cached) {
      setMessages(cached.messages);
      setThreadId(cached.threadId);
      setAgent(cached.agent);
      sessionsRef.current.set(key, { ...cached, unread: 0 });
    } else {
      setMessages([]);
      setThreadId(null);
      setAgent("orchestrator");
    }
    prevExpRef.current = experimentId;
    forceRender((n) => n + 1);
  }, [experimentId, saveCurrentSession]);

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

  const closeSession = (key: string) => {
    sessionsRef.current.delete(key);
    if (key === sessionKey(experimentId)) {
      onSwitchExperiment?.(null);
    }
    forceRender((n) => n + 1);
  };

  const activeSessionKeys = Array.from(sessionsRef.current.keys());
  const currentKey = sessionKey(experimentId);
  if (!activeSessionKeys.includes(currentKey)) {
    activeSessionKeys.unshift(currentKey);
  }

  return (
    <div className="flex h-full w-full flex-col">
      {/* Session tab strip */}
      {activeSessionKeys.length > 0 && (
        <div className="flex items-center gap-0.5 overflow-x-auto border-b border-black/[0.05] px-2 py-1">
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
                  "group relative flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs transition-all",
                  isActive
                    ? "glass-heavy text-gray-900 font-semibold"
                    : "text-gray-400 hover:bg-black/[0.04] hover:text-gray-700",
                )}
              >
                <span className={clsx(
                  "inline-block h-1.5 w-1.5 rounded-full",
                  isGeneral ? "bg-blue-500" : "bg-emerald-500",
                )} />
                <span className="max-w-[120px] truncate">{expName}</span>
                {unread > 0 && !isActive && (
                  <span className="ml-0.5 rounded-full bg-coral px-1.5 py-0.5 text-[9px] font-bold leading-none text-white">
                    {unread}
                  </span>
                )}
                {session && session.messages.length > 0 && (
                  <span
                    onClick={(e) => {
                      e.stopPropagation();
                      closeSession(key);
                    }}
                    className="ml-0.5 hidden rounded p-0.5 text-gray-400 hover:bg-black/[0.06] hover:text-gray-700 group-hover:inline-block"
                  >
                    ✕
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Agent selector */}
      <div className="flex items-center gap-2 border-b border-black/[0.05] px-3 py-1.5 text-xs text-gray-500">
        <span>Agent:</span>
        <select
          value={agent}
          onChange={(e) => setAgent(e.target.value)}
          className="rounded-lg bg-black/[0.04] px-2 py-1 text-gray-700 outline-none"
        >
          {(primitives?.agents.length ? primitives.agents : ["orchestrator"]).map(
            (a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ),
          )}
        </select>
        {experimentId && (
          <span className="ml-auto text-[10px] text-gray-400">
            exp: {experimentId.slice(0, 8)}…
          </span>
        )}
      </div>

      {/* Messages area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 py-4"
      >
        {messages.length === 0 && (
          <div className="glass-heavy rounded-2xl p-5 text-sm">
            <h2 className="mb-2 text-base font-semibold text-gray-900">
              Talk to your GTM team.
            </h2>
            <p className="mb-2 text-xs text-gray-500">Examples:</p>
            <ul className="ml-4 list-disc text-xs text-gray-500">
              <li>Find 20 e-commerce founders on Apollo and send my pitch.</li>
              <li>Set up a weekly cold outbound experiment.</li>
              <li>Search memory for what worked with dev tools.</li>
            </ul>
          </div>
        )}

        {messages.map((m) => (
          <Message key={m.id} m={m} />
        ))}
      </div>

      {/* Input area */}
      <div className="border-t border-black/[0.05] px-3 py-3">
        <div className="flex items-center gap-2 rounded-full glass-heavy px-4 py-1">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="Ask me anything..."
            rows={1}
            className="flex-1 resize-none bg-transparent py-2 text-[12.5px] outline-none placeholder-gray-400"
            disabled={streaming}
          />
          {streaming ? (
            <button
              onClick={stop}
              className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-full bg-red-500 text-white transition hover:bg-red-600"
            >
              ■
            </button>
          ) : (
            <button
              onClick={send}
              disabled={!input.trim()}
              className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-full bg-coral text-white shadow-[0_2px_8px_rgba(239,99,68,0.3)] transition hover:bg-coral-hover disabled:opacity-40"
            >
              ↑
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
      <div className="my-2 rounded-xl glass-subtle px-3 py-2 text-xs text-gray-500">
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
      <div className="my-2 rounded-xl border border-amber-400/20 bg-amber-50 px-3 py-2 text-xs text-amber-700">
        {m.content}
      </div>
    );
  }

  return (
    <div
      className={clsx(
        "my-2 flex",
        m.role === "user" ? "justify-end" : "justify-start",
      )}
    >
      <div className="flex gap-2 max-w-[92%]">
        {m.role === "assistant" && (
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-coral to-[#FF8A65] text-[11px] font-bold text-white">
            G
          </div>
        )}
        <div>
          <div
            className={clsx(
              "rounded-2xl px-3.5 py-2.5",
              m.role === "user"
                ? "bg-coral text-white shadow-[0_2px_8px_rgba(239,99,68,0.25)]"
                : "glass-heavy text-gray-900",
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
        {m.role === "user" && (
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-500/10 text-[11px] font-bold text-blue-600">
            J
          </div>
        )}
      </div>
    </div>
  );
}
