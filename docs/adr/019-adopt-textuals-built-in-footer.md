# ADR 019: Adopt Textual's Built-in Footer Widget

**Status:** Accepted
**Date:** 2025-10-08
**Deciders:** Project Team
**Tags:** ui, refactoring, user-experience, textual

---

## Context
The ChatScreen currently implements a custom footer using a Static widget with the ID #status-line. This widget is styled to sit at the bottom of the screen and is manually updated to show application state, such as "Processing..." or "Safety: ON/OFF".

This home-grown approach presents several issues:

It's not idiomatic: It bypasses Textual's standard Footer widget, which is designed for this exact purpose.

Lacks discoverability: The primary function of a Textual footer is to display available key bindings. Our custom solution does not do this automatically, forcing users to remember shortcuts or open the command palette.

Maintenance overhead: It requires custom CSS and Python code to manage its state and appearance, which could be handled by the framework.

Inconsistency: The main application class, ADHApp, already composes a global Footer widget, but the custom status line in ChatScreen overrides or duplicates its role, leading to an inconsistent UI.

## Decision
We will adopt Textual's built-in Footer widget as the standard for displaying key bindings and persistent bottom-of-screen information. This involves removing the custom Static widget (#status-line) and its associated logic from the ChatScreen. The global Footer instance composed in ADHApp will now be responsible for this part of the UI across all screens.

## Implementation
Remove the Static widget: Delete the Static widget with id="status-line" from the compose() method of adh_cli/screens/chat_screen.py.

Remove associated code: Delete all Python code that updates the status line, such as self.query_one("#status-line", Static).update(...).

Remove CSS: Delete the CSS rules for #status-line from the ChatScreen.CSS definition.

Rely on the global Footer: The Footer already present in adh_cli/app.py will now be visible and will automatically display the BINDINGS defined in the active ChatScreen.

## Consequences

### Positive
Improved Discoverability: The Footer automatically displays key bindings from the App and the active Screen, making the application easier to use.

Code Simplification: We can remove the custom Static widget, its CSS, and the Python logic used to update it. This reduces the amount of code to maintain.

Consistency: The application will use a standard, framework-provided component, leading to a more consistent and predictable user experience.

Maintainability: Adding or changing key bindings on a screen will automatically be reflected in the footer without any extra work.

### Negative
Loss of Custom Status Text: The #status-line was used to display dynamic status text (e.g., "Processing...", "Safety: ON/OFF"). This information will no longer appear in the footer.

Mitigation: This is a worthwhile trade-off. Dynamic status information is better suited for other UI elements like notifications (app.notify), the title of the RichLog, or as temporary messages within the chat log itself. The footer's primary role should be for key bindings.

### Risks
The risk is minimal. The main consideration is ensuring that important status information previously shown in the status line is relocated to a suitable place in the UI.

## Alternatives Considered

### Alternative 1: Keep the Custom Status Line
Continue using the existing Static widget.

Pros: No code changes are required.

Cons: It does not display key bindings, is not idiomatic, and requires manual maintenance.

Rejected because: The benefits of adopting the standard Footer far outweigh the convenience of leaving the current implementation as-is.

### Alternative 2: Enhance the Custom Status Line to Show Bindings
Add logic to the ChatScreen to manually fetch the BINDINGS and render them into the Static widget.

Pros: Would provide full control over the footer's content.

Cons: This amounts to re-implementing the Footer widget, which is complex, brittle, and unnecessary.

Rejected because: It is significantly more work and less maintainable than using the built-in component.

## Implementation Notes
The changes are confined to adh_cli/screens/chat_screen.py.

No changes are needed in adh_cli/app.py, as it already correctly composes a global Footer.

The BINDINGS class attribute in ChatScreen will now be automatically rendered by the Footer.

## References
Textual Footer Widget Documentation: https://textual.textualize.io/widgets/footer/

Related ADRs: ADR-013 (UI Design System)

Relevant Files: adh_cli/app.py, adh_cli/screens/chat_screen.py

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2025-10-08 | Initial decision | Project Team |
