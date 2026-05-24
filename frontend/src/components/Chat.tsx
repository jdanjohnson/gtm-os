import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import clsx from "clsx";
import { Send, Square, ChevronDown, Bot, User, Wrench } from "lucide-react";

import { PrimitivesSummary, streamChat } from "../lib/api";

interface Props {
  experimentId: string | null;
  primitives: PrimitivesSummary | null;
  defaultAgent?: string;
  onAgentChange?: (agent: string) => void;
  compact?: boolean;
}

interface UIMessage {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  tool_name?: string;
  ok?: boolean;
  pending?: boolean;
}

export default function Chat({ experimentId, primitives, defaultAgent, onAgentChange, compact }: Props) {
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [agent, setAgent] = useState<string>(defaultAgent ?? "orchestrator");
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (defaultAgent) setAgent(defaultAgent);
  }, [defaultAgent]);

  useEffect(() => {
    setThreadId(null);
    setMessages([]);
  }, [experimentId]);

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
            if (meta.agent) {
              setAgent(meta.agent);
              onAgentChange?.(meta.agent);
            }
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
                      "\n\n-> " +
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
      // handled in onError
    } finally {
      setStreaming(false);
    }
  }, [input, streaming, threadId, experimentId, agent, onAgentChange]);

  const stop = () => {
    abortRef.current?.abort();
    setStreaming(false);
  };

  return (
    <div className="flex h-full w-full flex-col">
      {/* Agent bar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-white/[0.06] text-[11px] text-slate-400">
        <div className="flex items-center gap-1.5">
          <Bot size={12} className="text-emerald-400" />
          <select
            value={agent}
            onChange={(e) => {
              setAgent(e.target.value);
              onAgentChange?.(e.target.value);
            }}
            className="glass-input !rounded-lg px-2 py-0.5 text-[11px] text-emerald-300 bg-transparent border-emerald-500/20"
          >
            {(primitives?.agents.length ? primitives.agents : ["orchestrator"]).map(
              (a) => (
                <option key={a} value={a}>{a}</option>
              ),
            )}
          </select>
        </div>
        <span className="text-slate-600">|</span>
        <span>
          {experimentId ? `exp: ${experimentId.slice(0, 8)}...` : "no experiment"}
        </span>
        {threadId && (
          <>
            <span className="text-slate-600">|</span>
            <span className="text-slate-500">thread: {threadId.slice(0, 10)}...</span>
          </>
        )}
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className={clsx("flex-1 overflow-y-auto px-4 py-4", compact && "px-4 py-3")}
      >
        {messages.length === 0 && (
          <div className="glass-card mx-auto max-w-xl p-5 text-center">
            <h2 className="mb-1.5 text-sm font-medium text-slate-200">
              Talk to your GTM team
            </h2>
            <p className="text-xs text-slate-400">
              Describe what you want them to do: run experiments, draft sequences, search memory, or analyze results.
            </p>
          </div>
        )}

        {messages.map((m) => (
          <Message key={m.id} m={m} compact={compact} />
        ))}
      </div>

      {/* Input */}
      <div className="border-t border-white/[0.06] px-4 py-3">
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
            rows={compact ? 1 : 2}
            className="glass-input flex-1 resize-none px-3 py-2 text-sm text-slate-100"
            disabled={streaming}
          />
          {streaming ? (
            <button
              onClick={stop}
              className="glass-btn-danger flex items-center gap-1.5 rounded-xl px-4 py-2 text-sm"
            >
              <Square size={14} />
            </button>
          ) : (
            <button
              onClick={send}
              disabled={!input.trim()}
              className="glass-btn flex items-center gap-1.5 rounded-xl px-4 py-2 text-sm disabled:opacity-30"
            >
              <Send size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Message({ m, compact }: { m: UIMessage; compact?: boolean }) {
  if (m.role === "tool") {
    return (
      <div className="mx-auto my-2 max-w-2xl glass-card !rounded-xl px-3 py-2 text-xs">
        <div className="flex items-center gap-2 text-slate-400">
          <Wrench size={10} />
          <span className="font-mono">
            {m.pending ? "..." : m.ok ? "done" : "failed"} {m.tool_name}
          </span>
        </div>
        <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap font-mono text-[10px] text-slate-500">
          {m.content}
        </pre>
      </div>
    );
  }

  if (m.role === "system") {
    return (
      <div className="mx-auto my-2 max-w-2xl rounded-xl border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-300">
        {m.content}
      </div>
    );
  }

  const isUser = m.role === "user";

  return (
    <div
      className={clsx(
        "mx-auto my-2 flex max-w-2xl",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      <div className="flex items-start gap-2">
        {!isUser && (
          <div className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400">
            <Bot size={12} />
          </div>
        )}
        <div
          className={clsx(
            "max-w-xl rounded-2xl px-4 py-2.5",
            isUser
              ? "glass border border-emerald-500/20 text-slate-100"
              : "glass text-slate-200",
            m.pending && "opacity-80",
          )}
        >
          <div className="prose-chat">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {m.content || (m.pending ? "..." : "")}
            </ReactMarkdown>
          </div>
        </div>
        {isUser && (
          <div className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-slate-700/50 text-slate-400">
            <User size={12} />
          </div>
        )}
      </div>
    </div>
  );
}
