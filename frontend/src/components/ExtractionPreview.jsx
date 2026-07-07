import { useEffect } from "react";
import { useSession } from "../context/SessionContext";

const GAP_SEVERITY_STYLES = {
  critical: "border-red-300 bg-red-50 text-red-800",
  major: "border-amber-300 bg-amber-50 text-amber-800",
  informational: "border-slate-300 bg-slate-50 text-slate-700",
};

// ExtractionPreview (ARCHITECTURE_v2.0.md section 11.1): parsed
// ProjectContext verification -- tech stack, components, NFRs, stories, gaps.
export default function ExtractionPreview() {
  const { state, actions } = useSession();
  const { session, projectContext, loading } = state;

  useEffect(() => {
    if (session?.id) actions.loadExtraction(session.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.id]);

  if (!session) return <p className="text-sm text-slate-500">Create a session first.</p>;
  if (loading.extraction && !projectContext) return <p className="text-sm text-slate-500">Loading extraction...</p>;
  if (!projectContext) return <p className="text-sm text-slate-500">Extraction hasn't run yet.</p>;

  async function handleConfirm() {
    await actions.confirmExtraction(session.id);
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Extraction preview</h2>
        <button
          type="button"
          onClick={handleConfirm}
          disabled={loading.confirmExtraction}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {loading.confirmExtraction ? "Confirming..." : "Confirm extraction"}
        </button>
      </div>

      <Section title={`Tech stack (${projectContext.tech_stack.length})`}>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {projectContext.tech_stack.map((item, i) => (
            <div key={i} className="rounded-md border bg-white px-3 py-2 text-sm">
              <span className="font-medium">{item.technology}</span>
              {item.version && <span className="text-slate-500"> v{item.version}</span>}
              <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">{item.category}</span>
            </div>
          ))}
          {projectContext.tech_stack.length === 0 && <EmptyRow />}
        </div>
      </Section>

      <Section title={`Components (${projectContext.components.length})`}>
        <div className="space-y-2">
          {projectContext.components.map((component, i) => (
            <div key={i} className="rounded-md border bg-white p-3 text-sm">
              <p className="font-medium text-slate-900">
                {component.name} <span className="text-xs font-normal text-slate-500">({component.type})</span>
              </p>
              <p className="mt-1 text-slate-600">{component.description}</p>
              {component.dependencies.length > 0 && (
                <p className="mt-1 text-xs text-slate-500">Depends on: {component.dependencies.join(", ")}</p>
              )}
            </div>
          ))}
          {projectContext.components.length === 0 && <EmptyRow />}
        </div>
      </Section>

      <Section title={`Non-functional requirements (${projectContext.nfrs.length})`}>
        <div className="space-y-2">
          {projectContext.nfrs.map((nfr, i) => (
            <div key={i} className="rounded-md border bg-white p-3 text-sm">
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">{nfr.category}</span>
              <p className="mt-1 text-slate-700">{nfr.requirement}</p>
              {nfr.measurable && <p className="mt-1 text-xs text-emerald-600">Measurable</p>}
            </div>
          ))}
          {projectContext.nfrs.length === 0 && <EmptyRow />}
        </div>
      </Section>

      <Section title={`Stories (${projectContext.stories.length})`}>
        <div className="space-y-2">
          {projectContext.stories.map((story) => (
            <div key={story.id} className="rounded-md border bg-white p-3 text-sm">
              <p className="font-medium text-slate-900">
                {story.id}: {story.title}
              </p>
              <p className="mt-1 text-slate-600">{story.description}</p>
              <p className="mt-1 text-xs text-slate-500">Complexity: {story.estimated_complexity}</p>
            </div>
          ))}
          {projectContext.stories.length === 0 && <EmptyRow />}
        </div>
      </Section>

      <Section title={`Gaps (${projectContext.gaps.length})`}>
        <div className="space-y-2">
          {projectContext.gaps.map((gap, i) => (
            <div key={i} className={`rounded-md border p-3 text-sm ${GAP_SEVERITY_STYLES[gap.severity] || ""}`}>
              <p className="font-medium uppercase tracking-wide">{gap.severity}</p>
              <p className="mt-1">{gap.description}</p>
              {gap.suggestion && <p className="mt-1 text-xs opacity-80">Suggestion: {gap.suggestion}</p>}
            </div>
          ))}
          {projectContext.gaps.length === 0 && <EmptyRow />}
        </div>
      </Section>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section>
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      {children}
    </section>
  );
}

function EmptyRow() {
  return <p className="text-sm text-slate-400">None extracted.</p>;
}
