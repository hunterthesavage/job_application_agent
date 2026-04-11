# Roleworthy Design System v1

## Purpose

This document defines the visual and interaction system for Roleworthy. It ensures consistent, high-quality UI across all screens and prevents design drift during development.

---

# 1. Brand Principles

* Precise, trustworthy, and selectively bold
* Clean and easy at first glance
* Calm by default, expressive when it matters
* Focused on decision-making, not decoration

---

# 2. Color System

## Core Meaning

* Blue = structure, system, trust
* Amber = action, importance, decision
* Red = destructive actions only
* Green = success states only

## Tokens

### Background

* bg.primary = #0B0F17
* bg.surface = #111827
* border.subtle = #1F2937

### Brand (Blue)

* brand.primary = #3B82F6
* brand.hover = #2563EB
* brand.soft = #60A5FA

### Action (Amber)

* action.primary = #F59E0B
* action.hover = #FBBF24
* action.deep = #D97706

### Text

* text.primary = #F9FAFB
* text.secondary = #9CA3AF
* text.muted = #6B7280

---

# 3. Typography

* Font: Inter or system equivalent
* No serif fonts
* No decorative fonts

## Scale

* h1: 28px semibold
* h2: 22px semibold
* body: 14–16px regular
* label: 12px medium

---

# 4. Layout System

* Use 8px spacing grid
* Standard spacing: 8 / 16 / 24 / 32
* Border radius: 8–12px
* Avoid dense stacking unless necessary

---

# 5. Component Rules

## Buttons

Primary:

* Use for ONE key action per screen
* Color: amber
* Meaning: “do this now”

Secondary:

* Neutral, bordered
* Meaning: available but not urgent

Ghost:

* Minimal emphasis
* Meaning: optional

---

## Cards

* Background: bg.surface
* Border: subtle
* Padding: 16–24px
* Clean, not heavy
* Used for jobs, insights, sections

---

## Inputs

* Minimal styling
* Blue focus state
* No heavy shadows or decoration

---

# 6. Signal System (Core Differentiator)

## Pulse Line

Represents activity, opportunity flow, and system intelligence

## Node (Critical)

Represents:

* key opportunity
* decision moment
* “this matters”

## Usage

Use pulse + node for:

* recommended jobs
* high-fit roles
* insights
* timing signals

## Rules

* Do not overuse
* Do not stack multiple nodes unnecessarily
* Do not animate excessively

---

# 7. UI Behavior Rules

* Calm by default
* Important elements stand out clearly
* One primary action per section
* Avoid visual noise
* Use spacing before adding UI elements

---

# 8. Implementation Guidance

* Prefer updating shared components over styling individual screens
* Avoid inline styles where possible
* Centralize tokens (CSS variables or theme file)
* Preserve existing UX flow while upgrading visuals

---

# 9. Design Goal

Roleworthy should feel like:

* a clear, intelligent system
* helping users make confident career decisions
* not a cluttered job board or internal tool
