# Credit Risk Source and Evidence Policy (spec `0072`)

How this pack decides what counts as evidence, what to do when sources
disagree, and what may never be stored here.

## Evidence hierarchy

Higher authority wins on the specific point it actually addresses — not on
adjacent points it merely touches.

1. **Statute and regulation.** Binding rule text (for example ECOA and
   Regulation B for adverse action).
2. **Accounting standards.** Standard-setter material for impairment and
   expected credit loss.
3. **Capital framework and national implementing rules.** The international
   framework is *not* the applicable rule for any institution; where the two
   differ, national implementation governs and the record must say which it
   describes.
4. **Supervisory guidance.** Bulletins and handbooks. Guidance is not
   regulation, and a derived record must preserve that distinction rather than
   flatten both into "the rule".
5. **Supervisory scenarios, instructions, and reporting forms.**
6. **Official statistical publishers** already registered under `0027`, used as
   scenario drivers with vintage controls.
7. **Rating agency and vendor methodology**, by public locator only.
8. **Reviewed internal policy.**
9. **Analyst interpretation**, always labeled, never promoted above its
   evidence.

A record cites the specific document or dataset version it uses. Membership in
a tier is not evidence by itself.

## Conflict resolution

When two sources disagree:

1. If they address different jurisdictions, scopes, or periods, they do not
   conflict — the record is under-specified. Add the missing field.
2. If they genuinely conflict on the same point, the higher tier governs, and
   the conflict is **retained visibly** on the record rather than silently
   resolved.
3. If they are the same tier, the record stays `draft` with both cited and the
   conflict named. An unresolved conflict is information, not a defect to hide.

## Time

Two independent axes, never collapsed:

- `knowledge_as_of` — when the library could have known this.
- `effective_from` / `effective_to` — when the underlying rule applies.

A standard issued today and effective in two years is knowable now and
applicable later. A historical question passes the knowledge check first, then
the effective check. Getting this wrong lets a later rule silently rewrite an
earlier answer, which is the failure mode `rule.pit.scenario_vintage` and
`rule.pit.restatement_backfill` exist to prevent.

## Freshness

Regulatory, accounting, and supervisory records carry a review date. A record
whose source has been amended, superseded, or rescinded since its review date is
stale, and staleness is a `reviewed`-promotion blocker — not a warning. A
rescinded bulletin remains the correct authority for a historical period and is
marked `superseded`, never deleted.

## Licensing and what is never stored

Several bodies in the hierarchy above license their full text. This pack stores
**definitions, identifiers, structure, formulas, and public locators** — never
reproduced regulation, standard, codification, master-agreement, or vendor
methodology text.

Never stored here, permanently and by requirement (`0072` NFR-006):

- consumer PII, credit files, and loan-level tapes;
- bureau attribute values;
- internal counterparty terms and pricing;
- MNPI, secrets, and credentials;
- licensed vendor documentation and rating-agency methodology text.

Every committed example is synthetic and disclosed per `0025`. This is not a
handling rule to be applied carefully — it is a prohibition, because the
re-identification and licensing risks have no version of "careful" that makes
them acceptable in a public scaffold.

## Not a compliance determination

Registering a source identifies authoritative material so a derived rule can
cite it with a jurisdiction and an effective interval. Whether a rule applies to
a particular institution, product, or exposure is a qualified owner's decision,
not this pack's.
