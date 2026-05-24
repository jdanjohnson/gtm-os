import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import clsx from "clsx";

import { PrimitivesSummary, streamChat } from "../lib/api";

interface Props {
  experimentId: string | null;
  primitives: PrimitivesSummary | null;
}

interface UIMessage {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  tool_name?: string;
  ok?: boolean;
  pending?: boolean;
}

export default function Chat({ experimentId, primitives }: Props) {
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [agent, setAgent] = useState<string>("orchestrator");
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // When experiment changes, reset thread so each experiment has its own conversation.
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
    } catch (err) {
      // already handled in onError
    } finally {
      setStreaming(false);
    }
  }, [input, streaming, threadId, experimentId, agent]);

  const stop = () => {
    abortRef.current?.abort();
    setStreaming(false);
  };

  return (
    <div className="flex h-full w-full flex-col">
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
