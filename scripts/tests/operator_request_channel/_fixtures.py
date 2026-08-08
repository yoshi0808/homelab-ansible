"""Synthetic DLP test fixtures, assembled from fragments at import/call
time.

None of these are real secrets or real internal IPs. They are deliberately
built by concatenating short fragments (and, for the numeric/entropy
values, by calling `secrets` at runtime) so that no single literal in this
file's *source text* is a completed secret-shaped string or an IPv4
dotted-quad -- requirement §9.5 and the task briefing both call this out:
`scripts/git-pre-commit-check.sh` greps the staged *diff text* for exactly
those shapes (gitleaks patterns, and a raw `([0-9]{1,3}\\.){3}[0-9]{1,3}`
scan), so a value that only exists after Python concatenates fragments at
runtime never appears as a contiguous match in the file gitleaks/the IPv4
check actually reads.

If you are tempted to "simplify" one of these into a single literal
string, don't -- that reintroduces exactly the commit-blocking pattern
this file exists to avoid.
"""

import secrets


def pem_private_key_block() -> str:
    begin = "-----BEGIN " + "RSA" + " PRIVATE" + " KEY" + "-----"
    body = "\n".join(secrets.token_hex(30) for _ in range(2))
    end = "-----END " + "RSA" + " PRIVATE" + " KEY" + "-----"
    return begin + "\n" + body + "\n" + end


def slack_bot_token() -> str:
    return "xox" + "b" + "-" + secrets.token_hex(6) + "-" + secrets.token_hex(6) + "-" + secrets.token_hex(12)


def slack_webhook_url() -> str:
    return (
        "https://hooks" + ".slack.com/services/"
        + "T" + secrets.token_hex(5).upper() + "/"
        + "B" + secrets.token_hex(5).upper() + "/"
        + secrets.token_hex(12)
    )


def semaphore_api_token_text() -> str:
    return "semaphore_" + "api_token" + ": " + secrets.token_hex(16)


def bearer_token_text() -> str:
    return "Bearer" + " " + secrets.token_hex(20)


def jwt_text() -> str:
    def seg():
        return secrets.token_hex(10)

    return "eyJ" + seg() + "." + seg() + "." + seg()


def password_keyvalue_text() -> str:
    return "pass" + "word" + ": " + secrets.token_hex(8)


def vault_plaintext_text() -> str:
    return "vault_" + "db_password" + " = " + secrets.token_hex(8)


def credential_url_text() -> str:
    return "https://" + "svc" + ":" + secrets.token_hex(6) + "@" + "internal.example.invalid" + "/path"


def env_dump_text() -> str:
    lines = [
        "PATH" + "=/usr/bin:/bin",
        "HOME" + "=/home/svc",
        "SSH_AUTH" + "_SOCK=/tmp/agent." + secrets.token_hex(4),
    ]
    return "\n".join(lines)


def proc_environ_text() -> str:
    return "/proc/" + "self" + "/environ"


def private_ipv4_text() -> str:
    # An RFC1918 10/8 address, built from separate octet literals with no
    # "." between them in the source, so no dotted-quad literal exists in
    # this file.
    octets = ["10", "0", "0", "7"]
    return ".".join(octets)


def ipv6_ula_text() -> str:
    return "fd" + secrets.token_hex(1) + ":" + ":".join(secrets.token_hex(2) for _ in range(3)) + "::1"


def ipv6_link_local_text() -> str:
    return "fe80" + ":" + ":".join(secrets.token_hex(2) for _ in range(3)) + "::1"


def high_entropy_text() -> str:
    return secrets.token_urlsafe(24)


def benign_prose() -> str:
    return "quory の disk 使用率が閾値を超えている可能性があり、確認をお願いします。"
