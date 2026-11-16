# Connector integration review — 2026-11-16

Parent #7 was merged normally at `09427b15f07e23ae395225b76ce221d1919cd504` after
rechecking its unchanged head, all four successful hosted checks, and empty review
submissions/threads. Main was merged into this child without conflicts or rewriting
history. This child has separate changes and requires its own exact-head checks.

## Malformed upstream Unicode regression

The integration review found that JSON escapes can decode to unpaired surrogates.
The connector accepted these strings, but evaluation then raised `UnicodeEncodeError`
while hashing the output, leaving the persisted run `running`. An ad-hoc prediction
could similarly fail while serializing its response. This is an upstream protocol
failure and must be represented as a bounded failure, not an uncaught server error.

Before the fix, new real-loopback HTTP tests produced **four failures and one pass**:
high/low surrogate transport rejection and persisted interruption/retry failed;
valid non-BMP text passed. After adding strict UTF-8 encoding validation inside the
existing completion-validation boundary, **37 focused API/identity/import tests
passed** locally on Windows. The resulting `UnicodeEncodeError` is a `ValueError`,
so the existing sanitized `RuntimeFault` path handles it without broadening exception
handling. Valid emoji text is preserved, not normalized or stripped.

Tests inspect the saved run after the response, its failed connection and interrupted
history entry, the absent second-case request and the blocked implicit retry. After
explicit reconnection, both cases execute again, producing one exact match and one
unscored observation. The installed connector harness additionally injects malformed
Unicode into a prediction and requires the sanitized 409 plus saved failed state,
then retains the previous HTTP-500/evaluation/retry checks.

## Evidence boundaries

The earlier 596-test result and Windows/Linux ZIP receipts at `64798eb` remain
historical evidence for that application revision. The Unicode fix changes executable
code; those receipts do not certify this newer ZIP. Fresh installed and final-head
local/hosted results must be recorded separately. No model, GPU inference, acceptance
threshold or historical performance measurement is changed by this correction.

Native Windows fresh-profile onboarding, actual participant comprehension, native
file-picker usability and real-model/server compatibility remain unverified. All
authored HTTP responses are protocol fixtures, not learned model output.
