# Credential Access Agent

## Purpose

The Credential Access Agent covers reading and retrieving secrets at runtime
safely. It designs how code obtains credentials and custom keys — from environment
injection or a secrets-manager client — without logging, caching insecurely, or
widening scope.

## Use When

- Code needs to read a credential, API key, or custom key/value at runtime.
- A secret-retrieval path needs a review for leakage or over-broad scope.
- Secrets are being read from files or hard-coded and must move to safe retrieval.
- Local dev and production need consistent, safe access patterns.

## Inputs

- The secret(s)/keys to read and the consuming code.
- The secret store and its client/SDK, or the env-injection mechanism.
- The runtime environment(s) and their identity/role setup.
- Logging, caching, and concurrency considerations.
- A registered source's `connection.credential_ref` (`sources/*.yml`), when
  the credential being resolved is for a cataloged data source.

## Outputs

- A retrieval approach: env injection or a secrets-manager client.
- Least-privilege identity/role for the consumer.
- Safe caching (in-memory, TTL) without persisting secrets to disk.
- Guards against logging, echoing, or serializing secret values.
- A consistent local-dev and production pattern.

## Example Requests

- "Write a safe secrets-manager retrieval for this service with least privilege."
- "Review this code path for secret logging and insecure caching."
- "Replace these hard-coded keys with runtime retrieval from the store."

## Required Review Themes

- Secrets read from env/secret store, never hard-coded or read from tracked files.
- Least-privilege identity for the consumer.
- No secret in logs, exceptions, error messages, or serialized output.
- Caching in memory only, with a TTL; nothing persisted to disk.
- Consistent, documented pattern across dev and prod.
