# Fixture-Backed Market Text Prompt

System: summarize the supplied public market context into one structured signal
record. Use only the provided context and the declared fixture response.

Inputs:

- `as_of_date`
- `source_id`

Return JSON with `theme`, `sentiment`, and `confidence`.
