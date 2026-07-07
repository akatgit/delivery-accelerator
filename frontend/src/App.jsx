import { useEffect, useState } from "react";
import { SessionProvider, useSession } from "./context/SessionContext";
import { useWebSocket } from "./hooks/useWebSocket";
import UploadView from "./components/UploadView";
import StandardsCoverage from "./components/StandardsCoverage";
import ExtractionPreview from "./components/ExtractionPreview";
import PipelineView from "./components/PipelineView";
import ReviewDashboard from "./components/ReviewDashboard";
import ApprovalGate from "./components/ApprovalGate";
import GenerationProgress from "./components/GenerationProgress";
import ScaffoldingPreview from "./components/ScaffoldingPreview";
import DecisionLog from "./components/DecisionLog";

const TABS = [
  { key: "upload", label: "Upload" },
  { key: "standards", label: "Standards" },
  { key: "extraction", label: "Extraction" },
  { key: "review", label: "Review" },
  { key: "generation", label: "Generation" },
  { key: "scaffolding", label: "Scaffolding" },
  { key: "decisions", label: "Decision Log" },
];

// Maps the backend's current_stage/paused_at (ARCHITECTURE_v2.0.md section
// 9.1) onto which tab the dashboard should default to.
function stageToTab(stage, pausedAt) {
  if (pausedAt === "human_gate_1") return "review";
  if (pausedAt === "human_gate_2") return "scaffolding";
  if (!stage) return "upload";
  if (["extraction_preview", "document_parsing"].includes(stage)) return "extraction";
  if (["review_board", "review_aggregation", "review_qa"].includes(stage)) return "review";
  if (["context_synthesis", "ai_development_setup"].includes(stage)) return "generation";
  if (["consistency_check", "project_scaffolding"].includes(stage)) return "scaffolding";
  if (stage === "completed") return "scaffolding";
  return "upload";
}

function Dashboard() {
  const { state, actions } = useSession();
  const { session, status, error } = state;
  const [activeTab, setActiveTab] = useState("upload");

  useWebSocket(session?.id, (event) => {
    actions.dispatchWsEvent(event);
    if (session?.id) actions.loadStatus(session.id);
  });

  useEffect(() => {
    if (!session?.id) return undefined;
    actions.loadStatus(session.id);
    const interval = setInterval(() => actions.loadStatus(session.id), 4000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.id]);

  useEffect(() => {
    if (status) setActiveTab(stageToTab(status.current_stage, status.paused_at));
  }, [status?.current_stage, status?.paused_at]);

  if (!session) {
    return (
      <div className="min-h-screen">
        <Header projectName={null} />
        <main className="p-6">
          <UploadView />
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <Header projectName={session.project_name} />

      {error && (
        <div className="mx-6 mt-4 rounded-md border border-red-300 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <PipelineView />

      <nav className="flex gap-1 overflow-x-auto border-b bg-white px-4">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={`whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium ${
              activeTab === tab.key
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main className="p-6">
        {activeTab === "upload" && <UploadView />}
        {activeTab === "standards" && <StandardsCoverage />}
        {activeTab === "extraction" && <ExtractionPreview />}
        {activeTab === "review" && (
          <div className="space-y-6">
            <ReviewDashboard />
            {status?.paused_at === "human_gate_1" && <ApprovalGate gate="human_gate_1" />}
          </div>
        )}
        {activeTab === "generation" && <GenerationProgress />}
        {activeTab === "scaffolding" && (
          <div className="space-y-6">
            <ScaffoldingPreview />
            {status?.paused_at === "human_gate_2" && <ApprovalGate gate="human_gate_2" />}
          </div>
        )}
        {activeTab === "decisions" && <DecisionLog />}
      </main>
    </div>
  );
}

function Header({ projectName }) {
  return (
    <header className="border-b bg-white px-6 py-4">
      <h1 className="text-xl font-semibold text-slate-900">ASDA</h1>
      <p className="text-sm text-slate-500">
        {projectName || "Agentic Solution Delivery Accelerator"}
      </p>
    </header>
  );
}

export default function App() {
  return (
    <SessionProvider>
      <Dashboard />
    </SessionProvider>
  );
}
