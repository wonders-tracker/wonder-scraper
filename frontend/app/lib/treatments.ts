/**
 * Treatment color utilities
 * Single source of truth for treatment display across the app
 */

export type Treatment =
  | "Raw"
  | "Foil"
  | "Stonefoil"
  | "Gilded Foil"
  | "Serialized"
  | "Gilded Stonefoil Serialized"
  | "Holo Gilded"

export interface TreatmentStyle {
  bg: string
  text: string
  border: string
  gradient?: string
}

/**
 * Treatment color definitions
 * Ordered by rarity/value (Raw = common, Holo Gilded = ultra rare)
 */
export const TREATMENT_STYLES: Record<Treatment | string, TreatmentStyle> = {
  Raw: {
    bg: "bg-zinc-100 dark:bg-zinc-800",
    text: "text-zinc-600 dark:text-zinc-400",
    border: "border-zinc-200 dark:border-zinc-700",
  },
  Foil: {
    bg: "bg-blue-50 dark:bg-blue-950/50",
    text: "text-blue-600 dark:text-blue-400",
    border: "border-blue-200 dark:border-blue-800",
  },
  Stonefoil: {
    bg: "bg-amber-50 dark:bg-amber-950/50",
    text: "text-amber-600 dark:text-amber-400",
    border: "border-amber-200 dark:border-amber-800",
  },
  "Gilded Foil": {
    bg: "bg-yellow-50 dark:bg-yellow-950/50",
    text: "text-yellow-600 dark:text-yellow-500",
    border: "border-yellow-300 dark:border-yellow-700",
    gradient: "bg-gradient-to-r from-yellow-200 via-yellow-400 to-yellow-200 dark:from-yellow-800 dark:via-yellow-600 dark:to-yellow-800",
  },
  Serialized: {
    bg: "bg-purple-50 dark:bg-purple-950/50",
    text: "text-purple-600 dark:text-purple-400",
    border: "border-purple-200 dark:border-purple-800",
  },
  "Gilded Stonefoil Serialized": {
    bg: "bg-gradient-to-r from-amber-50 to-purple-50 dark:from-amber-950/50 dark:to-purple-950/50",
    text: "text-amber-600 dark:text-amber-400",
    border: "border-amber-300 dark:border-amber-700",
    gradient: "bg-gradient-to-r from-amber-300 via-purple-400 to-amber-300 dark:from-amber-700 dark:via-purple-600 dark:to-amber-700",
  },
  "Holo Gilded": {
    bg: "bg-gradient-to-r from-pink-50 via-purple-50 to-cyan-50 dark:from-pink-950/50 dark:via-purple-950/50 dark:to-cyan-950/50",
    text: "text-purple-600 dark:text-purple-400",
    border: "border-purple-300 dark:border-purple-700",
    gradient: "bg-gradient-to-r from-pink-400 via-purple-400 to-cyan-400 dark:from-pink-600 dark:via-purple-600 dark:to-cyan-600",
  },
}

/**
 * Get treatment style classes
 */
export function getTreatmentStyle(treatment: string | null | undefined): TreatmentStyle {
  if (!treatment) return TREATMENT_STYLES.Raw
  return TREATMENT_STYLES[treatment] || TREATMENT_STYLES.Raw
}

/**
 * Get treatment background color class
 */
export function getTreatmentBg(treatment: string | null | undefined): string {
  return getTreatmentStyle(treatment).bg
}

/**
 * Get treatment text color class
 */
export function getTreatmentColor(treatment: string | null | undefined): string {
  return getTreatmentStyle(treatment).text
}

/**
 * Get treatment border color class
 */
export function getTreatmentBorder(treatment: string | null | undefined): string {
  return getTreatmentStyle(treatment).border
}

/**
 * Check if treatment should have shimmer effect (rare)
 */
export function shouldShimmer(treatment: string | null | undefined): boolean {
  if (!treatment) return false
  return ["Gilded Foil", "Serialized", "Gilded Stonefoil Serialized", "Holo Gilded"].includes(treatment)
}

/**
 * Check if treatment should have holo effect (ultra rare)
 */
export function shouldHolo(treatment: string | null | undefined): boolean {
  if (!treatment) return false
  return treatment === "Holo Gilded"
}

/**
 * Treatment rarity order (for sorting)
 */
export const TREATMENT_ORDER: Record<string, number> = {
  Raw: 0,
  Foil: 1,
  Stonefoil: 2,
  "Gilded Foil": 3,
  Serialized: 4,
  "Gilded Stonefoil Serialized": 5,
  "Holo Gilded": 6,
}

/**
 * Sort treatments by rarity
 */
export function sortByTreatmentRarity(a: string | null | undefined, b: string | null | undefined): number {
  const orderA = TREATMENT_ORDER[a || "Raw"] ?? 0
  const orderB = TREATMENT_ORDER[b || "Raw"] ?? 0
  return orderA - orderB
}

/**
 * Get all treatment options for dropdowns
 */
export function getTreatmentOptions(): Array<{ value: string; label: string }> {
  return Object.keys(TREATMENT_STYLES).map((treatment) => ({
    value: treatment,
    label: treatment,
  }))
}
