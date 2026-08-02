PROTOCOL_VERSION = "universal-core-blind-eval-v1"
FROZEN_CORE_COMMIT = "89a54d44d0ef3a4f1078cdad9a15564b3b31ecd9"
ARCHIVE_BRANCH = "archive/universal-bbeh-dual-track-4520-2026-07-28"
ARCHIVE_COMMIT = "a0c099a41c85f267ca6323235a019b2052107873"
MIN_NONCE_BYTES = 32
ZERO_DIGEST = "0" * 64
FORBIDDEN_PUBLIC_KEYS = frozenset({
    "target", "targets", "answer", "answers", "label", "labels", "gold",
    "family", "family_id", "task_family", "generalization_level", "level",
    "generator", "generator_source", "private_notes", "routing_hint",
})
