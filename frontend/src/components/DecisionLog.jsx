import { useEffect, useState } from "react";
import { useSession } from "../context/SessionContext";

// DecisionLog (ARCHITECTURE_v2.0.md section 11.1): timeline with agent,
// skill, prompt version, decision, rationale, standard references (FR-6.2).
export default function DecisionLog() {
  const { state, actions } = useSession();
  const { session, decisionLog, loading } = state;
  const [agentFilter, setAgentFilter] = useState("all");

  useEffect(() => {
    if (session?.id) actions.loadDecisionLog(session.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.id]);

  if (!session) return <p className="text-sm text-slate-500">Create a session first.</p>;
  if (loading.decisionLog && decisionLog.length === 0) return <p className="text-sm text-slate-500">Loading...</p>;
  if (decisionLog.length === 0) return <p className="text-sm text-slate-500">No decisions logged yet.</p>;

  const agents = ["all", ...new Set(decisionLog.map((e) => e.agent))];
  const entries = decisionLog
    .filter((e) => agentFilter === "all" || e.agent === agentFilter)
    .slice()
    .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Decision log ({entries.length})</h2>
        <select
          className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          value={agentFilter}
          onChange={(e) => setAgentFilter(e.target.value)}
        >
          {agents.map((agent) => (
            <option key={agent} value={agent}>
              {agent}
            </option>
          ))}
        </select>
      </div>

      <ol className="relative space-y-4 border-l border-slate-200 pl-4">
        {entries.map((entry, i) => (
          <li key={i} className="relative">
            <span className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full bg-indigo-500" />
            <div className="rounded-md border bg-white p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span>{new Date(entry.timestamp).toLocaleString()}</span>
                <span className="rounded bg-slate-100 px-1.5 py-0.5 font-medium text-slate-700">{entry.agent}</span>
                {entry.skill && <span className="rounded bg-blue-100 px-1.5 py-0.5 text-blue-700">{entry.skill}</span>}
                {entry.prompt_version && (
                  <span className="rounded bg-slate-100 px-1.5 py-0.5">prompt v{entry.prompt_version}</span>
                )}
              </div>
              <p className="mt-1 font-medium text-slate-900">{entry.decision}</p>
              <p className="mt-1 text-slate-600">{entry.rationale}</p>
              {entry.standard_refs?.length > 0 && (
                <p className="mt-1 text-xs text-slate-500">Standards: {entry.standard_refs.join(", ")}</p>
              )}
              {entry.context_refs?.length > 0 && (
                <p className="mt-1 text-xs text-slate-400">Context: {entry.context_refs.join(", ")}</p>
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
