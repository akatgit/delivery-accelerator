import { useEffect, useState } from "react";
import { useSession } from "../context/SessionContext";

const DOCUMENT_TYPES = [
  { key: "brd", label: "BRD" },
  { key: "architecture", label: "Architecture doc" },
  { key: "stories", label: "Stories" },
  { key: "tech_preferences", label: "Tech preferences" },
];

// UploadView (ARCHITECTURE_v2.0.md section 11.1): project docs + standards
// upload, standards coverage indicator, conflict display with resolution
// controls, and a session-reuse dropdown (FR-1.11).
export default function UploadView() {
  const { state, actions } = useSession();
  const { session, sessions, standardsCoverage, conflicts, loading } = state;

  const [projectName, setProjectName] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [uploadedDocs, setUploadedDocs] = useState({});
  const [reuseSourceId, setReuseSourceId] = useState("");
  const [resolutionDrafts, setResolutionDrafts] = useState({});

  useEffect(() => {
    actions.loadSessions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (session?.id) {
      actions.loadStandardsCoverage(session.id);
      actions.loadConflicts(session.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.id]);

  async function handleCreateSession(e) {
    e.preventDefault();
    await actions.createSession(projectName || "Untitled Project", projectDescription);
  }

  async function handleDocumentUpload(docType, file) {
    if (!file) return;
    await actions.uploadDocument(session.id, docType, file);
    setUploadedDocs((prev) => ({ ...prev, [docType]: file.name }));
  }

  async function handleStandardUpload(file) {
    if (!file) return;
    await actions.uploadStandard(session.id, file);
  }

  async function handleReuse() {
    if (!reuseSourceId) return;
    await actions.reuseStandards(session.id, reuseSourceId);
  }

  function updateDraft(conflict, field, value) {
    const key = `${conflict.category_a}:${conflict.category_b}`;
    setResolutionDrafts((prev) => ({ ...prev, [key]: { ...prev[key], [field]: value } }));
  }

  async function submitResolution(conflict) {
    const key = `${conflict.category_a}:${conflict.category_b}`;
    const draft = resolutionDrafts[key];
    if (!draft?.resolution) return;
    await actions.resolveConflicts(session.id, [
      { category_a: conflict.category_a, category_b: conflict.category_b, resolution: draft.resolution },
    ]);
  }

  async function handleStart() {
    await actions.startPipeline(session.id);
    await actions.loadStatus(session.id);
  }

  if (!session) {
    return (
      <div className="mx-auto max-w-md rounded-lg border bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">Start a new session</h2>
        <form onSubmit={handleCreateSession} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Project name</label>
            <input
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="Order Processing System"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Description</label>
            <textarea
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={projectDescription}
              onChange={(e) => setProjectDescription(e.target.value)}
              rows={3}
            />
          </div>
          <button
            type="submit"
            disabled={loading.createSession}
            className="w-full rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {loading.createSession ? "Creating..." : "Create session"}
          </button>
        </form>
      </div>
    );
  }

  const unresolvedConflicts = conflicts.filter((c) => !c.resolution);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <section className="rounded-lg border bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">Project documents</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {DOCUMENT_TYPES.map(({ key, label }) => (
            <div key={key}>
              <label className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
              <input
                type="file"
                accept=".md,.txt"
                onChange={(e) => handleDocumentUpload(key, e.target.files[0])}
                className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm"
              />
              {uploadedDocs[key] && <p className="mt-1 text-xs text-emerald-600">Uploaded: {uploadedDocs[key]}</p>}
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border bg-white p-6 shadow-sm">
        <h2 className="mb-2 text-lg font-semibold text-slate-900">Organization standards</h2>
        <input
          type="file"
          accept=".md,.txt"
          multiple
          onChange={(e) => Array.from(e.target.files).forEach(handleStandardUpload)}
          className="mb-4 block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm"
        />

        {sessions.length > 1 && (
          <div className="mb-4 flex items-center gap-2">
            <select
              className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              value={reuseSourceId}
              onChange={(e) => setReuseSourceId(e.target.value)}
            >
              <option value="">Reuse standards from a previous session...</option>
              {sessions.filter((s) => s.id !== session.id).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.project_name} ({s.created_at.slice(0, 10)})
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={handleReuse}
              disabled={!reuseSourceId}
              className="rounded-md bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-200 disabled:opacity-50"
            >
              Reuse
            </button>
          </div>
        )}

        {standardsCoverage && (
          <p className="mb-4 text-sm text-slate-600">
            <span className="font-medium text-emerald-600">{standardsCoverage.loaded_categories.length} loaded</span>
            {" · "}
            <span className="font-medium text-amber-600">{standardsCoverage.missing_categories.length} missing</span>
            {" — see the Standards tab for the full grid."}
          </p>
        )}

        {unresolvedConflicts.length > 0 && (
          <div className="space-y-3 rounded-md border border-amber-300 bg-amber-50 p-4">
            <p className="text-sm font-medium text-amber-800">
              {unresolvedConflicts.length} standard conflict(s) must be resolved or acknowledged before proceeding (FR-1.5).
            </p>
            {unresolvedConflicts.map((conflict) => {
              const key = `${conflict.category_a}:${conflict.category_b}`;
              return (
                <div key={key} className="rounded-md border border-amber-200 bg-white p-3 text-sm">
                  <p className="font-medium text-slate-800">
                    {conflict.category_a} vs {conflict.category_b}
                  </p>
                  <p className="mt-1 text-slate-600">{conflict.description}</p>
                  <ul className="mt-1 list-disc pl-5 text-slate-600">
                    <li>
                      <span className="font-medium">{conflict.category_a}:</span> {conflict.statement_a}
                    </li>
                    <li>
                      <span className="font-medium">{conflict.category_b}:</span> {conflict.statement_b}
                    </li>
                  </ul>
                  <div className="mt-2 flex gap-2">
                    <input
                      type="text"
                      placeholder="Which standard wins, or how this is acknowledged"
                      className="flex-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
                      value={resolutionDrafts[key]?.resolution || ""}
                      onChange={(e) => updateDraft(conflict, "resolution", e.target.value)}
                    />
                    <button
                      type="button"
                      onClick={() => submitResolution(conflict)}
                      className="rounded-md bg-amber-600 px-3 py-1 text-sm font-medium text-white hover:bg-amber-500"
                    >
                      Resolve
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <button
        type="button"
        onClick={handleStart}
        disabled={loading.startPipeline || unresolvedConflicts.length > 0}
        className="w-full rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
      >
        {loading.startPipeline ? "Starting..." : "Start pipeline"}
      </button>
    </div>
  );
}
