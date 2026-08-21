import { useConsole } from "../../lib/store";
import { Panel } from "../../components/ui";
import { GraphCanvas } from "../../components/GraphCanvas";

export function GraphView() {
  const model = useConsole((s) => s.model)!;
  return (
    <Panel title="Knowledge Graph — records × scope × evidence × workflow">
      <GraphCanvas model={model} />
    </Panel>
  );
}
