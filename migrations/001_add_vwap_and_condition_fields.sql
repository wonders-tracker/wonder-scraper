-- Migration: Add VWAP support and box/pack condition tracking
-- Date: 2025-11-23
-- Description:
--   1. Add quantity field to marketprice for true VWAP calculations
--   2. Add condition field to card for sealed/unsealed boxes and packs
--   3. Add performance indexes for common queries

-- ============================================================================
-- Add new columns
-- ============================================================================

-- Add quantity to marketprice (defaults to 1 for existing records)
ALTER TABLE marketprice
ADD COLUMN IF NOT EXISTS quantity INTEGER NOT NULL DEFAULT 1;

-- Add condition to card (null for singles, 'Sealed'/'Unsealed' for boxes/packs)
ALTER TABLE card
ADD COLUMN IF NOT EXISTS condition VARCHAR(20);

-- ============================================================================
-- Add performance indexes
-- ============================================================================

-- Index for VWAP calculations (card_id + listing_type + sold_date + quantity)
CREATE INDEX IF NOT EXISTS idx_marketprice_vwap
ON marketprice(card_id, listing_type, sold_date DESC)
WHERE listing_type = 'sold' AND price > 0 AND quantity > 0;

-- Index for card condition filtering
CREATE INDEX IF NOT EXISTS idx_card_condition
ON card(product_type, condition)
WHERE condition IS NOT NULL;

-- Composite index for card market queries
CREATE INDEX IF NOT EXISTS idx_card_product_set
ON card(product_type, set_name, created_at DESC);

-- Index for time-based price queries
CREATE INDEX IF NOT EXISTS idx_marketprice_time
ON marketprice(sold_date DESC, listing_type, price)
WHERE listing_type = 'sold' AND price > 0;

-- ============================================================================
-- Data quality: Set default quantity for historical records
-- ============================================================================

-- Update existing records to have quantity = 1 if they don't already
UPDATE marketprice
SET quantity = 1
WHERE quantity IS NULL OR quantity = 0;

-- ============================================================================
-- Comments for documentation
-- ============================================================================

COMMENT ON COLUMN marketprice.quantity IS 'Number of items sold/listed (for VWAP calculation: SUM(price*quantity)/SUM(quantity))';
COMMENT ON COLUMN card.condition IS 'Condition for boxes/packs: Sealed, Unsealed. NULL for singles.';
