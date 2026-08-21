# EIA API Profile

## Use For

- Energy production, consumption, price, inventory, and forecast datasets
  from the U.S. Energy Information Administration — petroleum, natural gas,
  electricity, coal, and renewables.
- Weekly petroleum status, monthly/annual energy reviews, short-term energy
  outlook, and state/regional (SEDS) series used in commodities research,
  macro/energy features, or briefing context.

## Required Metadata

- `route` (the API v2 hierarchical path, e.g. `petroleum/stoc/wstk`)
- `series_id` when using the legacy v1-style identifier (e.g. `PET.WCRSTUS1.W`)
- `period` (date/year/month/week, per the series' frequency)
- `frequency`
- `units`
- `padd` or other regional/facet identifiers when applicable
- `release_date` when available
- `retrieved_at_utc`
- `source_url`

## Delivery Rules

- Use the v2 route-based endpoint (`/v2/{route}/data/`) with explicit
  `facets`, `data`, `frequency`, `start`, and `end` parameters rather than
  scraping a legacy series ID blindly; v1 series IDs are being phased out.
- Keep preliminary and finalized releases distinct: weekly petroleum status
  figures are preliminary and are later reconciled in the monthly/annual
  Petroleum Supply reports — do not treat a weekly pull as final.
- Preserve unit and frequency metadata explicitly; EIA mixes barrels, cubic
  feet, BTU, dollars, and index units across routes, often within the same
  dataset family.
- Record PADD or other facet/region identifiers alongside the observation;
  regional and national totals are not interchangeable.
- Store the route and series/facet combination used in each request so a
  pull can be reproduced against the same hierarchy path later.

## Risks

- Weekly and monthly figures for the same underlying series can differ
  meaningfully; joining them without a stated preliminary-vs-final policy
  introduces silent revision risk.
- The v1-to-v2 API migration changes identifier and endpoint shape; code
  written against v1 series IDs may not carry over directly.
- Unit mismatches (e.g. thousand barrels vs. barrels, nominal vs. real
  dollars) are a common source of silent scaling errors across EIA routes.
