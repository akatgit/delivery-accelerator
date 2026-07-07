import { createContext, useContext, useReducer, useCallback, useMemo } from "react";
import * as api from "../api/client";

const SessionContext = createContext(null);

const initialState = {
  session: null,
  sessions: [],
  standardsCoverage: null,
  conflicts: [],
  status: null,
  projectContext: null,
  review: null,
  reviewQuality: null,
  artifacts: [],
  scaffolding: null,
  decisionLog: [],
  events: [],
  // Local staging area for the two-phase human_gate_1 flow (ARCHITECTURE_v2.0.md
  // section 5.5/9.1): the user can resolve any number of contradictions first
  // (each its own "resolve_contradiction" submission the graph node loops on),
  // then separately finalize with accept/override/revise. ReviewDashboard and
  // ApprovalGate both read/write this so neither has to prop-drill to the other.
  reviewDecisions: {
    overrides: [],
    contradictionResolutions: [],
  },
  error: null,
  loading: {},
};

function reducer(state, action) {
  switch (action.type) {
    case "SET_LOADING":
      return { ...state, loading: { ...state.loading, [action.key]: action.value } };
    case "SET_ERROR":
      return { ...state, error: action.error };
    case "CLEAR_ERROR":
      return { ...state, error: null };
    case "SESSION_SET":
      return { ...state, session: action.session };
    case "SESSIONS_SET":
      return { ...state, sessions: action.sessions };
    case "STANDARDS_COVERAGE_SET":
      return { ...state, standardsCoverage: action.coverage };
    case "CONFLICTS_SET":
      return { ...state, conflicts: action.conflicts };
    case "STATUS_SET":
      return { ...state, status: action.status };
    case "PROJECT_CONTEXT_SET":
      return { ...state, projectContext: action.projectContext };
    case "REVIEW_SET":
      return { ...state, review: action.review };
    case "REVIEW_QUALITY_SET":
      return { ...state, reviewQuality: action.reviewQuality };
    case "ARTIFACTS_SET":
      return { ...state, artifacts: action.artifacts };
    case "SCAFFOLDING_SET":
      return { ...state, scaffolding: action.scaffolding };
    case "DECISION_LOG_SET":
      return { ...state, decisionLog: action.decisionLog };
    case "WS_EVENT":
      return { ...state, events: [action.event, ...state.events].slice(0, 200) };
    case "SET_FINDING_OVERRIDE": {
      const overrides = state.reviewDecisions.overrides.filter((o) => o.finding_id !== action.override.finding_id);
      overrides.push(action.override);
      return { ...state, reviewDecisions: { ...state.reviewDecisions, overrides } };
    }
    case "CLEAR_FINDING_OVERRIDE": {
      const overrides = state.reviewDecisions.overrides.filter((o) => o.finding_id !== action.findingId);
      return { ...state, reviewDecisions: { ...state.reviewDecisions, overrides } };
    }
    case "ADD_CONTRADICTION_RESOLUTION": {
      const contradictionResolutions = state.reviewDecisions.contradictionResolutions.filter(
        (r) => !(r.finding_id_a === action.resolution.finding_id_a && r.finding_id_b === action.resolution.finding_id_b)
      );
      contradictionResolutions.push(action.resolution);
      return { ...state, reviewDecisions: { ...state.reviewDecisions, contradictionResolutions } };
    }
    case "RESET_REVIEW_DECISIONS":
      return { ...state, reviewDecisions: initialState.reviewDecisions };
    case "RESET":
      return initialState;
    default:
      return state;
  }
}

export function SessionProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const withLoading = useCallback(async (key, fn) => {
    dispatch({ type: "SET_LOADING", key, value: true });
    dispatch({ type: "CLEAR_ERROR" });
    try {
      return await fn();
    } catch (err) {
      dispatch({ type: "SET_ERROR", error: err.message });
      throw err;
    } finally {
      dispatch({ type: "SET_LOADING", key, value: false });
    }
  }, []);

  const actions = useMemo(() => {
    const a = {
      async createSession(name, description) {
        return withLoading("createSession", async () => {
          const session = await api.createSession(name, description);
          dispatch({ type: "SESSION_SET", session });
          return session;
        });
      },
      async loadSessions() {
        return withLoading("sessions", async () => {
          const { sessions } = await api.listSessions();
          dispatch({ type: "SESSIONS_SET", sessions });
          return sessions;
        });
      },
      async loadSession(id) {
        return withLoading("session", async () => {
          const session = await api.getSession(id);
          dispatch({ type: "SESSION_SET", session });
          return session;
        });
      },
      async uploadDocument(id, type, file) {
        return withLoading("uploadDocument", () => api.uploadDocument(id, type, file));
      },
      async uploadStandard(id, file) {
        return withLoading("uploadStandard", async () => {
          const result = await api.uploadStandard(id, file);
          await a.loadStandardsCoverage(id);
          await a.loadConflicts(id);
          return result;
        });
      },
      async reuseStandards(id, sourceId) {
        return withLoading("reuseStandards", async () => {
          const result = await api.reuseStandards(id, sourceId);
          await a.loadStandardsCoverage(id);
          return result;
        });
      },
      async loadStandardsCoverage(id) {
        return withLoading("standardsCoverage", async () => {
          const coverage = await api.getStandardsCoverage(id);
          dispatch({ type: "STANDARDS_COVERAGE_SET", coverage });
          return coverage;
        });
      },
      async loadConflicts(id) {
        return withLoading("conflicts", async () => {
          const { conflicts } = await api.getConflicts(id);
          dispatch({ type: "CONFLICTS_SET", conflicts });
          return conflicts;
        });
      },
      async resolveConflicts(id, resolutions) {
        return withLoading("resolveConflicts", async () => {
          const result = await api.resolveConflicts(id, resolutions);
          await a.loadConflicts(id);
          return result;
        });
      },
      async startPipeline(id) {
        return withLoading("startPipeline", () => api.startPipeline(id));
      },
      async loadStatus(id) {
        return withLoading("status", async () => {
          const status = await api.getStatus(id);
          dispatch({ type: "STATUS_SET", status });
          return status;
        });
      },
      async loadExtraction(id) {
        return withLoading("extraction", async () => {
          const { project_context: projectContext } = await api.getExtraction(id);
          dispatch({ type: "PROJECT_CONTEXT_SET", projectContext });
          return projectContext;
        });
      },
      async confirmExtraction(id) {
        return withLoading("confirmExtraction", () => api.confirmExtraction(id));
      },
      async loadReview(id) {
        return withLoading("review", async () => {
          const review = await api.getReview(id);
          dispatch({ type: "REVIEW_SET", review });
          return review;
        });
      },
      async loadReviewQuality(id) {
        return withLoading("reviewQuality", async () => {
          const reviewQuality = await api.getReviewQuality(id);
          dispatch({ type: "REVIEW_QUALITY_SET", reviewQuality });
          return reviewQuality;
        });
      },
      async approve(id, decision, extra) {
        return withLoading("approve", async () => {
          const result = await api.approve(id, decision, extra);
          dispatch({ type: "RESET_REVIEW_DECISIONS" });
          return result;
        });
      },
      async reupload(id, documents) {
        return withLoading("reupload", () => api.reupload(id, documents));
      },
      async retryDomain(id, domain) {
        return withLoading(`retry:${domain}`, () => api.retryDomain(id, domain));
      },
      async loadArtifacts(id) {
        return withLoading("artifacts", async () => {
          const { artifacts } = await api.getArtifacts(id);
          dispatch({ type: "ARTIFACTS_SET", artifacts });
          return artifacts;
        });
      },
      async loadScaffolding(id) {
        return withLoading("scaffolding", async () => {
          const scaffolding = await api.getScaffolding(id);
          dispatch({ type: "SCAFFOLDING_SET", scaffolding });
          return scaffolding;
        });
      },
      async loadDecisionLog(id) {
        return withLoading("decisionLog", async () => {
          const { entries } = await api.getDecisionLog(id);
          dispatch({ type: "DECISION_LOG_SET", decisionLog: entries });
          return entries;
        });
      },
      dispatchWsEvent(event) {
        dispatch({ type: "WS_EVENT", event });
      },
      setFindingOverride(override) {
        dispatch({ type: "SET_FINDING_OVERRIDE", override });
      },
      clearFindingOverride(findingId) {
        dispatch({ type: "CLEAR_FINDING_OVERRIDE", findingId });
      },
      addContradictionResolution(resolution) {
        dispatch({ type: "ADD_CONTRADICTION_RESOLUTION", resolution });
      },
      reset() {
        dispatch({ type: "RESET" });
      },
    };
    return a;
  }, [withLoading]);

  const value = useMemo(() => ({ state, dispatch, actions }), [state, actions]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within a SessionProvider");
  return ctx;
}
