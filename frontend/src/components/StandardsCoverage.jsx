import { useEffect } from "react";
import { useSession } from "../context/SessionContext";

const ALL_CATEGORIES = [
  "coding",
  "security",
  "api_design",
  "naming",
  "logging",
  "exception_handling",
  "testing",
  "cicd",
  "repository_conventions",
  "organization_practices",
];

const STATUS_STYLES = {
  loaded: "border-emerald-300 bg-emerald-50 text-emerald-800",
  missing: "border-amber-300 bg-amber-50 text-amber-800",
  conflicting: "border-red-300 bg-red-50 text-red-800",
};

// StandardsCoverage (ARCHITECTURE_v2.0.md section 11.1): grid showing
// loaded/missing/conflicting categories (FR-1.9, FR-1.5).
export default function StandardsCoverage() {
  const { state, actions } = useSession();
  const { session, standardsCoverage, conflicts, loading } = state;

  useEffect(() => {
    if (session?.id) {
      actions.loadStandardsCoverage(session.id);
      actions.loadConflicts(session.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.id]);

  if (!session) {
    return <p className="text-sm text-slate-500">Create a session to see standards coverage.</p>;
  }

  const conflictingCategories = new Set(conflicts.filter((c) => !c.resolution).flatMap((c) => [c.category_a, c.category_b]));
  const loadedCategories = new Set(standardsCoverage?.loaded_categories || []);

  function statusFor(category) {
    if (conflictingCategories.has(category)) return "conflicting";
    if (loadedCategories.has(category)) return "loaded";
    return "missing";
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h2 className="mb-4 text-lg font-semibold text-slate-900">Standards coverage</h2>
      {loading.standardsCoverage && <p className="text-sm text-slate-500">Loading...</p>}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {ALL_CATEGORIES.map((category) => {
          const status = statusFor(category);
          return (
            <div key={category} className={`rounded-md border px-3 py-2 text-sm ${STATUS_STYLES[status]}`}>
              <p className="font-medium">{category.replace(/_/g, " ")}</p>
              <p className="text-xs uppercase tracking-wide opacity-80">{status}</p>
            </div>
          );
        })}
      </div>
      <div className="mt-4 flex gap-4 text-xs text-slate-500">
        <Legend color="bg-emerald-400" label="Loaded" />
        <Legend color="bg-amber-400" label="Missing" />
        <Legend color="bg-red-400" label="Conflicting (unresolved)" />
      </div>
    </div>
  );
}

function Legend({ color, label }) {
  return (
    <span className="flex items-center gap-1">
      <span className={`h-2 w-2 rounded-full ${color}`} />
      {label}
    </span>
  );
}
