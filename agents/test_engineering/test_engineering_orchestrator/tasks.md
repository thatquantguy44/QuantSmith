# Test Engineering Orchestrator Tasks

## Route A Single-Language Request

Input: code or a repo section in one clear language.

Output: the specialist routed to, and their output passed through with a
named downstream handoff.

## Route A Multi-Language Request

Input: a repo or change spanning more than one language (e.g. a Python
backend and a TypeScript frontend).

Output: each applicable specialist's findings, consolidated into one
summary with overlaps/gaps between them called out, and one handoff line.

## Disambiguate An Unclear Stack

Input: a request that doesn't name a language, or files with ambiguous or
misleading extensions.

Output: the actual signal used to detect the language(s) (build/config file,
code content), the specialist(s) routed to, and their consolidated output.
