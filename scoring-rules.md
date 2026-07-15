# Scoring Rules

## Overview

Standings are calculated per Season.

Each player's seasonal standing is determined by summing their **Top 5 highest scoring events**.

---

## Calculation Logic

For each player in a season:

1. Retrieve all event results.
2. Extract points.
3. Sort points descending.
4. Select the top 5 values.
5. Sum those values.

If a player has fewer than 5 events:
- Sum all available events.

---

## Example

Player scores across 6 events:

[12, 6, 18, 0, 9, 20]

Sorted:

[20, 18, 12, 9, 6, 0]

Top 5:

[20, 18, 12, 9, 6]

Total = 65

---

## Tie-Breakers (Planned)

**TO BE UPDATED**

---

## Season Reset

- Standings do not carry across seasons.
- Each season is calculated independently.
- Players persist, but statistics reset.

---

## Data Integrity

- Calculations are performed dynamically from stored results.
- No manual editing of standings totals allowed.
- All standings derive from raw event results.

---

## Future Rule Changes

If scoring rules change:

- Raw results remain intact.
- Calculation logic can be versioned.
- Historical seasons can optionally retain legacy rule versions.
