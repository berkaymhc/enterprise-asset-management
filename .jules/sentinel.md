## 2024-05-24 - [CSRF via GET Requests for Destructive Actions]
**Vulnerability:** The application exposed critical destructive actions (resetting the entire database) via GET requests (`/sifirla-demirbas`, `/sifirla-personel`). This allowed potential Cross-Site Request Forgery (CSRF) attacks, where a malicious link could trigger these actions if an admin visited it.
**Learning:** Destructive actions must always use HTTP methods that do not support caching or pre-fetching (POST, PUT, DELETE) and must be protected by CSRF tokens. Relying on `login_required` and `yetki_duzeyi` checks is insufficient if the endpoint is accessible via GET.
**Prevention:**
1. Use `methods=['POST']` for all routes that modify state.
2. Ensure `Flask-WTF` CSRF protection is enabled (which it is).
3. Update frontend logic to use forms (or fetch with CSRF headers) instead of simple links (`window.location.href`) for these actions.
