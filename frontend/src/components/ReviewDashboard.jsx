import { useEffect } from "react";
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Tooltip } from "recharts";
import { useSession } from "../context/SessionContext";

const SEVERITY_STYLES = {
  critical: "border-red-300 bg-red-50 text-red-800",
  major: "border-amber-300 bg-amber-50 text-amber-800",
  minor: "border-blue-300 bg-blue-50 text-blue-800",
  suggestion: "border-slate-300 bg-slate-50 text-slate-700",
};

// ReviewDashboard (ARCHITECTURE_v2.0.md section 11.1): radar chart of domain
// scores, overall + review quality score, QA-validated findings
// (deduplicated, contradictions highlighted, low-quality flagged), and
// per-finding accept/override toggles that stage into reviewDecisions
// (finalized with justification in ApprovalGate).
export default function ReviewDashboard() {
  const { state, actions } = useSession();
  const { session, review, reviewQuality, reviewDecisions, loading } = state;

  useEffect(() => {
    if (session?.id) {
      actions.loadReview(session.id);
      actions.loadReviewQuality(session.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.id]);

  if (!session) return <p className="text-sm text-slate-500">Create a session first.</p>;
  if (loading.review && !review) return <p className="text-sm text-slate-500">Loading review...</p>;
  if (!review) return <p className="text-sm text-slate-500">The review board hasn't completed yet.</p>;

  const radarData = review.reviews.map((r) => ({ domain: r.domain, score: r.score }));
  const qualityScore = reviewQuality?.review_qa?.quality_score;
  const contradictions = reviewQuality?.review_qa?.contradictions || [];
  const lowQualityIds = new Set(reviewQuality?.review_qa?.low_quality_findings || []);
  const contradictionFindingIds = new Set(contradictions.flatMap((c) => [c.finding_id_a, c.finding_id_b]));

  const overriddenIds = new Set(reviewDecisions.overrides.map((o) => o.finding_id));

  function toggleOverride(finding) {
    if (overriddenIds.has(finding.id)) {
      actions.clearFindingOverride(finding.id);
    } else {
      actions.setFindingOverride({ finding_id: finding.id, justification: "", confirmed: false });
    }
  }

  const findingsBySeverity = { critical: [], major: [], minor: [], suggestion: [] };
  for (const finding of review.findings) {
    (findingsBySeverity[finding.severity] || findingsBySeverity.suggestion).push(finding);
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <div className="rounded-lg border bg-white p-4 shadow-sm">
          <h3 className="mb-2 text-sm font-semibold text-slate-500">Domain scores</h3>
          <ResponsiveContainer width="100%" height={260}>
            <RadarChart data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="domain" tick={{ fontSize: 11 }} />
              <PolarRadiusAxis angle={30} domain={[0, 10]} />
              <Radar name="Score" dataKey="score" stroke="#4f46e5" fill="#4f46e5" fillOpacity={0.4} />
              <Tooltip />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div className="flex flex-col justify-center gap-4 rounded-lg border bg-white p-6 shadow-sm">
          <ScoreStat
            label="Overall score"
            value={review.overall_score != null ? review.overall_score.toFixed(1) : "—"}
            passed={review.threshold_passed}
          />
          <ScoreStat label="Review quality score" value={qualityScore != null ? `${qualityScore}/10` : "—"} />
          {review.remediation_summary && <p className="text-sm text-slate-600">{review.remediation_summary}</p>}
        </div>
      </div>

      {contradictions.length > 0 && (
        <div className="rounded-lg border border-purple-300 bg-purple-50 p-4">
          <h3 className="mb-2 text-sm font-semibold text-purple-800">
            {contradictions.length} contradiction(s) need resolution — see the Approval step below.
          </h3>
          <ul className="space-y-1 text-sm text-purple-700">
            {contradictions.map((c) => (
              <li key={`${c.finding_id_a}-${c.finding_id_b}`}>
                <span className="font-medium">{c.domain_a}</span> ({c.finding_id_a}) vs{" "}
                <span className="font-medium">{c.domain_b}</span> ({c.finding_id_b}): {c.description}
              </li>
            ))}
          </ul>
        </div>
      )}

      {["critical", "major", "minor", "suggestion"].map((severity) => {
        const findings = findingsBySeverity[severity];
        if (findings.length === 0) return null;
        return (
          <section key={severity}>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
              {severity} ({findings.length})
            </h3>
            <div className="space-y-2">
              {findings.map((finding) => {
                const isOverridden = overriddenIds.has(finding.id);
                const isContradiction = contradictionFindingIds.has(finding.id);
                const isLowQuality = lowQualityIds.has(finding.id);
                return (
                  <div key={finding.id} className={`rounded-md border p-3 text-sm ${SEVERITY_STYLES[severity]}`}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium text-slate-900">{finding.title}</p>
                        <p className="mt-1 text-slate-700">{finding.description}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          Affects: {finding.affected_components.join(", ") || "—"}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">Recommendation: {finding.recommendation}</p>
                        <p className="mt-1 text-xs text-slate-400">Based on: {finding.based_on}</p>
                        <div className="mt-2 flex flex-wrap gap-1">
                          {finding.contributing_domains?.length > 1 && (
                            <Badge color="bg-indigo-100 text-indigo-700">
                              merged from {finding.contributing_domains.join(", ")}
                            </Badge>
                          )}
                          {isContradiction && <Badge color="bg-purple-100 text-purple-700">contradiction</Badge>}
                          {isLowQuality && <Badge color="bg-orange-100 text-orange-700">low quality</Badge>}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => toggleOverride(finding)}
                        className={`shrink-0 rounded-md px-3 py-1 text-xs font-medium ${
                          isOverridden
                            ? "bg-red-600 text-white hover:bg-red-500"
                            : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                        }`}
                      >
                        {isOverridden ? "Overridden" : "Accept"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        );
      })}
      {review.findings.length === 0 && <p className="text-sm text-slate-400">No findings.</p>}
    </div>
  );
}

function ScoreStat({ label, value, passed }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="text-3xl font-semibold text-slate-900">{value}</p>
      {passed !== undefined && (
        <p className={`text-xs font-medium ${passed ? "text-emerald-600" : "text-red-600"}`}>
          {passed ? "Meets the 6.0 threshold" : "Below the 6.0 threshold"}
        </p>
      )}
    </div>
  );
}

function Badge({ color, children }) {
  return <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${color}`}>{children}</span>;
}
