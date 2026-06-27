# Security Policy

## Reporting a vulnerability

Please report security issues **privately** — use GitHub's *"Report a
vulnerability"* button on the repository's **Security** tab
(<https://github.com/gmarav/DeACED/security/advisories>). Do not open a public
issue for a security report. You can expect an initial response within a few
days.

## Scope and threat model

DeACED parses **untrusted, attacker-controlled** Java serialization streams — that
is its purpose — so two properties matter for using it safely:

- **It never deserializes Java objects.** DeACED only reads and decodes the byte
  stream into a descriptive tree; it does not load classes, instantiate objects,
  or invoke `readObject` / `readResolve`. The classic Java deserialization gadget
  chains cannot execute through DeACED.
- **It fails cleanly on malformed input.** Truncated or structurally-invalid
  streams raise a `deaced.errors.SerDumpError` carrying the byte offset. Negative
  lengths/counts are rejected rather than driving large allocations, and deeply
  nested streams raise an error rather than overflowing the interpreter stack.

Resource use is still proportional to input size: a multi-gigabyte stream yields
a correspondingly large parse. Apply your own size limits when feeding DeACED
data from the network.

## Supported versions

DeACED is pre-1.0; security fixes are applied to the latest released version.
