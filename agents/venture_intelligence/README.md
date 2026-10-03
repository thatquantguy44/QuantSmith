# Venture Intelligence Agents

Agents for venture capital and non-traditional intelligence channels, organized
by world region plus cross-cutting capabilities. Foundation spec:
`specs/0083-venture-intelligence-foundation/`; first build:
`specs/0084-venture-regional-agents-southeast-asia/`. Shared standard:
`instructions/venture_intelligence.md`.

## Cross-cutting

| Agent | Handles | Never |
| --- | --- | --- |
| `entity_resolution/` | Cross-source, cross-script company identity decisions with reasons | Merge on a name alone |
| `multilingual_document_nlp/` | Source-anchored extraction and normalization from start-up documents in Mandarin, Bahasa, Vietnamese, Thai, Filipino, English | Legal translation or interpretation |

## Regions

| Region | Status | Scope |
| --- | --- | --- |
| Southeast Asia (`southeast_asia/`) | **built** (`0084`) | Singapore, Indonesia, Vietnam, Thailand, Malaysia, Philippines; thin-coverage Cambodia, Laos, Myanmar, Brunei, Timor-Leste |
| Greater China & East Asia | reserved (`0085`) | PRC, Hong Kong, Taiwan, Japan, Korea; Mandarin/Japanese/Korean documents |
| South Asia | reserved (`0085`) | India, Bangladesh, Sri Lanka, Pakistan |
| Middle East & North Africa | reserved (`0086`) | Gulf sovereign-capital ecosystems, Israel, Turkey, Egypt |
| Europe | reserved (`0086`) | EU, UK, Nordics, CEE |
| Central Asia & Caucasus | reserved (`0086`) | Kazakhstan, Uzbekistan, Georgia, Armenia |
| Sub-Saharan Africa | reserved (`0087`) | Nigeria, Kenya, South Africa, Francophone Africa |
| Latin America & Caribbean | reserved (`0087`) | Brazil, Mexico, Colombia, Southern Cone |
| North America | reserved (`0087`) | US, Canada |
| Oceania | reserved (`0087`) | Australia, New Zealand, Pacific |

A region gets a regional lead first; specialists are added only when a coverage
row shows a workflow no existing agent holds.

## Southeast Asia agents

| Agent | Handles | Never |
| --- | --- | --- |
| `southeast_asia/regional_lead/` | Market-by-market view, coverage, routing | Recommend/rank investments |
| `southeast_asia/entity_structure_analyst/` | Holdco/opco maps, ownership indicators (`sovereign_adjacent`) | Designate, attribute, accuse |
| `southeast_asia/funding_ecosystem_analyst/` | Comparable rounds, investors, exit routes | Recommend, size, or value |

All are contract-only (no SDK runtime); inputs are caller-supplied.
