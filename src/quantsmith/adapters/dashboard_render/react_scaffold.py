"""React scaffold provider — turn a ReactDashboardPayload into a runnable React app.

Pure standard library: it generates deterministic React source files from the payload
and writes them (or, on ``dry_run``, plans them). Implements
``adapters/dashboard_render/react_scaffold.md``. Data is fetched from a governed
endpoint at runtime; no data or secrets are baked into the bundle.
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict

from ...pipelines.react_profile import ReactDashboardPayload
from .result import RenderResult, contains_secret, manifest


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "dashboard"


def _files(payload: ReactDashboardPayload) -> Dict[str, str]:
    slug = _slug(payload.title)
    used = []
    for c in payload.components:
        if c.component not in used:
            used.append(c.component)

    package_json = json.dumps(
        {
            "name": slug,
            "version": "0.0.0",
            "private": True,
            "type": "module",
            "scripts": {"dev": "vite", "build": "vite build"},
            "dependencies": {"react": "18.3.1", "react-dom": "18.3.1", "recharts": "2.12.7"},
            "devDependencies": {"vite": "5.4.8"},
        },
        indent=2,
        sort_keys=True,
    ) + "\n"

    # Component registry — a thin wrapper per used component name.
    registry_lines = ["// Auto-generated component registry. Do not edit by hand.", ""]
    for name in used:
        registry_lines.append(
            f"export function {name}({{ title, metric, dimensions }}) {{\n"
            f"  return (\n"
            f"    <figure aria-label={{`{{title}} ({{metric}})`}}>\n"
            f"      <figcaption>{{title}}</figcaption>\n"
            f"      {{/* {name} bound to governed metric `{{metric}}` */}}\n"
            f"    </figure>\n"
            f"  );\n"
            f"}}\n"
        )
    components_jsx = "\n".join(registry_lines)

    # Data hook — fetch from a governed endpoint; loading/error/empty states.
    use_data = (
        "import { useEffect, useState } from 'react';\n\n"
        "// Fetch governed data from a server endpoint. No credentials in the client.\n"
        "export function useData(dataset) {\n"
        "  const [state, setState] = useState({ status: 'loading', rows: [] });\n"
        "  useEffect(() => {\n"
        "    let live = true;\n"
        "    fetch(`/api/data?dataset=${encodeURIComponent(dataset)}`)\n"
        "      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))\n"
        "      .then((rows) => live && setState({ status: rows.length ? 'ready' : 'empty', rows }))\n"
        "      .catch(() => live && setState({ status: 'error', rows: [] }));\n"
        "    return () => { live = false; };\n"
        "  }, [dataset]);\n"
        "  return state;\n"
        "}\n"
    )

    # Dashboard — render each panel at its grid position.
    imports = ", ".join(used) if used else ""
    layout_by_id = {g.i: g for g in payload.layout}
    panel_lines = []
    for c in payload.components:
        g = layout_by_id.get(c.id)
        style = (
            f"{{{{ gridColumn: '{(g.x // 6) + 1} / span {(g.w // 6) or 1}', "
            f"gridRow: '{(g.y // 4) + 1}' }}}}" if g else "{{}}"
        )
        props = json.dumps(c.props, sort_keys=True)
        panel_lines.append(
            f"      <div key=\"{c.id}\" style={style}>\n"
            f"        <{c.component} {{...{props}}} />\n"
            f"      </div>"
        )
    panels = "\n".join(panel_lines)
    filters = json.dumps(dict(payload.filters), sort_keys=True)
    dashboard_jsx = (
        f"import {{ {imports} }} from './components/registry.jsx';\n"
        "import { useData } from './useData.js';\n\n"
        f"const DATASET = {json.dumps(payload.dataset)};\n"
        f"const FILTERS = {filters};\n\n"
        "export default function Dashboard() {\n"
        "  const { status } = useData(DATASET);\n"
        "  return (\n"
        f"    <main aria-busy={{status === 'loading'}}>\n"
        f"      <h1>{payload.title}</h1>\n"
        "      <section style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(2, 1fr)' }}>\n"
        f"{panels}\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )

    main_jsx = (
        "import React from 'react';\n"
        "import { createRoot } from 'react-dom/client';\n"
        "import Dashboard from './Dashboard.jsx';\n\n"
        "createRoot(document.getElementById('root')).render(<Dashboard />);\n"
    )

    readme = (
        f"# {payload.title}\n\n"
        f"Generated React dashboard for dataset `{payload.dataset}` (page: {payload.page}).\n\n"
        "Data is fetched from `/api/data` at runtime; credentials stay server-side.\n"
        "Run `npm install && npm run dev`.\n"
    )

    gitignore = "node_modules/\ndist/\n.env\n"

    return {
        "package.json": package_json,
        "README.md": readme,
        ".gitignore": gitignore,
        "src/main.jsx": main_jsx,
        "src/Dashboard.jsx": dashboard_jsx,
        "src/useData.js": use_data,
        "src/components/registry.jsx": components_jsx,
    }


def scaffold_react(
    payload: ReactDashboardPayload,
    destination: str,
    dry_run: bool = False,
) -> RenderResult:
    """Generate a React app from a ReactDashboardPayload.

    Deterministic: the same payload yields the same files and checksums. On ``dry_run``
    the files are planned (manifest computed) but nothing is written. Raises if any
    generated file would contain a secret.
    """
    files = _files(payload)
    for path, content in files.items():
        if contains_secret(content):
            raise ValueError(f"generated file '{path}' would contain a secret")

    records = manifest(files)
    if dry_run:
        return RenderResult(
            adapter_name="dashboard_render",
            provider="react_scaffold",
            status="planned",
            artifact_uri=None,
            files=records,
            dry_run=True,
        )

    for rel, content in files.items():
        full = os.path.join(destination, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)

    return RenderResult(
        adapter_name="dashboard_render",
        provider="react_scaffold",
        status="generated",
        artifact_uri=destination,
        files=records,
        dry_run=False,
    )
