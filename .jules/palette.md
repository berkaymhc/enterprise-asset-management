## 2024-05-23 - [Start of Journal]
**Learning:** Initial setup.
**Action:** Ready to record UX learnings.

## 2024-05-23 - [Password Visibility Toggle]
**Learning:** Users often mistype passwords on mobile devices or when caps lock is accidentally on. Standard password inputs provide no feedback on the actual characters entered.
**Action:** Implemented a visibility toggle on the login screen. This small addition significantly reduces login frustration and support tickets related to "forgotten passwords" which were actually just typos.

## 2026-01-09 - [Search Bar Accessibility]
**Learning:** Search inputs often lack associated labels when designed as "icon-only" or "placeholder-only" elements in dense navbars. This renders them invisible or confusing to screen reader users who cannot rely on visual context. Adding `role="search"` and proper labels drastically improves the navigation experience for these users.
**Action:** Added `aria-label`, `title`, and a visually hidden `<label>` to the main search form. Used `visually-hidden` utility class to maintain the clean visual design while adhering to WCAG standards.

## 2026-01-10 - [Icon-Only Button Tooltips]
**Learning:** Icon-only buttons (like Edit/Delete) save space but are ambiguous to users unfamiliar with the iconography. They also fail accessibility standards if they lack textual labels. Bootstrap tooltips improve confidence for mouse users, while `aria-label` is critical for screen readers.
**Action:** Added `aria-label` and `title` attributes to all action buttons in the main data tables. Implemented a reusable `.js-tooltip` class to initialize Bootstrap tooltips globally, ensuring consistent behavior across the application without inline script repetition.
