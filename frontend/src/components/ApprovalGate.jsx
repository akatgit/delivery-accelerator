import { useState } from "react";
import { useSession } from "../context/SessionContext";

const MIN_JUSTIFICATION_LENGTH = 20;
const MAX_REVIEW_ITERATIONS = 5;

// ApprovalGate (ARCHITECTURE_v2.0.md section 11.1): finding action controls,
// contradiction resolution (choose recommendation A or B with rationale),
// override justification modal, iteration counter. Mirrors human_gate_1's
// two-phase design (graph/nodes.py): contradictions can be resolved first,
// independently, before the terminal accept/override/revise decision.
export default function ApprovalGate({ gate }) {
  const { state, actions } = useSession();
  const { session, review, reviewQuality, reviewDecisions, status } = state;
  const [revising, setRevising] = useState(false);
  const [reviseJustification, setReviseJustification] = useState("");

  if (!session) return null;

  const findingsById = new Map((review?.findings || []).map((f) => [f.id, f]));
  const contradictions = (reviewQuality?.review_qa?.contradictions || []).filter((c) => !c.resolution);

  async function refreshAfterDecision() {
    await actions.loadStatus(session.id);
    if (gate === "human_gate_1") {
      await actions.loadReview(session.id);
      await actions.loadReviewQuality(session.id);
    }
  }

  async function handleAcceptAll() {
    await actions.approve(session.id, "accept");
    await refreshAfterDecision();
  }

  async function handleSubmitOverrides() {
    const overrides = reviewDecisions.overrides.map((o) => ({
      finding_id: o.finding_id,
      justification: o.justification,
      confirmed: o.confirmed,
    }));
    await actions.approve(session.id, "override", { overrides });
    await refreshAfterDecision();
  }

  async function handleRevise() {
    const action = gate === "human_gate_1" ? "revise" : "revise";
    await actions.approve(session.id, action, { justification: reviseJustification });
    setRevising(false);
    setReviseJustification("");
    await refreshAfterDecision();
  }

  async function handleResolveContradiction(contradiction, chosenId, rationale) {
    await actions.approve(session.id, "resolve_contradiction", {
      contradiction_resolutions: [
        {
          finding_id_a: contradiction.finding_id_a,
          finding_id_b: contradiction.finding_id_b,
          chosen_finding_id: chosenId,
          rationale,
        },
      ],
    });
    await refreshAfterDecision();
  }

  const overridesValid = reviewDecisions.overrides.every((o) => {
    const finding = findingsById.get(o.finding_id);
    const justificationOk = (o.justification || "").length >= MIN_JUSTIFICATION_LENGTH;
    const confirmationOk = finding?.severity !== "critical" || o.confirmed;
    return justificationOk && confirmationOk;
  });

  return (
    <div className="rounded-lg border-2 border-indigo-200 bg-indigo-50/40 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-slate-900">
          {gate === "human_gate_1" ? "Review approval" : "Scaffolding approval"}
        </h3>
        {status && (
          <span className="text-sm text-slate-500">
            Iteration {status.review_iteration} / {MAX_REVIEW_ITERATIONS}
          </span>
        )}
      </div>

      {gate === "human_gate_1" && contradictions.length > 0 && (
        <div className="mb-6 space-y-3">
          <p className="text-sm font-medium text-slate-700">Resolve contradictions first</p>
          {contradictions.map((c) => (
            <ContradictionResolver
              key={`${c.finding_id_a}-${c.finding_id_b}`}
              contradiction={c}
              onResolve={handleResolveContradiction}
            />
          ))}
        </div>
      )}

      {gate === "human_gate_1" && reviewDecisions.overrides.length > 0 && (
        <div className="mb-6 space-y-3">
          <p className="text-sm font-medium text-slate-700">Justify overrides</p>
          {reviewDecisions.overrides.map((o) => (
            <OverrideForm key={o.finding_id} override={o} finding={findingsById.get(o.finding_id)} />
          ))}
        </div>
      )}

      {revising ? (
        <div className="space-y-2">
          <textarea
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            rows={3}
            placeholder="Why does this need another pass?"
            value={reviseJustification}
            onChange={(e) => setReviseJustification(e.target.value)}
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleRevise}
              disabled={status && status.review_iteration >= MAX_REVIEW_ITERATIONS}
              className="rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-500 disabled:opacity-50"
            >
              Submit revision request
            </button>
            <button
              type="button"
              onClick={() => setRevising(false)}
              className="rounded-md bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200"
            >
              Cancel
            </button>
          </div>
          {status && status.review_iteration >= MAX_REVIEW_ITERATIONS && (
            <p className="text-xs text-red-600">Maximum of {MAX_REVIEW_ITERATIONS} revise iterations reached.</p>
          )}
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {reviewDecisions.overrides.length > 0 ? (
            <button
              type="button"
              onClick={handleSubmitOverrides}
              disabled={!overridesValid}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              Submit with {reviewDecisions.overrides.length} override(s)
            </button>
          ) : (
            <button
              type="button"
              onClick={handleAcceptAll}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
            >
              Accept all
            </button>
          )}
          <button
            type="button"
            onClick={() => setRevising(true)}
            className="rounded-md bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200"
          >
            {gate === "human_gate_1" ? "Revise & re-review" : "Reject scaffolding"}
          </button>
        </div>
      )}
    </div>
  );
}

function ContradictionResolver({ contradiction, onResolve }) {
  const [chosen, setChosen] = useState(null);
  const [rationale, setRationale] = useState("");
  const valid = chosen && rationale.length >= MIN_JUSTIFICATION_LENGTH;

  return (
    <div className="rounded-md border border-purple-300 bg-white p-3 text-sm">
      <p className="text-slate-700">{contradiction.description}</p>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          onClick={() => setChosen(contradiction.finding_id_a)}
          className={`flex-1 rounded-md border px-3 py-2 text-left text-xs ${
            chosen === contradiction.finding_id_a ? "border-purple-500 bg-purple-50" : "border-slate-200"
          }`}
        >
          <span className="font-medium">A: {contradiction.domain_a}</span> ({contradiction.finding_id_a})
        </button>
        <button
          type="button"
          onClick={() => setChosen(contradiction.finding_id_b)}
          className={`flex-1 rounded-md border px-3 py-2 text-left text-xs ${
            chosen === contradiction.finding_id_b ? "border-purple-500 bg-purple-50" : "border-slate-200"
          }`}
        >
          <span className="font-medium">B: {contradiction.domain_b}</span> ({contradiction.finding_id_b})
        </button>
      </div>
      <textarea
        className="mt-2 w-full rounded-md border border-slate-300 px-2 py-1 text-xs"
        rows={2}
        placeholder="Rationale (min 20 characters)"
        value={rationale}
        onChange={(e) => setRationale(e.target.value)}
      />
      <button
        type="button"
        disabled={!valid}
        onClick={() => onResolve(contradiction, chosen, rationale)}
        className="mt-2 rounded-md bg-purple-600 px-3 py-1 text-xs font-medium text-white hover:bg-purple-500 disabled:opacity-50"
      >
        Submit resolution
      </button>
    </div>
  );
}

function OverrideForm({ override, finding }) {
  const { actions } = useSession();
  const isCritical = finding?.severity === "critical";

  function update(field, value) {
    actions.setFindingOverride({ ...override, [field]: value });
  }

  return (
    <div className="rounded-md border border-red-300 bg-white p-3 text-sm">
      <p className="font-medium text-slate-900">{finding?.title || override.finding_id}</p>
      <textarea
        className="mt-2 w-full rounded-md border border-slate-300 px-2 py-1 text-xs"
        rows={2}
        placeholder={`Justification (min ${MIN_JUSTIFICATION_LENGTH} characters)`}
        value={override.justification}
        onChange={(e) => update("justification", e.target.value)}
      />
      {isCritical && (
        <label className="mt-2 flex items-center gap-2 text-xs text-red-700">
          <input
            type="checkbox"
            checked={override.confirmed}
            onChange={(e) => update("confirmed", e.target.checked)}
          />
          I confirm overriding this critical finding
        </label>
      )}
    </div>
  );
}
