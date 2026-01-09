## 2024-05-23 - Hardcoded SECRET_KEY in Config
**Vulnerability:** Found a hardcoded fallback value `guclu-gizli-anahtar-123` for `SECRET_KEY` in `config.py`.
**Learning:** Developers often provide fallback values for convenience during local development, but this pattern can lead to production deployments using weak, public secrets if the environment variable is forgotten.
**Prevention:** Avoid providing insecure default values for security-critical configurations. Instead, fail fast (raise an error) or generate a secure random value at runtime (with a warning) to ensure safety by default.

## 2025-01-09 - Missing Authorization in Update Endpoint (IDOR)
**Vulnerability:** The `guncelle_demirbas` endpoint lacked a check for the user's authorization level (`yetki_duzeyi`). Any logged-in user, including those with `yetki_duzeyi=0` (read-only), could send a POST request to update inventory items.
**Learning:** Relying solely on UI restrictions (hiding buttons) is insufficient security. Backend endpoints must explicitly verify permissions for every action, especially state-changing ones (POST/PUT/DELETE).
**Prevention:** Implement role-based access control (RBAC) checks at the beginning of every controller function. Use decorators or helper functions to enforce minimum privilege levels consistently.
