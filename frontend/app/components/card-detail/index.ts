/**
 * Card Detail Page Components
 *
 * TCGPlayer-inspired layout system for card detail pages.
 * @see tasks.json for full implementation plan
 */

// Layout components
export {
  CardDetailLayout,
  Section,
  SectionLoadingSkeleton,
  TwoColumnSection,
  SectionDivider
} from './CardDetailLayout'
export type { SectionProps } from './CardDetailLayout'

// CardHero component
export { CardHero, CardHeroSkeleton } from './CardHero'
export type { CardHeroProps } from './CardHero'

// PriceBox component
export { PriceBox, PriceBoxSkeleton } from './PriceBox'
export type { PriceBoxProps, TreatmentOption, PriceSource, PlatformPrice, ProductDetails } from './PriceBox'

// ListingsPanel component
export {
  ListingsPanel,
  ListingsPanelComponents
} from './ListingsPanel'
export type {
  ListingsPanelProps,
  Listing,
  ListingPlatform
} from './ListingsPanel'

// PriceAlertModal component
export { PriceAlertModal } from './PriceAlertModal'
export type { PriceAlertModalProps, PriceAlertType } from './PriceAlertModal'

// PricePoints component
export { PricePoints, PricePointsSkeleton } from './PricePoints'
export type { PricePointsProps, VolatilityLevel } from './PricePoints'

// ThreeMonthSnapshot component
export { ThreeMonthSnapshot, ThreeMonthSnapshotSkeleton } from './ThreeMonthSnapshot'
export type { ThreeMonthSnapshotProps } from './ThreeMonthSnapshot'

// TreatmentPricingTable component
export { TreatmentPricingTable, TreatmentPricingTableSkeleton } from './TreatmentPricingTable'
export type { TreatmentPricingTableProps, TreatmentRow } from './TreatmentPricingTable'

// ListingsTable component
export { ListingsTable, ListingsTableSkeleton, PAGE_SIZE_OPTIONS } from './ListingsTable'
export type {
  ListingsTableProps,
  PaginationState,
  SortState,
  SortKey,
  PageSizeOption
} from './ListingsTable'

// SimilarCards carousel component
export { SimilarCards, SimilarCardsSkeleton } from './SimilarCards'
export type { SimilarCardsProps, SimilarCard } from './SimilarCards'

// StickyPriceHeader component (mobile)
export { StickyPriceHeader, StickyPriceHeaderWithScroll, useScrollPast } from './StickyPriceHeader'
export type { StickyPriceHeaderProps } from './StickyPriceHeader'

// CardDetailHeader component (top navigation)
export { CardDetailHeader } from './CardDetailHeader'
export type { CardDetailHeaderProps } from './CardDetailHeader'
