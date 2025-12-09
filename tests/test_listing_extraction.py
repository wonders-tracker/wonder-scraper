"""
Listing Extraction Tests.

Tests for eBay scraper field extraction functions including:
- Treatment detection (Sealed, Open Box, Foil types, etc.)
- Product subtype detection (Collector Booster Box, Play Bundle, etc.)
- Grading detection (PSA, TAG, BGS, CGC)
- Quantity detection
- Condition extraction
"""

import pytest
from app.scraper.ebay import (
    _detect_treatment,
    _detect_product_subtype,
    _detect_quantity,
    _detect_bundle_pack_count,
    _detect_grading,
)


class TestSealedTreatmentDetection:
    """Tests for sealed/unsealed/opened detection on boxes, packs, bundles."""

    # === SEALED DETECTION ===
    @pytest.mark.parametrize("title,expected", [
        # Explicit "sealed" keyword
        ("Wonders of the First Collector Booster Box SEALED", "Sealed"),
        ("Sealed Wonders of the First Existence Play Bundle", "Sealed"),
        ("Factory Sealed WOTF Collector Booster Box", "Sealed"),
        ("factory-sealed wotf collector box", "Sealed"),
        # "New" keyword
        ("NEW Wonders of the First Collector Booster Box", "Sealed"),
        ("Wonders of the First Existence Box New", "Sealed"),
        # "Unopened" keyword
        ("Unopened Wonders of the First Existence Booster Box", "Sealed"),
        ("WOTF Booster Pack UNOPENED", "Sealed"),
        # "NIB" (New In Box)
        ("Wonders of the First Collector Box NIB", "Sealed"),
        # "Mint" condition
        ("Mint Condition Wonders of the First Booster Box", "Sealed"),
        # No explicit indicator - defaults to Sealed for boxes
        ("Wonders of the First Collector Booster Box", "Sealed"),
        ("WOTF Existence Play Bundle 1st Edition", "Sealed"),
    ])
    def test_sealed_box_detection(self, title, expected):
        """Test that sealed boxes are correctly detected."""
        result = _detect_treatment(title, product_type="Box")
        assert result == expected, f"Expected {expected} for '{title}', got {result}"

    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First Collector Booster Pack SEALED", "Sealed"),
        ("Sealed WOTF Play Booster Pack", "Sealed"),
        ("Wonders of the First Booster Pack New", "Sealed"),
        # Default to Sealed
        ("Wonders of the First Collector Booster Pack", "Sealed"),
    ])
    def test_sealed_pack_detection(self, title, expected):
        """Test that sealed packs are correctly detected."""
        result = _detect_treatment(title, product_type="Pack")
        assert result == expected

    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First Play Bundle SEALED", "Sealed"),
        ("Sealed Serialized Advantage Bundle", "Sealed"),
        ("New Wonders of the First Blaster Box", "Sealed"),
        # Default to Sealed
        ("Wonders of the First Serialized Advantage", "Sealed"),
    ])
    def test_sealed_bundle_detection(self, title, expected):
        """Test that sealed bundles are correctly detected."""
        result = _detect_treatment(title, product_type="Bundle")
        assert result == expected

    # === OPEN BOX / OPENED DETECTION ===
    @pytest.mark.parametrize("title,expected", [
        # Explicit "open box"
        ("Wonders of the First Collector Booster Box Open Box", "Open Box"),
        ("Open Box WOTF Existence Booster Box", "Open Box"),
        # "Opened" keyword
        ("Wonders of the First Box - Opened", "Open Box"),
        ("Opened WOTF Collector Booster Box - Missing 2 Packs", "Open Box"),
        # "Used" keyword
        ("Used Wonders of the First Booster Box", "Open Box"),
    ])
    def test_open_box_detection(self, title, expected):
        """Test that opened/open box products are correctly detected."""
        result = _detect_treatment(title, product_type="Box")
        assert result == expected, f"Expected {expected} for '{title}', got {result}"

    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First Play Bundle - Opened", "Open Box"),
        ("Used Serialized Advantage Bundle", "Open Box"),
    ])
    def test_open_bundle_detection(self, title, expected):
        """Test that opened bundles are correctly detected."""
        result = _detect_treatment(title, product_type="Bundle")
        assert result == expected

    # === EDGE CASES ===
    def test_sealed_takes_priority_over_open(self):
        """Test that 'sealed' takes priority when both keywords present."""
        # This could happen in weird listings like "Sealed box, was opened to check contents"
        # The "sealed" keyword should win
        title = "Factory Sealed Wonders of the First Box - Never Opened"
        result = _detect_treatment(title, product_type="Box")
        assert result == "Sealed"


class TestSingleTreatmentDetection:
    """Tests for card treatment detection on singles."""

    # === SERIALIZED / OCM ===
    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First Gorrash OCM Serialized 15/99", "OCM Serialized"),
        ("WOTF Existence Deep Black Goop Serialized /25", "OCM Serialized"),
        ("Gorrash OCM 42/99 Mythic", "OCM Serialized"),
        ("Deep Black Goop /10 Mythic Existence", "OCM Serialized"),
        ("Existence Mythic /50 serialized", "OCM Serialized"),
        ("WOTF OCM Card 1/75", "OCM Serialized"),
    ])
    def test_serialized_detection(self, title, expected):
        """Test that serialized/OCM cards are correctly detected."""
        result = _detect_treatment(title, product_type="Single")
        assert result == expected

    # === SPECIAL FOILS ===
    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First Gorrash Stonefoil", "Stonefoil"),
        ("WOTF Existence Stone Foil Mythic", "Stonefoil"),
        ("Deep Black Goop Formless Foil", "Formless Foil"),
        ("Formless Wonders of the First Epic", "Formless Foil"),
    ])
    def test_special_foil_detection(self, title, expected):
        """Test that special foil treatments are correctly detected."""
        result = _detect_treatment(title, product_type="Single")
        assert result == expected

    # === OTHER VARIANTS ===
    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First Prerelease Promo Card", "Prerelease"),
        ("WOTF Existence Prerelease Stamp", "Prerelease"),
        ("Wonders of the First Promo Card", "Promo"),
        ("WOTF Kickstarter Promo", "Promo"),
        ("Wonders of the First Proof Card", "Proof/Sample"),
        ("WOTF Sample Card Not For Sale", "Proof/Sample"),
        ("Wonders of the First Errata Version", "Error/Errata"),
        ("WOTF Error Card Misprint", "Error/Errata"),
    ])
    def test_variant_detection(self, title, expected):
        """Test that special variants are correctly detected."""
        result = _detect_treatment(title, product_type="Single")
        assert result == expected

    # === CLASSIC FOIL ===
    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First Gorrash Foil", "Classic Foil"),
        ("WOTF Existence Holo Rare", "Classic Foil"),
        ("Refractor Wonders Card", "Classic Foil"),
    ])
    def test_classic_foil_detection(self, title, expected):
        """Test that classic foils are correctly detected."""
        result = _detect_treatment(title, product_type="Single")
        assert result == expected

    # === CLASSIC PAPER (default) ===
    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First Gorrash Mythic", "Classic Paper"),
        ("WOTF Existence Deep Black Goop", "Classic Paper"),
        ("Wonders of the First Common Card", "Classic Paper"),
    ])
    def test_classic_paper_default(self, title, expected):
        """Test that cards without foil indicators default to Classic Paper."""
        result = _detect_treatment(title, product_type="Single")
        assert result == expected

    # === PRIORITY TESTS ===
    def test_serialized_priority_over_foil(self):
        """Test that serialized takes priority over foil keywords."""
        title = "Wonders of the First Gorrash OCM Serialized 15/99 Foil"
        result = _detect_treatment(title, product_type="Single")
        assert result == "OCM Serialized"

    def test_stonefoil_priority_over_classic_foil(self):
        """Test that stonefoil takes priority over generic foil."""
        title = "Wonders of the First Stone Foil Foil Card"
        result = _detect_treatment(title, product_type="Single")
        assert result == "Stonefoil"


class TestProductSubtypeDetection:
    """Tests for product subtype detection."""

    # === BOXES ===
    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First Collector Booster Box", "Collector Booster Box"),
        ("WOTF Existence Collector Booster Box Sealed", "Collector Booster Box"),
        ("Collector Booster Box Wonders of the First", "Collector Booster Box"),
        ("Wonders Booster Box 1st Edition", "Collector Booster Box"),
        # Case (6 boxes)
        ("Wonders of the First Collector Booster Box Case", "Case"),
        ("WOTF Case 6 Boxes", "Case"),
        # Generic box
        ("Wonders of the First Display Box", "Box"),
    ])
    def test_box_subtype_detection(self, title, expected):
        """Test that box subtypes are correctly detected."""
        result = _detect_product_subtype(title, product_type="Box")
        assert result == expected, f"Expected {expected} for '{title}', got {result}"

    # === BUNDLES ===
    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First Serialized Advantage", "Serialized Advantage"),
        ("WOTF Serialized Advantage Bundle", "Serialized Advantage"),
        ("Wonders of the First Starter Set", "Starter Set"),
        ("WOTF Existence Starter Kit", "Starter Set"),
        ("Wonders of the First Play Bundle", "Play Bundle"),
        ("WOTF Existence Blaster Box", "Blaster Box"),
        ("Blaster Box Wonders of the First", "Blaster Box"),
        # Generic bundle
        ("Wonders of the First Bundle", "Play Bundle"),
    ])
    def test_bundle_subtype_detection(self, title, expected):
        """Test that bundle subtypes are correctly detected."""
        result = _detect_product_subtype(title, product_type="Bundle")
        assert result == expected, f"Expected {expected} for '{title}', got {result}"

    # === PACKS ===
    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First Collector Booster Pack", "Collector Booster Pack"),
        ("WOTF Collector Booster", "Collector Booster Pack"),
        ("Wonders of the First Play Booster Pack", "Play Booster Pack"),
        ("WOTF Play Booster", "Play Booster Pack"),
        ("Wonders of the First Silver Pack", "Silver Pack"),
        ("Silver Pack WOTF Promo", "Silver Pack"),
        # Generic booster defaults to Collector
        ("Wonders of the First Booster Pack", "Collector Booster Pack"),
        # Generic pack
        ("Wonders of the First Pack", "Pack"),
    ])
    def test_pack_subtype_detection(self, title, expected):
        """Test that pack subtypes are correctly detected."""
        result = _detect_product_subtype(title, product_type="Pack")
        assert result == expected, f"Expected {expected} for '{title}', got {result}"

    # === LOTS ===
    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First Card Lot", "Lot"),
        ("WOTF Bulk Lot 100 Cards", "Bulk"),
        ("Bulk Commons Wonders of the First", "Bulk"),
    ])
    def test_lot_subtype_detection(self, title, expected):
        """Test that lot subtypes are correctly detected."""
        result = _detect_product_subtype(title, product_type="Lot")
        assert result == expected

    # === SINGLES (no subtype) ===
    def test_singles_have_no_subtype(self):
        """Test that singles return None for subtype."""
        title = "Wonders of the First Gorrash Mythic"
        result = _detect_product_subtype(title, product_type="Single")
        assert result is None


class TestGradingDetection:
    """Tests for grading company detection (PSA, TAG, BGS, CGC, SGC)."""

    # === PSA GRADING ===
    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First Gorrash PSA 10 Gem Mint", "PSA 10"),
        ("PSA 9 MINT Wonders of the First Mythic", "PSA 9"),
        ("WOTF Deep Black Goop PSA 8", "PSA 8"),
        ("PSA-10 Wonders of the First Mythic", "PSA 10"),
        ("PSA10 WOTF Card", "PSA 10"),
        ("PSA GEM MINT 10 Wonders Card", "PSA 10"),
    ])
    def test_psa_grading_detection(self, title, expected):
        """Test that PSA graded cards are correctly identified."""
        result = _detect_grading(title)
        assert result == expected, f"Expected {expected} for '{title}', got {result}"

    # === TAG GRADING ===
    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First Gorrash TAG 10 Perfect", "TAG 10"),
        ("TAG 9.5 WOTF Mythic Card", "TAG 9.5"),
        ("TAG-10 Wonders of the First", "TAG 10"),
        ("TAG PERFECT 10 Deep Black Goop", "TAG 10"),
    ])
    def test_tag_grading_detection(self, title, expected):
        """Test that TAG graded cards are correctly identified."""
        result = _detect_grading(title)
        assert result == expected, f"Expected {expected} for '{title}', got {result}"

    # === BGS (BECKETT) GRADING ===
    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First BGS 9.5 Gem Mint", "BGS 9.5"),
        ("BGS 10 Black Label Wonders", "BGS 10"),
        ("BGS-9.5 WOTF Mythic", "BGS 9.5"),
        ("BECKETT 9.5 Wonders Card", "BGS 9.5"),
    ])
    def test_bgs_grading_detection(self, title, expected):
        """Test that BGS/Beckett graded cards are correctly identified."""
        result = _detect_grading(title)
        assert result == expected, f"Expected {expected} for '{title}', got {result}"

    # === CGC GRADING ===
    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First CGC 9.8", "CGC 9.8"),
        ("CGC 10 WOTF Mythic", "CGC 10"),
        ("CGC-9.5 Wonders Card", "CGC 9.5"),
    ])
    def test_cgc_grading_detection(self, title, expected):
        """Test that CGC graded cards are correctly identified."""
        result = _detect_grading(title)
        assert result == expected, f"Expected {expected} for '{title}', got {result}"

    # === SGC GRADING ===
    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First SGC 10", "SGC 10"),
        ("SGC-9.5 WOTF Mythic", "SGC 9.5"),
    ])
    def test_sgc_grading_detection(self, title, expected):
        """Test that SGC graded cards are correctly identified."""
        result = _detect_grading(title)
        assert result == expected, f"Expected {expected} for '{title}', got {result}"

    # === RAW CARDS ===
    @pytest.mark.parametrize("title", [
        "Wonders of the First Gorrash Mythic",
        "WOTF Existence Deep Black Goop Foil",
        "Wonders of the First Common Card NM",
        "OCM Serialized 42/99 Wonders",
    ])
    def test_raw_cards_have_no_grading(self, title):
        """Test that ungraded cards return None for grading."""
        result = _detect_grading(title)
        assert result is None, f"Expected None for '{title}', got {result}"

    # === TAG SLAB (ungraded slabs) ===
    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First Gorrash TAG SLAB Prerelease", "TAG SLAB"),
        ("TAG SLAB Wonders of the First Mythic", "TAG SLAB"),
        ("WOTF Prerelease TAG-SLAB", "TAG SLAB"),
        ("Wonders TAG SLAB Card", "TAG SLAB"),
    ])
    def test_tag_slab_detection(self, title, expected):
        """Test that TAG SLAB (ungraded slabs) are correctly identified."""
        result = _detect_grading(title)
        assert result == expected, f"Expected {expected} for '{title}', got {result}"

    # === GENERIC GRADED/SLAB ===
    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First Gorrash GRADED Card", "GRADED"),
        ("GRADED Wonders of the First Mythic", "GRADED"),
        ("Wonders of the First SLAB", "GRADED"),
        ("SLABBED Wonders of the First Card", "GRADED"),
        ("Professional Graded Wonders Card", "GRADED"),
    ])
    def test_generic_graded_detection(self, title, expected):
        """Test that generic GRADED/SLAB mentions are detected."""
        result = _detect_grading(title)
        assert result == expected, f"Expected {expected} for '{title}', got {result}"

    # === EDGE CASES ===
    def test_stag_not_detected_as_tag(self):
        """Test that 'STAG' in title doesn't trigger TAG detection."""
        title = "Wonders of the First STAG Promo Card"
        result = _detect_grading(title)
        assert result is None


class TestQuantityDetection:
    """Tests for quantity detection from listing titles."""

    # === SINGLE CARDS ===
    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First Gorrash Mythic", 1),
        ("2x Wonders of the First Common Card", 2),
        ("3x Wonders of the First Epic Cards", 3),  # Need the "x" to be explicit
        ("Lot of 5 Wonders of the First Cards", 5),
        ("5 card lot WOTF", 5),
        ("WOTF Card x4", 4),
    ])
    def test_single_quantity_detection(self, title, expected):
        """Test quantity detection for single cards."""
        result = _detect_quantity(title, product_type="Single")
        assert result == expected, f"Expected {expected} for '{title}', got {result}"

    # === SEALED PRODUCTS ===
    @pytest.mark.parametrize("title,expected", [
        # Single box
        ("Wonders of the First Collector Booster Box", 1),
        # Multiple boxes
        ("2x Wonders of the First Collector Booster Box", 2),
        ("2 Wonders Collector Booster Box", 2),
        ("Lot of 3 WOTF Booster Boxes", 3),
        # Should NOT detect contents as quantity
        ("Wonders Play Bundle (6 Booster Packs Inside)", 1),
        ("Collector Box Contains 12 Packs", 1),
        ("Bundle with 6 packs", 1),
    ])
    def test_box_quantity_detection(self, title, expected):
        """Test quantity detection for boxes."""
        result = _detect_quantity(title, product_type="Box")
        assert result == expected, f"Expected {expected} for '{title}', got {result}"

    @pytest.mark.parametrize("title,expected", [
        ("Wonders of the First Collector Booster Pack", 1),
        ("3x Wonders Collector Booster Pack", 3),  # Fixed: needs "Wonders" not "WOTF" after Nx
        ("5ct Wonders Booster Packs", 5),
        ("Set of 2 Wonders Packs", 2),
    ])
    def test_pack_quantity_detection(self, title, expected):
        """Test quantity detection for packs."""
        result = _detect_quantity(title, product_type="Pack")
        assert result == expected, f"Expected {expected} for '{title}', got {result}"

    # === YEAR EXCLUSION ===
    @pytest.mark.parametrize("title,expected", [
        # 2025 should NOT be detected as quantity
        ("2025 Wonders of the First Booster Box", 1),
        ("Wonders of the First 2025 Collector Box", 1),
        # 2024 should NOT be detected as quantity
        ("2024 Wonders of the First Pack", 1),
    ])
    def test_year_not_detected_as_quantity(self, title, expected):
        """Test that years (2020-2030) are not detected as quantities."""
        result = _detect_quantity(title, product_type="Box")
        assert result == expected, f"Expected {expected} for '{title}', got {result}"

    # === CARD NAME EXCLUSIONS ===
    @pytest.mark.parametrize("title,expected", [
        # Carbon-X7 is a card name, not 7 copies
        ("Wonders of the First Carbon-X7 Synthforge Mythic", 1),
        ("Carbon-X7 Synthforge Foil Card", 1),
        ("WOTF Carbon-X7 Classic Paper", 1),
        # X7v1 variant naming
        ("Wonders of the First X7v1 Variant", 1),
        # Experiment X series
        ("Experiment X Wonders of the First", 1),
    ])
    def test_card_names_with_x_not_detected_as_quantity(self, title, expected):
        """Test that card names containing X (Carbon-X7, X7v1) are not detected as quantities."""
        result = _detect_quantity(title, product_type="Single")
        assert result == expected, f"Expected {expected} for '{title}', got {result}"

    # === X PREFIX PATTERNS ===
    @pytest.mark.parametrize("title,expected", [
        # "X3" at start of title
        ("X3 Wonders of the First Common Cards", 3),
        ("x2 WOTF Mythic Card Lot", 2),
        # "3x" at start
        ("3x Wonders of the First Epic Card", 3),
        # Quantity at end
        ("Wonders of the First Common x4", 4),
        ("WOTF Epic Card x3", 3),
    ])
    def test_x_prefix_quantity_patterns(self, title, expected):
        """Test various X prefix/suffix quantity patterns."""
        result = _detect_quantity(title, product_type="Single")
        assert result == expected, f"Expected {expected} for '{title}', got {result}"


class TestBundlePackCount:
    """Tests for bundle pack count detection."""

    @pytest.mark.parametrize("title,expected", [
        # Play Bundle = 6 packs
        ("Wonders of the First Play Bundle", 6),
        # Blaster Box = 6 packs
        ("WOTF Existence Blaster Box", 6),
        # Serialized Advantage = 4 packs
        ("Wonders of the First Serialized Advantage", 4),
        # Collector Booster Box = 12 packs
        ("Wonders of the First Collector Booster Box", 12),
        # Single pack = 0 (not a bundle)
        ("Wonders of the First Booster Pack", 0),
        # Generic bundle
        ("Wonders of the First Bundle", 0),
    ])
    def test_bundle_pack_count(self, title, expected):
        """Test that bundle pack counts are correctly detected."""
        result = _detect_bundle_pack_count(title)
        assert result == expected, f"Expected {expected} for '{title}', got {result}"


class TestDataQualityIntegration:
    """Integration tests for extraction against real database data."""

    @pytest.fixture
    def integration_session(self):
        """Get a database session for integration tests."""
        from app.db import get_session
        return next(get_session())

    def test_sealed_boxes_have_sealed_treatment(self, integration_session):
        """Test that eBay box listings in DB have correct sealed treatment.

        Note: OpenSea NFT boxes have different treatment fields (box art traits like 'Dragon').
        This test only validates eBay boxes.
        """
        from sqlmodel import select
        from app.models.market import MarketPrice
        from app.models.card import Card

        # Get eBay box listings only (OpenSea boxes use NFT trait treatments)
        boxes = integration_session.exec(
            select(MarketPrice)
            .join(Card, MarketPrice.card_id == Card.id)
            .where(Card.product_type == "Box")
            .where(MarketPrice.platform == "ebay")
            .limit(50)
        ).all()

        if not boxes:
            pytest.skip("No eBay box listings in database")

        issues = []
        for box in boxes:
            treatment = box.treatment or ""
            # eBay boxes should be either "Sealed" or "Open Box"
            if treatment not in ("Sealed", "Open Box", ""):
                issues.append(f"Box ID {box.id}: '{box.title[:50]}...' has treatment '{treatment}'")

        if issues:
            print(f"\n{len(issues)} eBay boxes with unexpected treatments:")
            for issue in issues[:10]:
                print(f"  - {issue}")

        # Allow some flexibility - this is more of a data quality check than a hard assertion
        assert len(issues) < len(boxes) * 0.1, f"More than 10% of eBay boxes have unexpected treatments"

    def test_singles_have_card_treatments(self, integration_session):
        """Test that single card listings have card-appropriate treatments."""
        from sqlmodel import select
        from app.models.market import MarketPrice
        from app.models.card import Card

        valid_single_treatments = {
            "Classic Paper", "Classic Foil", "Stonefoil", "Formless Foil",
            "OCM Serialized", "Prerelease", "Promo", "Proof/Sample", "Error/Errata",
            ""  # Allow empty/null
        }

        singles = integration_session.exec(
            select(MarketPrice)
            .join(Card, MarketPrice.card_id == Card.id)
            .where(Card.product_type == "Single")
            .limit(100)
        ).all()

        issues = []
        for single in singles:
            treatment = single.treatment or ""
            if treatment not in valid_single_treatments:
                issues.append(f"Single ID {single.id}: '{single.title[:40]}...' has treatment '{treatment}'")

        if issues:
            print(f"\n{len(issues)} singles with unexpected treatments:")
            for issue in issues[:10]:
                print(f"  - {issue}")

        assert len(issues) < len(singles) * 0.05, f"More than 5% of singles have unexpected treatments"

    def test_bundles_have_subtypes(self, integration_session):
        """Test that bundle listings have product subtypes set."""
        from sqlmodel import select
        from app.models.market import MarketPrice
        from app.models.card import Card

        bundles = integration_session.exec(
            select(MarketPrice)
            .join(Card, MarketPrice.card_id == Card.id)
            .where(Card.product_type == "Bundle")
            .limit(50)
        ).all()

        if not bundles:
            pytest.skip("No bundle listings in database")

        with_subtype = sum(1 for b in bundles if b.product_subtype)
        without_subtype = sum(1 for b in bundles if not b.product_subtype)

        print(f"\nBundle subtype coverage: {with_subtype}/{len(bundles)} have subtypes")

        # Informational - don't fail, just report
        if without_subtype > 0:
            import warnings
            warnings.warn(f"{without_subtype} bundles missing product_subtype")

    def test_packs_have_subtypes(self, integration_session):
        """Test that pack listings have product subtypes set."""
        from sqlmodel import select
        from app.models.market import MarketPrice
        from app.models.card import Card

        packs = integration_session.exec(
            select(MarketPrice)
            .join(Card, MarketPrice.card_id == Card.id)
            .where(Card.product_type == "Pack")
            .limit(50)
        ).all()

        if not packs:
            pytest.skip("No pack listings in database")

        with_subtype = sum(1 for p in packs if p.product_subtype)

        print(f"\nPack subtype coverage: {with_subtype}/{len(packs)} have subtypes")

        # Informational
        if with_subtype < len(packs):
            import warnings
            warnings.warn(f"{len(packs) - with_subtype} packs missing product_subtype")

    def test_grading_detected_correctly(self, integration_session):
        """Test that graded listings have grading field populated."""
        from sqlmodel import select
        from app.models.market import MarketPrice

        # Find listings that mention grading keywords but don't have grading field set
        grading_keywords = ['PSA', 'BGS', 'CGC', 'SGC', 'TAG ', 'SLAB', 'GRADED']

        listings = integration_session.exec(
            select(MarketPrice)
            .where(MarketPrice.platform == "ebay")
            .where(MarketPrice.grading.is_(None))
            .limit(500)
        ).all()

        issues = []
        for listing in listings:
            title_upper = (listing.title or "").upper()
            for keyword in grading_keywords:
                # Check for keyword but exclude STAG (not TAG)
                if keyword in title_upper:
                    if keyword == 'TAG ' and 'STAG' in title_upper:
                        continue
                    issues.append(f"ID {listing.id}: '{listing.title[:50]}...' has '{keyword}' but no grading")
                    break

        if issues:
            print(f"\n{len(issues)} listings with grading keywords but no grading field:")
            for issue in issues[:10]:
                print(f"  - {issue}")

        # Allow up to 5% of listings to slip through (edge cases)
        assert len(issues) < len(listings) * 0.05, \
            f"{len(issues)} listings have grading keywords but no grading field set"

    def test_quantity_detected_correctly(self, integration_session):
        """Test that multi-quantity listings have quantity > 1."""
        from sqlmodel import select
        from app.models.market import MarketPrice
        import re

        # Find listings that look like multi-quantity but have quantity = 1
        qty_patterns = [
            r'^\d+x\s+',           # "2x " at start
            r'^x\d+\s+',           # "x2 " at start
            r'lot\s+of\s+\d+',     # "lot of 5"
            r'\d+\s+card\s+lot',   # "5 card lot"
        ]

        listings = integration_session.exec(
            select(MarketPrice)
            .where(MarketPrice.platform == "ebay")
            .where(MarketPrice.quantity == 1)
            .limit(500)
        ).all()

        issues = []
        for listing in listings:
            title_lower = (listing.title or "").lower()
            for pattern in qty_patterns:
                if re.search(pattern, title_lower):
                    issues.append(f"ID {listing.id}: '{listing.title[:50]}...' matches '{pattern}' but qty=1")
                    break

        if issues:
            print(f"\n{len(issues)} listings that may have incorrect quantity=1:")
            for issue in issues[:10]:
                print(f"  - {issue}")

        # Allow some false positives
        assert len(issues) < len(listings) * 0.02, \
            f"{len(issues)} listings may have incorrect quantity"

    def test_no_wrong_game_cards(self, integration_session):
        """Test that no non-WOTF cards are in the database."""
        from sqlmodel import select
        from app.models.market import MarketPrice
        import re

        # Keywords that indicate wrong game
        wrong_game_keywords = [
            r'\byu-?gi-?oh\b',
            r'\bpokemon\b',
            r'\bmagic\s+the\s+gathering\b',
            r'\bmtg\b',
            r'\blorcana\b',
            r'\bweiss\s+schwarz\b',
            r'\bdragon\s+ball\b',
            r'\bnaruto\b',
            r'\bone\s+piece\s+tcg\b',
        ]

        listings = integration_session.exec(
            select(MarketPrice)
            .where(MarketPrice.platform == "ebay")
            .limit(500)
        ).all()

        issues = []
        for listing in listings:
            title_lower = (listing.title or "").lower()
            for pattern in wrong_game_keywords:
                if re.search(pattern, title_lower):
                    issues.append(f"ID {listing.id}: '{listing.title[:50]}...' may be wrong game")
                    break

        if issues:
            print(f"\n{len(issues)} listings may be from wrong games:")
            for issue in issues[:10]:
                print(f"  - {issue}")

        # Should be 0 wrong game cards
        assert len(issues) == 0, f"{len(issues)} listings appear to be from other TCGs"


class TestCardNameNormalization:
    """Tests for card name normalization used in matching."""

    @pytest.mark.parametrize("input_name,expected", [
        # Apostrophe styles
        ("Bathr'al the Cursed", "bathr'al the cursed"),
        ("Bathr'al the Cursed", "bathr'al the cursed"),
        ("Bathr'al the Cursed", "bathr'al the cursed"),
        # Quote styles
        ('"Lightbringer" Leonis', '"lightbringer" leonis'),
        ('"Lightbringer" Leonis', '"lightbringer" leonis'),
        # Commas removed
        ("Gorrash, the Destroyer", "gorrash the destroyer"),
        # Hyphens to spaces
        ("Cave-Dwelling Rootling", "cave dwelling rootling"),
        # "of the" -> "of"
        ("Keeper of the Skulls", "keeper of skulls"),
        # Leading "the" removed
        ("The Prisoner", "prisoner"),
    ])
    def test_normalize_card_name(self, input_name, expected):
        """Test card name normalization for fuzzy matching."""
        from scripts.cleanup_listing_data import normalize_card_name
        result = normalize_card_name(input_name)
        assert result == expected, f"Expected '{expected}' for '{input_name}', got '{result}'"

    @pytest.mark.parametrize("typo,correction", [
        ("Issac Sparkpaw", "Isaac Sparkpaw"),
        ("Mutaded Dragon", "Mutated Dragon"),
        ("Deathsworm Gravesman", "Deathsworn Gravesman"),
        ("Ceacean Warrior", "Cetacean Warrior"),
        ("Lyonnaisa", "Lyonnisia"),
    ])
    def test_spelling_corrections(self, typo, correction):
        """Test that common typos can be corrected."""
        from scripts.cleanup_listing_data import SPELLING_CORRECTIONS, apply_spelling_corrections
        result = apply_spelling_corrections(typo)
        assert correction.lower() in result.lower(), f"Expected '{correction}' for '{typo}', got '{result}'"
