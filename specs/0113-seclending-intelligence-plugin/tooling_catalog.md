# Tooling Catalog: SFMeridian

- **Spec:** 0113-seclending-intelligence-plugin (`spec.md` REQ-027, `plan.md`)
- **Status:** Draft — screening complete; admission reviews pending
- **Discovery input:** the community *Awesome Quant* list (supplied 2026-10-22),
  screened entry by entry against SFMeridian's scope
- **Last updated:** 2026-10-22

> The governed list of third-party libraries SFMeridian components may depend
> on, and the **only** list SFMeridian agents may recommend from (REQ-027). A
> curated community list is a discovery input, not an endorsement: nothing here
> is installed, vendored, or recommended until it passes admission review. The
> plugin core stays standard-library only (NFR-003); every entry is an optional
> extra or a reference.

## Admission Rules

An entry moves from `assess` to `trial` or `adopt` only after a named
reviewer records, in the machine-readable catalog (`T-036`):

1. **License** verified from the project's own repository at the pinned
   version, and compatible with the adopter's commercial use. Every license
   below is `to verify` until then; known concerns are flagged.
2. **Maintenance**: a release within the last 18 months, more than one
   maintainer or an organizational owner, an issue tracker that responds.
3. **Supply chain**: exact name checked against the official index
   (typosquats), version pinned with a hash, no install-time code fetches,
   advisory-database scan clean (`secret-scan`/dependency review gates).
4. **Fit**: a named SFMeridian component, agent, or workflow that needs it,
   and no stdlib or already-adopted alternative.
5. **Determinism**: seedable or deterministic where it feeds the evaluation
   gate (NFR-001).

**Rings:** `adopt` (allowed in shipped extras) · `trial` (allowed in one
child spec, behind a flag, with evidence required to promote) · `assess`
(read, prototype, or borrow a pattern; no dependency) · `hold` (do not
depend; reason stated) · `exclude` (out of scope; reason stated).

**Agent rule:** an agent that suggests a library must cite its catalog row.
A package name that is not in this catalog is never recommended — a
hallucinated or squatted package name is a supply-chain failure, not a typo.

## Screened Entries

### Numerical core and data handling (extra `[data]`)

| Library | Lang | Ring | SFMeridian use | Component / agent | Notes |
| --- | --- | --- | --- | --- | --- |
| numpy | Python | adopt | Arrays for `0023` runtime, metrics | `execute/`, `0023` | Already a QuantSmith base dependency. |
| scipy | Python | adopt | LP for inventory allocation (`0023`), stats | W7, `linear_programming` | Already the QuantSmith `quant` extra. |
| pandas | Python | adopt | Result frames for analytics agents and exports | `0119` agents, `reporting-agent` | Already the QuantSmith `data` extra. Never in the core. |
| polars | Python | trial | Fast point-in-time panel builds over large loan books | `feature_store_engineering`, W10 | Promote if panel builds exceed NFR-005 with pandas. |
| statistics | Python | adopt | Stdlib summary statistics in the core | `grounding/` recompute | Standard library. |
| ArcticDB | Python | hold | Tick/time-series store for PIT borrow panels | — | License reported as source-available (BSL-style); verify. Adopter databases are the store of record. |
| sympy, pymc3, modelx, quantdsl | Python | hold | — | — | No current SFMeridian need; Bayesian demand models revisit in `0119` if baselines fail. |
| R / Julia / Java / Rust numerical libs | various | exclude | — | — | Plugin runtime is Python; cross-language ports are out of scope. |

### Day counts, rates, and conventions (extra `[conventions]`)

| Library | Lang | Ring | SFMeridian use | Component / agent | Notes |
| --- | --- | --- | --- | --- | --- |
| QuantLib (Python bindings) / PyQL | Python | trial | Independent cross-check of ACT/360 fee and rebate accrual (`0066`), benchmark-rate compounding behind rebate = benchmark − fee | `grounding/` golden cases, `financing_cost_analysis` | Test-time only; never on the answer path. |
| rateslib | Python | hold | Same cross-checks | — | License reported as restricting commercial use; verify before any use. |
| day-count-conventions, compounded-sofr | TypeScript | assess | Published reference values for ACT/360 and SOFR compounding golden cases | `0117` golden set | Use their documented reference values, not the code. |
| financial-instrument pricers (vollib, FinancePy, gs-quant, tf-quant-finance, …) | various | exclude | — | — | Option and derivative pricing is outside SFMeridian's scope. |

### Calendars and settlement timing (extra `[calendars]`)

| Library | Lang | Ring | SFMeridian use | Component / agent | Notes |
| --- | --- | --- | --- | --- | --- |
| exchange_calendars | Python | adopt | Business-day as-of resolution, recall notice and settlement windows, accrual day counts | `verify/` PIT predicates, W3 | Pin; calendars change yearly. |
| pandas_market_calendars | Python | trial | Same, where an adopter already standardizes on it | `verify/` | Choose one calendar library per deployment. |
| bizdays | Python | trial | Custom lending-desk holiday sets | `semantic/` | |
| sifma-holidays, us-equity-market-calendar, fx-value-date | TypeScript | assess | Reference rules for bond-market holidays and T+1 settlement | `0117` golden cases | Port rules as test vectors only. |

### Time series and forecasting (extra `[timeseries]`)

| Library | Lang | Ring | SFMeridian use | Component / agent | Notes |
| --- | --- | --- | --- | --- | --- |
| statsmodels | Python | adopt | Naive/ETS/ARIMA baselines for borrow demand and utilization | `time_series_forecasting`, W2, W10 | REQ-022 baselines. |
| arch | Python | trial | Fee and utilization volatility for stress bands | `utilization_specials_analyst`, `risk` | |
| pmdarima | Python | trial | Automated ARIMA baselines | `time_series_forecasting` | |
| tsfresh | Python | trial | Feature extraction for specials and recall classifiers | `feature_store_engineering`, `supervised_learning` | All features computed as-of (`0006` folds). |
| gluon-ts, functime, Prophet | Python | assess | Probabilistic or panel forecasting if baselines leave a gap | `time_series_forecasting` | Heavier dependencies; need evidence first. |
| tsmoothie | Python | assess | Outlier smoothing in fee series | `unsupervised_anomaly` | |

### Validation and backtest integrity (extra `[validation]`)

| Library | Lang | Ring | SFMeridian use | Component / agent | Notes |
| --- | --- | --- | --- | --- | --- |
| purgedcv | Python | trial | Purged/embargoed CV and deflated Sharpe for borrow-signal models | `model_selection_validation`, W10 | Cross-check against `0006`/`0046` folds. |
| alphalens-reloaded | Python | trial | Evaluate borrow-fee and utilization signals as factors | `data_signal_intake`, `backtest_review` | |
| empyrical-reloaded / fincore | Python | trial | Performance metrics for borrow-cost-adjusted returns | `performance_attribution` | Pick one. |
| mlfinlab | Python | hold | — | — | Reported as commercial-licensed; verify. |
| zipline-reloaded, vectorbt, bt, backtrader, nautilus_trader, Lean | Python | hold | — | — | `0044`/`0046` engines already exist; use only as an independent cross-check in a child spec. |

### Portfolio optimization and risk (extra `[optimization]`)

| Library | Lang | Ring | SFMeridian use | Component / agent | Notes |
| --- | --- | --- | --- | --- | --- |
| skfolio | Python | trial | Short-side portfolio construction with borrow-cost constraints | W10, `risk_budgeting` | |
| Riskfolio-Lib | Python | trial | CVaR and risk-budget checks including borrow cost | `risk_budgeting`, `risk` | |
| PyPortfolioOpt | Python | assess | Same; overlaps skfolio and Riskfolio-Lib | — | Keep one primary. |
| fortitudo.tech | Python | assess | Entropy-pooling stress views on recall scenarios | `robust_optimization` | |
| riskparity.py | Python | hold | — | — | No risk-parity workflow in scope. |

### Market and reference data clients (extra `[sources]`)

Every data source must already be registered in `sources/*.yml` (`0027`);
a client library is only an adapter to a registered source.

| Library | Lang | Ring | Registered source | SFMeridian use | Notes |
| --- | --- | --- | --- | --- | --- |
| fedfred / pystlouisfed | Python | trial | `sources/fred.yml` | Benchmark rates for rebate and fee decomposition | Pick one; `0045` PIT adapter already reads FRED vintages. |
| newyorkfed | TypeScript | assess | `sources/ny_fed.yml` | SOFR/OBFR for cash-collateral rebate benchmarks | Use a stdlib HTTP adapter in Python; the TS client is a reference. |
| treasurydirect, treasury-fiscaldata | TypeScript | assess | `sources/treasury.yml` | Bill rates for cash-collateral reinvestment | Same. |
| edgartools | Python | trial | `sources/sec_edgar.yml` | Fund securities-lending income and collateral disclosures in N-CEN/N-PORT filings for beneficial-owner benchmarking | Public filings only. |
| OpenBB | Python | assess | per provider | Short-interest and market context | Provider licenses vary; each provider needs its own `0027` entry. |
| yfinance, yahooquery, pandas-datareader | Python | hold | — | — | Unofficial or terms-restricted; not acceptable for desk answers. |
| Bloomberg wrappers (pdblp, BloombergFetch, Rblpapi) | various | assess | adopter-licensed | Prices and reference data where the adopter licenses Bloomberg | Adopter-local; never in repo fixtures. |
| commercial data APIs (Commercial & Proprietary Services section) | various | exclude | — | — | Vendor selection is a non-goal; an adopter registers a licensed vendor via `0027`. |

### Database drivers and SQL parsing (extras `[postgres]`, `[oracle]`, `[databricks]`, `[sqlparse]`)

Not in the community list; added for the first adopter targets decided
2026-10-22 (PostgreSQL, Oracle, Databricks SQL). The SQLite fixture uses the
standard library.

| Library | Lang | Ring | SFMeridian use | Component / agent | Notes |
| --- | --- | --- | --- | --- | --- |
| psycopg (v3) | Python | trial | PostgreSQL read-only profiles; CI execution fixture | `execute/`, `catalog/` (`0115`/`0116`) | Admission review before `0116` ships. |
| oracledb | Python | trial | Oracle read-only profiles (thin mode, no client install) | `execute/`, `catalog/` | Admission review before `0116` ships. |
| databricks-sql-connector | Python | trial | Databricks SQL warehouse profiles | `execute/`, `catalog/` | Unity Catalog introspection via `information_schema`; admission review before `0116`. |
| sqlglot | Python | trial | Strict multi-dialect parsing for the verifier (Postgres, Oracle, Databricks) | `verify/` (`0116`) | Optional; the stdlib tokenizer fails closed without it. |

### Delivery and spreadsheets (extra `[excel]`)

| Library | Lang | Ring | SFMeridian use | Component / agent | Notes |
| --- | --- | --- | --- | --- | --- |
| openpyxl | Python | adopt | Desk-pack exports | `reporting-agent`, W2, W4 | Already a QuantSmith dev dependency; `0017` writer uses it. |
| xlsxwriter | Python | trial | Formatted desk packs | `reporting-agent` | |
| xlwings, pyxll | Python | assess | Excel-native desk front end calling the Python API | app surface (`0118` follow-up) | pyxll is commercial. |
| D-Tale | Python | assess | Analyst-side exploration of result sets | dev only | Never exposed to unauthenticated users. |

### Anti-hallucination and audit patterns (borrow the idea; no dependency)

These small projects implement ideas SFMeridian already requires. They are
recorded so the design can be checked against them, not depended on.

| Project | Pattern | SFMeridian counterpart |
| --- | --- | --- |
| thesis-ci | Fail any number without a source citation; freeze thresholds once results exist | REQ-012 grounding; REQ-016 thresholds versioned with the golden set |
| trading-research-agents | Language models only propose; deterministic rules decide and compute every figure | Plan approach; verify-token interface |
| lookahead-free, rulelint, backtest-audit-kit, pit-release-gate | Look-ahead and staggered-arrival detection | REQ-010 PIT predicates; `leakage` gate; W5/W10 |
| canli-pit-lake | Every read takes an explicit as-of | `ask(as_of)`; `0102` bitemporal store |
| autonomous-audit, falsification-ledger | Hash-chained, tamper-evident decision and pre-registration logs | `0070` run envelope; eval thresholds frozen per release |
| factor-qc, honest-signals | Fail-closed evidence gates; lift against a baseline, not a hit rate | `eval.run` gate; REQ-022 baselines |
| Seiche, Market Brief | Separate release and retrieval clocks; explicit missing-data states | REQ-007 dated snapshots; abstention naming missing evidence |

## Excluded Sections and Why

| Section or kind | Reason |
| --- | --- |
| Trading & backtesting platforms, broker and exchange connectors (ccxt, Lumibot, freqtrade, IBKR/MT5 bridges, execution engines) | SFMeridian is read-only decision support; it never places orders or books loans. |
| Crypto, DeFi, perpetuals, and prediction-market tools | Outside securities finance. |
| Technical indicators | Not a securities-lending analysis method SFMeridian needs. |
| Options, structured-product, and derivative pricers | Out of domain. |
| Sentiment and social-media APIs | No SFMeridian workflow; revisit only with a coverage row. |
| Hosted MCP servers that trade or that are proprietary data services | Read-only boundary; vendor selection is a non-goal. |
| Historical & archived projects | Unmaintained (admission rule 2). |
| Books, courses, and research repositories | Useful reading; no runtime role. Cite in agent instructions where relevant. |

## Gaps the List Does Not Cover

No entry addresses securities lending directly: none covers lendable
inventory, fee/rebate data models, recalls, or SFTR / Rule 10c-1a
reporting. Those stay with SFMeridian's own components and the existing
agents. Two needs the list does not meet and the plan already names:
a stricter SQL parser for the verifier and database drivers; both are now
catalogued above as `trial`, pending admission review.
