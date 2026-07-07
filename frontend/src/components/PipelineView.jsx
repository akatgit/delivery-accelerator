import { useSession } from "../context/SessionContext";

const REVIEW_DOMAINS = ["architecture", "security", "performance", "reliability", "compliance"];

// The 8-step stage indicator from ARCHITECTURE_v2.0.md section 11.1:
// "Upload -> Parse -> Review -> QA -> Approve -> Generate -> Scaffold -> Deliver".
const STEPS = [
  { key: "upload", label: "Upload", stages: [] },
  { key: "parse", label: "Parse", stages: ["document_parsing", "extraction_preview"] },
  { key: "review", label: "Review", stages: ["review_board", "review_aggregation"] },
  { key: "qa", label: "QA", stages: ["review_qa"] },
  { key: "approve", label: "Approve", stages: ["human_approval_review", "human_approval_final"] },
  { key: "generate", label: "Generate", stages: ["context_synthesis", "ai_development_setup"] },
  { key: "scaffold", label: "Scaffold", stages: ["consistency_check", "project_scaffolding"] },
  { key: "deliver", label: "Deliver", stages: ["completed"] },
];

function currentStepKey(stage, pausedAt) {
  if (pausedAt === "human_gate_1" || pausedAt === "human_gate_2") return "approve";
  const step = STEPS.find((s) => s.stages.includes(stage));
  return step ? step.key : "upload";
}

// Groups failed_components entries (e.g. "architecture:Completeness",
// "hook-config:lint rules") onto whichever stage step they belong to, using
// each component name's own naming convention (graph/nodes.py).
function failedSteps(failedComponents) {
  const failed = new Set();
  const reviewDomainFailures = [];
  for (const component of failedComponents) {
    const domain = REVIEW_DOMAINS.find((d) => component.startsWith(`${d}:`));
    if (domain) {
      failed.add("review");
      reviewDomainFailures.push(domain);
      continue;
    }
    if (["instruction-section", "skill-file", "hook-config", "prompt-entry", "tool-config"].some((p) => component.startsWith(p))) {
      failed.add("generate");
      continue;
    }
    if (["generate-folder-structure", "config-file", "pattern-sample"].some((p) => component.startsWith(p))) {
      failed.add("scaffold");
    }
  }
  return { failed, reviewDomainFailures };
}

// PipelineView (ARCHITECTURE_v2.0.md section 11.1): stage indicator with
// failed stages shown in red and a retry button (FR-2.9, reviewer domains only
// -- that's the one node the backend supports retrying in isolation).
export default function PipelineView() {
  const { state, actions } = useSession();
  const { session, status } = state;

  if (!session || !status) return null;

  const activeKey = currentStepKey(status.current_stage, status.paused_at);
  const { failed, reviewDomainFailures } = failedSteps(status.failed_components || []);

  async function handleRetry(domain) {
    await actions.retryDomain(session.id, domain);
    await actions.loadStatus(session.id);
    await actions.loadReview(session.id);
  }

  return (
    <div className="border-b bg-white px-6 py-4">
      <ol className="flex items-center gap-1 overflow-x-auto">
        {STEPS.map((step, i) => {
          const isFailed = failed.has(step.key);
          const isActive = step.key === activeKey;
          return (
            <li key={step.key} className="flex items-center">
              <div
                className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium whitespace-nowrap ${
                  isFailed
                    ? "bg-red-100 text-red-700"
                    : isActive
                    ? "bg-indigo-600 text-white"
                    : "bg-slate-100 text-slate-500"
                }`}
              >
                <span>{i + 1}.</span>
                <span>{step.label}</span>
              </div>
              {i < STEPS.length - 1 && <span className="mx-1 text-slate-300">→</span>}
            </li>
          );
        })}
      </ol>

      {reviewDomainFailures.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {reviewDomainFailures.map((domain) => (
            <button
              key={domain}
              type="button"
              onClick={() => handleRetry(domain)}
              className="rounded-md border border-red-300 bg-red-50 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-100"
            >
              Retry {domain} reviewer
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
