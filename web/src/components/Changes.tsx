import type { Model } from "../lib/types";
import { EmptyState } from "./common";

export function Changes({ model }: { model: Model }) {
  const { changes } = model;
  if (changes.length === 0) {
    return (
      <EmptyState>
        No git history over <code>memory/</code> is available in this view. When the
        console runs inside a git checkout, recent commits touching the store appear here.
      </EmptyState>
    );
  }
  return (
    <div className="card" style={{ padding: 0, overflowX: "auto" }}>
      <table className="tbl">
        <thead>
          <tr>
            <th>When</th>
            <th>Change</th>
            <th>Author</th>
            <th>Files</th>
            <th>Commit</th>
          </tr>
        </thead>
        <tbody>
          {changes.map((c) => (
            <tr key={c.hash}>
              <td style={{ whiteSpace: "nowrap", color: "var(--fg-dim)" }}>{c.date.slice(0, 10)}</td>
              <td style={{ maxWidth: 460 }}>{c.subject}</td>
              <td style={{ whiteSpace: "nowrap" }}>{c.author}</td>
              <td>
                {c.files.slice(0, 4).map((f) => (
                  <div key={f} className="prov">{f}</div>
                ))}
                {c.files.length > 4 && <div className="prov">+{c.files.length - 4} more</div>}
              </td>
              <td className="mono" style={{ color: "var(--accent)" }}>{c.hash}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
