"""Custom theme for ADH CLI application.

This module defines the ADH theme with custom colors optimized for
AI-assisted development workflows. The theme supports both light and dark
modes and follows Textual's design system principles.
"""

from textual.theme import Theme


# ADH Dark Theme - Professional dark color scheme
ADH_DARK = Theme(
    name="adh-dark",
    # Primary colors - Blue-based for trust and professionalism
    primary="#4A9EFF",  # Bright blue for primary actions
    secondary="#7B68EE",  # Purple for secondary elements
    # Background colors - Dark with subtle variations
    background="#0F1419",  # Deep charcoal for main background
    surface="#1A1F26",  # Slightly lighter for surfaces
    panel="#252B35",  # Even lighter for panels/cards
    # Semantic colors
    accent="#00D4AA",  # Teal for highlights and accents
    warning="#FFB648",  # Warm orange for warnings
    error="#FF5C5C",  # Bright red for errors
    success="#00D98C",  # Green for success states
    # Text colors - High contrast for readability
    foreground="#E8E8E8",  # Primary text color
    # Additional customizations
    variables={
        # Text hierarchy
        "text-primary": "#E8E8E8",
        "text-secondary": "#B8B8B8",
        "text-muted": "#888888",
        "text-disabled": "#555555",
        # Inverse text (for colored backgrounds)
        "text-on-primary": "#FFFFFF",
        "text-on-warning": "#1A1F26",
        "text-on-error": "#FFFFFF",
        "text-on-success": "#1A1F26",
        # Interactive states
        "primary-hover": "#5AAFFF",
        "primary-active": "#3A8EEF",
        # Borders
        "border": "#404854",
        "border-focus": "#4A9EFF",
        "border-error": "#FF5C5C",
        # Special colors for policy/risk levels
        "risk-none": "#888888",
        "risk-low": "#00D98C",
        "risk-medium": "#FFB648",
        "risk-high": "#FF8C42",
        "risk-critical": "#FF5C5C",
        # Tool execution states
        "execution-pending": "#7B68EE",
        "execution-running": "#4A9EFF",
        "execution-success": "#00D98C",
        "execution-failed": "#FF5C5C",
        "execution-blocked": "#FF8C42",
        # Chat colors (replacing hardcoded cyan/green)
        "chat-user": "#4A9EFF",
        "chat-ai": "#00D4AA",
        "chat-system": "#7B68EE",
        # Spacing scale (in cells)
        "space-xs": "0",
        "space-sm": "1",
        "space-md": "2",
        "space-lg": "4",
        "space-xl": "8",
        # Content width constraints
        "content-max-width": "120",  # Max width for readable content
        "chat-max-width": "100",  # Max width for chat messages
        "form-max-width": "80",  # Max width for forms
    },
)


# ADH Light Theme - Clean light color scheme
ADH_LIGHT = Theme(
    name="adh-light",
    # Primary colors - Deeper blues for light mode
    primary="#2563EB",  # Rich blue
    secondary="#7C3AED",  # Deep purple
    # Background colors - Light with subtle variations
    background="#FFFFFF",  # Pure white background
    surface="#F9FAFB",  # Light gray for surfaces
    panel="#F3F4F6",  # Slightly darker for panels
    # Semantic colors - Adjusted for light backgrounds
    accent="#0D9488",  # Deeper teal
    warning="#F59E0B",  # Amber for warnings
    error="#DC2626",  # Deep red for errors
    success="#10B981",  # Emerald for success
    # Text colors - Dark for readability
    foreground="#1F2937",  # Almost black for text
    # Additional customizations
    variables={
        # Text hierarchy
        "text-primary": "#1F2937",
        "text-secondary": "#4B5563",
        "text-muted": "#9CA3AF",
        "text-disabled": "#D1D5DB",
        # Inverse text
        "text-on-primary": "#FFFFFF",
        "text-on-warning": "#1F2937",
        "text-on-error": "#FFFFFF",
        "text-on-success": "#FFFFFF",
        # Interactive states
        "primary-hover": "#1D4ED8",
        "primary-active": "#1E40AF",
        # Borders
        "border": "#E5E7EB",
        "border-focus": "#2563EB",
        "border-error": "#DC2626",
        # Special colors for policy/risk levels
        "risk-none": "#9CA3AF",
        "risk-low": "#10B981",
        "risk-medium": "#F59E0B",
        "risk-high": "#F97316",
        "risk-critical": "#DC2626",
        # Tool execution states
        "execution-pending": "#7C3AED",
        "execution-running": "#2563EB",
        "execution-success": "#10B981",
        "execution-failed": "#DC2626",
        "execution-blocked": "#F97316",
        # Chat colors
        "chat-user": "#2563EB",
        "chat-ai": "#0D9488",
        "chat-system": "#7C3AED",
        # Spacing scale
        "space-xs": "0",
        "space-sm": "1",
        "space-md": "2",
        "space-lg": "4",
        "space-xl": "8",
        # Content width constraints
        "content-max-width": "120",
        "chat-max-width": "100",
        "form-max-width": "80",
    },
)


def get_themes():
    """Get all ADH themes.

    Returns:
        Dict mapping theme names to Theme objects
    """
    return {
        "adh-dark": ADH_DARK,
        "adh-light": ADH_LIGHT,
    }
