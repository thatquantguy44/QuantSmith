import { useConsole } from "../../lib/store";
import { Panel, Empty } from "../../components/ui";

export function Changes() {
  const model = useConsole((s) => s.model)!;
  const { changes } = model;
  return (
    <Panel title="Recent Changes — git history over memory/" bodyClass="p-0">
      {changes.length === 0 ? (
        <div className="p-3">
          <Empty>No git history over memory/ available in this view.</Empty>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-term-border text-3xs uppercase tracking-widest text-term-muted">
                <th className="px-3 py-2 text-left">When</th>
                <th className="px-3 py-2 text-left">Change</th>
                <th className="px-3 py-2 text-left">Author</th>
                <th className="px-3 py-2 text-left">Files</th>
                <th className="px-3 py-2 text-left">Commit</th>
              </tr>
            </thead>
            <tbody>
              {changes.map((c) => (
                <tr key={c.hash} className="row-hover border-b border-term-border/60 align-top">
                  <td className="whitespace-nowrap px-3 py-2 stat text-term-dim">{c.date.slice(0, 10)}</td>
                  <td className="max-w-[440px] px-3 py-2 text-term-text">{c.subject}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-term-dim">{c.author}</td>
                  <td className="px-3 py-2">
                    {c.files.slice(0, 4).map((f) => (
                      <div key={f} className="text-3xs text-term-muted">
                        {f}
                      </div>
                    ))}
                    {c.files.length > 4 && <div className="text-3xs text-term-muted">+{c.files.length - 4} more</div>}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 stat text-term-amber">{c.hash}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
