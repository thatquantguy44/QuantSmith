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

## Signal, sourcing, and diligence agents (cross-cutting)

| Agent | Handles | Class | Never |
| --- | --- | --- | --- |
| `patent_ip_analyst/` | Patent-family landscapes across offices and languages | analytic_support | Legal validity, infringement, valuation |
| `hiring_signal_analyst/` | Organization-level hiring and workforce signals | person_adjacent | Profile individuals; assert headcount from postings |
| `narrative_news_analyst/` | Multilingual news, syndication collapse, amplification indicators | analytic_support | Present narrative as fact; attribute campaigns |
| `technology_landscape_analyst/` | Multi-channel technology landscape with corroboration status | analytic_support | Predict success; assign readiness |
| `deal_sourcing/` | Longlist from signals against caller-stated criteria | analytic_support | Rank by merit; recommend |
| `company_diligence/` | Evidence/assumption/judgement memo from supplied evidence | analytic_support | Approve, reject, certify |

## Orchestration (cross-cutting)

| Agent | Handles | Class | Never |
| --- | --- | --- | --- |
| `venture_orchestrator/` | Routes a request to a chain of agents with gates, owner, class, and clearance; refuses what the suite must not do | analytic_support | Decide, recommend, or release; override a refusal |

## Product writers (cross-cutting)

| Agent | Handles | Class | Never |
| --- | --- | --- | --- |
| `intelligence_brief_writer/` | BLUF brief from cited, graded passages; separate evidence, assumptions, judgements, gaps | analytic_support | Release without a named reviewer; state an uncited claim |
| `investment_memo_writer/` | Committee memo from diligence, tradecraft, and fund outputs; decision owner named | analytic_support | Recommend, approve, or reject an investment |

## Fund and portfolio analytics agents (cross-cutting)

| Agent | Handles | Class | Never |
| --- | --- | --- | --- |
| `fund_performance_analyst/` | DPI/RVPI/TVPI, XIRR with roots, J-curve, KS-PME, vintage-matched peer rank, all as of a date | analytic_support | Set or certify a valuation; rank funds |
| `valuation_marks_reviewer/` | Mark-consistency flags with numbers against policy thresholds | analytic_support | Approve, reject, set, or propose a mark |
| `portfolio_reserve_analyst/` | Seeded fund-outcome and reserve-policy scenarios with assumptions and intervals | analytic_support | Decide follow-ons, set reserve policy, forecast returns |

## Tradecraft and screening-support agents (cross-cutting)

| Agent | Handles | Class | Never |
| --- | --- | --- | --- |
| `source_reliability_grader/` | Proposed source and information grades with stated bases; origin and corroboration counting | analytic_support | Override a human grade; grade on reputation |
| `confidence_language_reviewer/` | Likelihood wording against probability bands; vague-term flags | analytic_support | Change a judgement |
| `competing_hypotheses_analyst/` | Competing-hypotheses matrix with a deception/artifact hypothesis; diagnostic evidence; sensitivity | analytic_support | Select the conclusion |
| `collection_gap_tracker/` | Information-requirement register with lawful candidate channels | analytic_support | Task or recommend non-public collection |
| `ownership_screen/` | Effective ownership through chains, list matches as indicators, unresolved layers | sovereign_adjacent | Designate, attribute, accuse |
| `dual_use_indicator/` | Control-list resemblance as questions for counsel | sovereign_adjacent | Classify, license, or rule on legality |

## Regions

| Region | Status | Scope |
| --- | --- | --- |
| Southeast Asia (`southeast_asia/`) | **built** (`0084`) | Singapore, Indonesia, Vietnam, Thailand, Malaysia, Philippines; thin-coverage Cambodia, Laos, Myanmar, Brunei, Timor-Leste |
| Greater China & East Asia (`greater_china_east_asia/`) | **built** (`0085`) | Mainland China, Hong Kong, Taiwan, Japan, Korea; Chinese/Japanese/Korean documents |
| South Asia (`south_asia/`) | **built** (`0085`, lead only) | India, Bangladesh, Pakistan, Sri Lanka; thin-coverage Nepal, Bhutan, Maldives |
| Middle East & North Africa | reserved (`0087`, deferred while Asia is the focus) | Gulf sovereign-capital ecosystems, Israel, Turkey, Egypt |
| Europe | reserved (`0087`, deferred) | EU, UK, Nordics, CEE |
| Central Asia (`central_asia/`) | **built** (`0086`, lead only) | Kazakhstan, Uzbekistan, Kyrgyzstan, Tajikistan; thin-coverage Turkmenistan |
| Caucasus | reserved (`0087`, deferred) | Georgia, Armenia, Azerbaijan |
| Sub-Saharan Africa | reserved (`0087`, deferred) | Nigeria, Kenya, South Africa, Francophone Africa |
| Latin America & Caribbean | reserved (`0087`, deferred) | Brazil, Mexico, Colombia, Southern Cone |
| North America | reserved (`0087`, deferred) | US, Canada |
| Oceania | reserved (`0087`, deferred) | Australia, New Zealand, Pacific |

A region gets a regional lead first; specialists are added only when a coverage
row shows a workflow no existing agent holds.

## Southeast Asia agents

| Agent | Handles | Never |
| --- | --- | --- |
| `southeast_asia/regional_lead/` | Market-by-market view, coverage, routing | Recommend/rank investments |
| `southeast_asia/entity_structure_analyst/` | Holdco/opco maps, ownership indicators (`sovereign_adjacent`) | Designate, attribute, accuse |
| `southeast_asia/funding_ecosystem_analyst/` | Comparable rounds, investors, exit routes | Recommend, size, or value |

## Greater China & East Asia and South Asia agents

| Agent | Handles | Never |
| --- | --- | --- |
| `greater_china_east_asia/regional_lead/` | Market-by-market view (Mainland, Hong Kong, Taiwan, Japan, Korea), native-language coverage, routing | Recommend/rank investments; rule on permissibility |
| `greater_china_east_asia/entity_structure_analyst/` | Offshore-onshore structure, equity versus contractual control (`sovereign_adjacent`) | Designate, attribute, conclude control by any government or party |
| `south_asia/regional_lead/` | Market-by-market view, lakh/crore and fiscal-year normalization, domicile versus market | Recommend/rank investments; rule on permissibility |

## Central Asia agents

| Agent | Handles | Never |
| --- | --- | --- |
| `central_asia/regional_lead/` | Market-by-market view (Kazakhstan, Uzbekistan, Kyrgyzstan, Tajikistan), Cyrillic/Latin script variants, Russian-locale numbers | Recommend/rank investments; rule on permissibility, sanctions, or export-control status |

All are contract-only (no SDK runtime); inputs are caller-supplied.
