import { useEffect, useMemo, useState } from "react";
import { useSession } from "../context/SessionContext";
import { getScaffoldingDownloadUrl } from "../api/client";

// Builds a nested { name, path, children? } tree from a flat list of
// "a/b/c.py"-style paths, for a folder-tree display.
function buildTree(paths) {
  const root = { name: "", path: "", children: new Map() };
  for (const path of paths) {
    const parts = path.split("/");
    let node = root;
    let accPath = "";
    for (let i = 0; i < parts.length; i++) {
      accPath = accPath ? `${accPath}/${parts[i]}` : parts[i];
      if (!node.children.has(parts[i])) {
        node.children.set(parts[i], { name: parts[i], path: accPath, children: new Map() });
      }
      node = node.children.get(parts[i]);
    }
  }
  return root;
}

// ScaffoldingPreview (ARCHITECTURE_v2.0.md section 11.1): file tree, content
// preview, AI artifact badges, download button.
export default function ScaffoldingPreview() {
  const { state, actions } = useSession();
  const { session, scaffolding, artifacts, loading } = state;
  const [selectedPath, setSelectedPath] = useState(null);

  useEffect(() => {
    if (session?.id) {
      actions.loadScaffolding(session.id);
      actions.loadArtifacts(session.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.id]);

  const artifactsByFilename = useMemo(() => new Map(artifacts.map((a) => [a.filename, a])), [artifacts]);
  const tree = useMemo(() => buildTree(scaffolding?.files || []), [scaffolding]);

  if (!session) return <p className="text-sm text-slate-500">Create a session first.</p>;
  if (loading.scaffolding && !scaffolding) return <p className="text-sm text-slate-500">Loading scaffolding...</p>;
  if (!scaffolding) return <p className="text-sm text-slate-500">Scaffolding hasn't been generated yet.</p>;

  const selectedArtifact = selectedPath ? artifactsByFilename.get(selectedPath) : null;

  return (
    <div className="mx-auto grid max-w-5xl grid-cols-1 gap-6 md:grid-cols-2">
      <div className="rounded-lg border bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">File tree ({scaffolding.file_count})</h2>
          <a
            href={scaffolding.zip_path ? getScaffoldingDownloadUrl(session.id) : undefined}
            aria-disabled={!scaffolding.zip_path}
            className={`rounded-md px-3 py-1.5 text-sm font-medium text-white ${
              scaffolding.zip_path ? "bg-indigo-600 hover:bg-indigo-500" : "cursor-not-allowed bg-slate-300"
            }`}
          >
            Download .zip
          </a>
        </div>
        <TreeNode node={tree} depth={0} artifactsByFilename={artifactsByFilename} onSelect={setSelectedPath} selectedPath={selectedPath} />
      </div>

      <div className="rounded-lg border bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold text-slate-900">Content preview</h2>
        {selectedArtifact ? (
          <div>
            <p className="mb-2 font-mono text-xs text-slate-500">{selectedArtifact.filename}</p>
            <pre className="max-h-96 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
              {selectedArtifact.content}
            </pre>
          </div>
        ) : selectedPath ? (
          <p className="text-sm text-slate-500">
            This file isn't an AI-generated artifact tracked separately, so its content is only available in the
            downloaded archive.
          </p>
        ) : (
          <p className="text-sm text-slate-400">Select a file to preview its content.</p>
        )}
      </div>
    </div>
  );
}

function TreeNode({ node, depth, artifactsByFilename, onSelect, selectedPath }) {
  const isFile = node.children.size === 0 && node.path;
  if (isFile) {
    const isArtifact = artifactsByFilename.has(node.path);
    const isSelected = selectedPath === node.path;
    return (
      <button
        type="button"
        onClick={() => onSelect(node.path)}
        style={{ paddingLeft: `${depth * 16}px` }}
        className={`flex w-full items-center gap-2 rounded px-2 py-1 text-left text-sm hover:bg-slate-50 ${
          isSelected ? "bg-indigo-50 text-indigo-700" : "text-slate-700"
        }`}
      >
        <span>📄</span>
        <span className="truncate">{node.name}</span>
        {isArtifact && (
          <span className="ml-auto shrink-0 rounded bg-indigo-100 px-1.5 py-0.5 text-xs font-medium text-indigo-700">
            AI artifact
          </span>
        )}
      </button>
    );
  }

  return (
    <div>
      {node.name && (
        <div style={{ paddingLeft: `${depth * 16}px` }} className="flex items-center gap-2 px-2 py-1 text-sm font-medium text-slate-500">
          <span>📁</span>
          <span>{node.name}</span>
        </div>
      )}
      {Array.from(node.children.values()).map((child) => (
        <TreeNode
          key={child.path}
          node={child}
          depth={depth + 1}
          artifactsByFilename={artifactsByFilename}
          onSelect={onSelect}
          selectedPath={selectedPath}
        />
      ))}
    </div>
  );
}
