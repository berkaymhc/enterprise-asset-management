## 2024-05-23 - Hardcoded SECRET_KEY in Config
**Vulnerability:** Found a hardcoded fallback value `guclu-gizli-anahtar-123` for `SECRET_KEY` in `config.py`.
**Learning:** Developers often provide fallback values for convenience during local development, but this pattern can lead to production deployments using weak, public secrets if the environment variable is forgotten.
**Prevention:** Avoid providing insecure default values for security-critical configurations. Instead, fail fast (raise an error) or generate a secure random value at runtime (with a warning) to ensure safety by default.
