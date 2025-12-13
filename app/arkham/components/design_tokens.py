"""
Design tokens for consistent spacing, typography, and styling across the app.
"""

# Spacing scale (Radix Themes enum values: 0-9, maps to 0rem - 2rem)
# Note: These are Radix enum strings, not CSS values
SPACING = {
    "xs": "1",   # 0.5rem / 8px
    "sm": "2",   # 0.75rem / 12px
    "md": "3",   # 1rem / 16px
    "lg": "4",   # 1.5rem / 24px
    "xl": "5",   # 2rem / 32px
    "2xl": "6",  # 2.5rem / 40px
    "3xl": "7",  # 3rem / 48px
}

# Typography scale
FONT_SIZE = {
    "xs": "0.75rem",  # 12px
    "sm": "0.875rem",  # 14px
    "md": "1rem",  # 16px
    "lg": "1.125rem",  # 18px
    "xl": "1.25rem",  # 20px
    "2xl": "1.5rem",  # 24px
    "3xl": "1.875rem",  # 30px
    "4xl": "2.25rem",  # 36px
}

# Font weights
FONT_WEIGHT = {
    "normal": "400",
    "medium": "500",
    "semibold": "600",
    "bold": "700",
}

# Border radius
RADIUS = {
    "none": "0",
    "sm": "0.125rem",  # 2px
    "md": "0.375rem",  # 6px
    "lg": "0.5rem",  # 8px
    "xl": "0.75rem",  # 12px
    "full": "9999px",
}

# Z-index scale
Z_INDEX = {
    "base": "0",
    "dropdown": "1000",
    "sticky": "1100",
    "modal": "1200",
    "popover": "1300",
    "toast": "1400",
}

# Breakpoints for responsive design
BREAKPOINTS = {
    "sm": "640px",
    "md": "768px",
    "lg": "1024px",
    "xl": "1280px",
    "2xl": "1536px",
}

# Component-specific constants
SIDEBAR_WIDTH = "240px"
HEADER_HEIGHT = "64px"
CONTENT_MAX_WIDTH = "1400px"

# Page padding
PAGE_PADDING = {
    "x": SPACING["lg"],  # horizontal
    "y": SPACING["lg"],  # vertical
}

# Card styling
CARD_PADDING = SPACING["md"]
CARD_GAP = SPACING["md"]

# Common box shadow values
SHADOW = {
    "sm": "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
    "md": "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
    "lg": "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
    "xl": "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
}
