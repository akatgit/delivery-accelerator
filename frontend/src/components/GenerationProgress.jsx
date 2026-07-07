import { useEffect, useState } from "react";
import { useSession } from "../context/SessionContext";

// GenerationProgress (ARCHITECTURE_v2.0.md section 11.1): per-artifact
// generation status, org standard sources per artifact, default warnings,
// prompt versions used (FR-4.5).
export default function GenerationProgress() {
  const { state, actions } = useSession();
  const { session, artifacts, loading } = state;
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    if (!session?.id) return undefined;
    actions.loadArtifacts(session.id);
    const interval = setInterval(() => actions.loadArtifacts(session.id), 3000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.id]);

  if (!session) return <p className="text-sm text-slate-500">Create a session first.</p>;
  if (loading.artifacts && artifacts.length === 0) return <p className="text-sm text-slate-500">Loading artifacts...</p>;
  if (artifacts.length === 0) return <p className="text-sm text-slate-500">No artifacts generated yet.</p>;

  const byType = artifacts.reduce((acc, artifact) => {
    (acc[artifact.type] ||= []).push(artifact);
    return acc;
  }, {});

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Generation progress</h2>
        <span className="text-sm text-slate-500">{artifacts.length} artifact(s)</span>
      </div>

      {Object.entries(byType).map(([type, items]) => (
        <section key={type}>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
            {type.replace(/_/g, " ")} ({items.length})
          </h3>
          <div className="space-y-2">
            {items.map((artifact) => {
              const standardRefs = artifact.derived_from.filter((ref) => ref.startsWith("standard:"));
              const isExpanded = expanded === artifact.filename;
              return (
                <div key={artifact.filename} className="rounded-md border bg-white p-3 text-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-mono text-xs text-slate-500">{artifact.filename}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-xs font-medium text-emerald-700">
                          generated
                        </span>
                        {artifact.used_default && (
                          <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-700">
                            default guidance (no org standard)
                          </span>
                        )}
                        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
                          prompt v{artifact.prompt_version}
                        </span>
                      </div>
                      {standardRefs.length > 0 && (
                        <p className="mt-1 text-xs text-slate-500">
                          Sourced from: {standardRefs.map((r) => r.replace("standard:", "")).join(", ")}
                        </p>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => setExpanded(isExpanded ? null : artifact.filename)}
                      className="shrink-0 rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-200"
                    >
                      {isExpanded ? "Hide" : "Preview"}
                    </button>
                  </div>
                  {isExpanded && (
                    <pre className="mt-2 max-h-64 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
                      {artifact.content}
                    </pre>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
