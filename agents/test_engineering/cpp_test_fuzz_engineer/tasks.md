# C++ Test & Fuzz Engineer Tasks

## Write Unit Tests For A Class Or Function

Input: C++ code needing test coverage.

Output: GoogleTest or Catch2 tests grounded in the code's actual contract,
plus named remaining gaps.

## Build A Fuzz Harness

Input: an untrusted-input-handling function (parser, deserializer, decoder)
the requester confirms they own or are authorized to test.

Output: a libFuzzer or AFL++ harness scoped to that function, a seed corpus
approach, sanitizer build flags (ASan/UBSan minimum), and how to run it
locally.

## Triage A Crash

Input: a crashing input and its stack trace or sanitizer report.

Output: the minimized reproducer, the faulting function, the defect class,
and a suggested fix direction (not a fix itself, unless asked).
