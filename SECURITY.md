# Security

This is a loopback-only personal workbench. Do not expose it directly to the internet or run multiple workers against one database. Local roles do not provide tenant isolation.

- No default users/passwords; the first account becomes owner. Passwords use salted PBKDF2; opaque tokens are hashed at rest and expire after12hours. Logout revokes the token.
- Host/origin checks reduce DNS rebinding and cross-site bootstrap risks. Keep your local machine/browser secure: tokens live in browser localStorage and local administrators can read the database.
- Paid provider planning is disabled by default and owner-only. The server reads its own environment key; never paste credentials into scenario text, JSON, issues or a commit.
- XML imports are bounded and reject DTD/entity declarations and unknown semantic features. Scenario data is never evaluated as Python/shell code.
- The optional runner starts an explicitly configured local script without a shell. Only trusted maintainers should configure it. A simulator may retain state after a crash; inspect it before reusing it.

Report vulnerabilities through the repository's private vulnerability-reporting feature if enabled. Otherwise open an issue with only a high-level description and ask for a private channel; do not post exploit details, tokens or real scenario data publicly.

Version0.1.x is the currently supported release line. Security testing is bounded; passing unit tests is not a security certification.
