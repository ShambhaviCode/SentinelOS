# Security model

## What SentinelOS is

A policy decision point that evaluates an AI agent's inputs and proposed actions before
they proceed. It demonstrates three protections:

1. Prompt injection in content the agent reads.
2. Sensitive data in the agent's context or leaving the device.
3. Tool requests that exceed what the task needs, or that are inherently risky.

## Threat taxonomy

| Category | Examples detected | Default outcome |
|---|---|---|
| Prompt injection | "ignore your previous instructions", "reveal the system prompt", "you are now unrestricted", "do not tell the user" | Block when rule evidence is strong; review when only the model is confident |
| Data exposure | API tokens, private keys, passwords, card numbers (Luhn-checked), ID formats, email, phone | Review if in context; block if leaving the device |
| Excessive privilege | Recursive, profile-wide or drive-wide file access; vague justifications | Block (recursive/profile/drive), review (directory) |
| Unsafe tool use | Shell commands, destructive file operations | Review by default; block for listed patterns |
| Suspicious destination | Network or email destinations outside the allowlist | Review |
| Policy violation | Sensitive paths such as `.ssh`, `.aws`, credential files | Block |

## Trust boundaries

- **Untrusted context** (documents, web pages, email) is the main injection vector and is
  weighted at 1.0. The user's own prompt is weighted at 0.9; trusted context at 0.7.
- **Tool requests in the same turn as a likely injection are blocked** (policy XC-01),
  because the request may be attacker-influenced even if it looks harmless.
- **Secrets never reach the UI or audit log in full.** The data scanner redacts
  secret-class matches to the first four and last two characters.

## Operational security of SentinelOS itself

- The server binds to `127.0.0.1` only and limits request bodies to 256 KB.
- The analysis path makes no network calls. The only network activity is the UI's
  status probe (a TCP connect to 1.1.1.1:443, used to display online or offline), which
  sends no data.
- Tool execution is simulated. SentinelOS never runs commands or touches the files named in
  requests.
- All demo data is synthetic (see `demo/README.md`).

## Limitations (stated plainly)

- **Pattern-based detection finds known patterns.** Novel phrasings, other languages,
  encoded payloads (base64, homoglyphs) and multi-turn attacks can evade the rules. The ML
  classifier narrows but does not close this gap, and its accuracy on out-of-distribution
  text is not established here.
- **Sensitive data detection is format-based.** It will miss secrets without a recognizable
  shape and can flag look-alike numbers.
- **The agent is simulated.** SentinelOS is not yet integrated with a production agent
  framework; integration would be through the same `/api/analyze` contract.
- **No authentication on the local API.** Acceptable for a single-user local demo, not for
  shared deployment.
- **Not a guarantee.** SentinelOS reduces risk; it does not make an agent secure.
