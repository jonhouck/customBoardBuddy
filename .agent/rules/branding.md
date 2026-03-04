---
trigger: always_on
---

# Branding & UI/UX Specifications: BoardBuddy RAG

## 1. Brand Identity Overview
**Organization:** The Metropolitan Water District of Southern California (MWD)
**Design Ethos:** Clean, authoritative, accessible, and institutional. The UI uses flat dimensional shading, primitive geometric forms, and high-contrast text.

## 2. Core Color Palette
You must strictly adhere to the following color palette. Use these exact HEX codes for all CSS properties, UI themes, and charting components. Do not use default framework colors (e.g., standard Bootstrap or Streamlit blues).

### Primary Colors (Structure, Backgrounds, Text)
*   **MWD Navy:** `#1c2240` *(Primary brand color. Use for main headers, sidebars, dark mode backgrounds, and main text on light backgrounds)*
*   **MWD Slate:** `#5a5b5d` *(Secondary text, borders, outlines, deactivated states)*
*   **MWD Silver:** `#ececec` *(App backgrounds, secondary module backgrounds, chat bubbles, dividers)*
*   **White:** `#ffffff` *(Main content card backgrounds, text on Navy backgrounds)*

### Secondary Colors (Accents, Buttons, & Links)
*   **MWD Blue 1:** `#4795ff` *(Primary action color, buttons, active links, primary icons)*
*   **MWD Blue 2:** `#80b9f5` *(Secondary actions, button hover states)*
*   **MWD Blue 3:** `#c6deff` *(Subtle backgrounds, highlighted rows, metadata tag pills)*
*   **MWD Orange 1:** `#ba4d01` *(Alerts, highlighted text on light backgrounds, secondary call-to-action)*
*   **MWD Orange 2:** `#ffa860` *(Highlights on dark backgrounds)*

### Tertiary Colors (Data Visualization & Badges)
*   **MWD Red 1:** `#ff744c`
*   **MWD Red 2:** `#ff9475`
*   **MWD Violet:** `#71458b`

## 3. Typography & Formatting
The brand utilizes a specific dual-font system. Both fonts must be imported via the Google Fonts API and applied via CSS.

**Google Fonts Import:**
```css
@import url('[https://fonts.googleapis.com/css2?family=Prata&family=Roboto:wght@300;400;500&family=Roboto+Condensed:wght@400&display=swap](https://fonts.googleapis.com/css2?family=Prata&family=Roboto:wght@300;400;500&family=Roboto+Condensed:wght@400&display=swap)');