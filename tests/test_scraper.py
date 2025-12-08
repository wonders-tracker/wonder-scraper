"""
Tests for eBay scraper functionality.

Tests cover:
- Title validation and match filtering (_is_valid_match)
- Treatment extraction (_detect_treatment)
- Quantity detection (_detect_quantity)
- Non-WOTF card filtering (Yu-Gi-Oh, Pokemon, DBZ, etc.)
- Bundle/pack detection
"""

import pytest
from app.scraper.ebay import (
    _is_valid_match,
    _detect_treatment,
    _detect_quantity,
    _detect_bundle_pack_count,
    _detect_product_subtype,
)


class TestIsValidMatch:
    """Tests for the _is_valid_match function."""

    # =========================================================================
    # WOTF Card Matching - Should PASS
    # =========================================================================

    def test_exact_card_name_match(self):
        """Exact card name should match."""
        assert _is_valid_match(
            "Wonders of the First Progo Classic Paper",
            "Progo"
        ) is True

    def test_card_with_treatment(self):
        """Card name with treatment should match."""
        assert _is_valid_match(
            "WOTF Existence Zeltona Formless Foil",
            "Zeltona"
        ) is True

    def test_card_with_set_name(self):
        """Card with set name should match."""
        assert _is_valid_match(
            "Wonders of the First Existence Deep Black Goop Stonefoil",
            "Deep Black Goop"
        ) is True

    def test_sealed_product_match(self):
        """Sealed product should match with lenient rules."""
        assert _is_valid_match(
            "Wonders of the First Existence Collector Booster Box Sealed",
            "Collector Booster Box"
        ) is True

    def test_play_bundle_match(self):
        """Play Bundle should match."""
        assert _is_valid_match(
            "Wonders of the First Existence Play Bundle Blaster Box",
            "Play Bundle"
        ) is True

    def test_psa_graded_wotf_card(self):
        """PSA graded WOTF cards should still match."""
        assert _is_valid_match(
            "2024 Wonders of the First Existence Progo Formless Foil PSA 10",
            "Progo"
        ) is True

    def test_card_number_format(self):
        """Card with number format should match."""
        assert _is_valid_match(
            "Wonders of the First Zeltona 123/401 Classic Foil",
            "Zeltona"
        ) is True

    # =========================================================================
    # Non-WOTF Card Filtering - Should FAIL
    # =========================================================================

    class TestYuGiOhFiltering:
        """Tests for Yu-Gi-Oh card filtering."""

        def test_rejects_yugioh_mp22_code(self):
            """Should reject Yu-Gi-Oh MP22-EN card codes."""
            assert _is_valid_match(
                "Ruddy Rose Dragon MP22-EN077 2022 Tin of the Pharaoh's Gods 1st Edition",
                "Dragon's Gold"
            ) is False

        def test_rejects_yugioh_mged_code(self):
            """Should reject Yu-Gi-Oh MGED-EN card codes."""
            assert _is_valid_match(
                "Trishula Dragon of the Ice Barrier MGED-EN027 Gold Rare",
                "Dragon's Gold"
            ) is False

        def test_rejects_tin_of_pharaoh(self):
            """Should reject Tin of the Pharaoh's Gods."""
            assert _is_valid_match(
                "Albion the Branded Dragon 2022 Tin of the Pharaoh's Gods",
                "Dragon's Gold"
            ) is False

        def test_rejects_konami(self):
            """Should reject Konami products."""
            assert _is_valid_match(
                "Red-Eyes Black Dragon Konami 1st Edition",
                "Dragon's Gold"
            ) is False

        def test_rejects_yugioh_explicit(self):
            """Should reject explicit Yu-Gi-Oh mentions."""
            assert _is_valid_match(
                "Yu-Gi-Oh! Blue-Eyes White Dragon",
                "Dragon's Gold"
            ) is False

        def test_rejects_ice_barrier(self):
            """Should reject Ice Barrier archetype."""
            assert _is_valid_match(
                "Trishula Dragon of the Ice Barrier Secret Rare",
                "Dragon's Gold"
            ) is False

    class TestDragonBallZFiltering:
        """Tests for Dragon Ball Z card filtering."""

        def test_rejects_dragonball(self):
            """Should reject Dragon Ball Z cards."""
            assert _is_valid_match(
                "Dragonball Z CCG The Awakening Android 20 WA-066",
                "The Awakening"
            ) is False

        def test_rejects_dbz_characters(self):
            """Should reject DBZ character names."""
            assert _is_valid_match(
                "Dragon Ball Z Hercule 1st Edition Gold",
                "The Awakening"
            ) is False

        def test_rejects_dbz_card_codes(self):
            """Should reject DBZ card codes like WA-066."""
            assert _is_valid_match(
                "The Awakening WA-079 Holo 1st Ed",
                "The Awakening"
            ) is False

        def test_rejects_goku(self):
            """Should reject Goku cards."""
            assert _is_valid_match(
                "Goku Level 5 The Awakening Gold Stamp",
                "The Awakening"
            ) is False

    class TestPokemonFiltering:
        """Tests for Pokemon card filtering."""

        def test_rejects_pokemon_explicit(self):
            """Should reject explicit Pokemon mentions."""
            assert _is_valid_match(
                "Pokemon Scarlet Violet Charizard ex",
                "Charizard"
            ) is False

        def test_rejects_pokemon_characters(self):
            """Should reject Pokemon character names."""
            assert _is_valid_match(
                "Pikachu VMAX Rainbow Rare Evolving Skies",
                "Pikachu"
            ) is False

        def test_rejects_pokemon_sets(self):
            """Should reject Pokemon set names."""
            assert _is_valid_match(
                "Evolving Skies Booster Box Sealed",
                "Booster Box"
            ) is False

        def test_rejects_scarlet_violet(self):
            """Should reject Scarlet Violet set."""
            assert _is_valid_match(
                "Scarlet Violet 151 Booster Pack",
                "Booster Pack"
            ) is False

    class TestOnePieceFiltering:
        """Tests for One Piece TCG filtering."""

        def test_rejects_one_piece_codes(self):
            """Should reject One Piece card codes."""
            assert _is_valid_match(
                "OP05 Awakening of the New Era Luffy",
                "The Awakening"
            ) is False

        def test_rejects_straw_hat(self):
            """Should reject Straw Hat references."""
            assert _is_valid_match(
                "Straw Hat Crew Awakening Rare",
                "The Awakening"
            ) is False

        def test_rejects_luffy(self):
            """Should reject Luffy cards."""
            assert _is_valid_match(
                "Luffy Gear 5 Awakening Super Rare",
                "The Awakening"
            ) is False

    class TestMTGFiltering:
        """Tests for Magic: The Gathering filtering."""

        def test_rejects_magic_the_gathering(self):
            """Should reject Magic: The Gathering."""
            assert _is_valid_match(
                "Magic the Gathering Dragon Booster Pack",
                "Dragon's Gold"
            ) is False

        def test_rejects_planeswalker(self):
            """Should reject Planeswalker cards."""
            assert _is_valid_match(
                "Planeswalker Dragon Mythic Rare",
                "Dragon's Gold"
            ) is False

    class TestSportsCardFiltering:
        """Tests for sports card filtering."""

        def test_rejects_topps(self):
            """Should reject Topps cards."""
            assert _is_valid_match(
                "Topps Chrome Gold Refractor",
                "Dragon's Gold"
            ) is False

        def test_rejects_panini(self):
            """Should reject Panini cards."""
            assert _is_valid_match(
                "Panini Prizm Gold Parallel",
                "Dragon's Gold"
            ) is False

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_the_first_card_strict_matching(self):
        """'The First' card should require strict matching."""
        # Should match with card number
        assert _is_valid_match(
            "Wonders of the First The First 001/401 Formless Foil",
            "The First"
        ) is True

    def test_rejects_bundle_when_searching_pack(self):
        """Should reject bundles when searching for individual packs."""
        assert _is_valid_match(
            "Wonders of the First Play Bundle Blaster Box 6 Packs",
            "Booster Pack"
        ) is False

    def test_fuzzy_matching_typos(self):
        """Should handle minor typos with fuzzy matching."""
        # "Atherion" vs "Aetherion" - close enough
        assert _is_valid_match(
            "Wonders of the First Atherion Classic Foil",
            "Aetherion"
        ) is True


class TestDetectTreatment:
    """Tests for the _detect_treatment function."""

    # =========================================================================
    # Single Card Treatments
    # =========================================================================

    def test_classic_paper_default(self):
        """Default treatment for singles should be Classic Paper."""
        assert _detect_treatment("Wonders of the First Progo", "Single") == "Classic Paper"

    def test_classic_foil(self):
        """Should detect Classic Foil."""
        assert _detect_treatment("WOTF Progo Foil Holo", "Single") == "Classic Foil"

    def test_classic_foil_from_holo(self):
        """Should detect foil from 'holo' keyword."""
        assert _detect_treatment("Progo Holo Rare", "Single") == "Classic Foil"

    def test_stonefoil_single_word(self):
        """Should detect Stonefoil (single word)."""
        assert _detect_treatment("Deep Black Goop Stonefoil", "Single") == "Stonefoil"

    def test_stone_foil_two_words(self):
        """Should detect Stone Foil (two words)."""
        assert _detect_treatment("Deep Black Goop Stone Foil", "Single") == "Stonefoil"

    def test_formless_foil(self):
        """Should detect Formless Foil."""
        assert _detect_treatment("Zeltona Formless Foil", "Single") == "Formless Foil"

    def test_ocm_serialized(self):
        """Should detect OCM Serialized."""
        assert _detect_treatment("Progo OCM Serialized /50", "Single") == "OCM Serialized"

    def test_serialized_with_number(self):
        """Should detect serialized from /XX pattern."""
        assert _detect_treatment("Progo /99 Serialized", "Single") == "OCM Serialized"

    def test_serialized_slash_50(self):
        """Should detect /50 serialized."""
        assert _detect_treatment("Progo Foil /50", "Single") == "OCM Serialized"

    def test_prerelease(self):
        """Should detect Prerelease."""
        assert _detect_treatment("Skyrake Gearhawk Prerelease Promo", "Single") == "Prerelease"

    def test_promo(self):
        """Should detect Promo."""
        assert _detect_treatment("Skyrake Gearhawk Promo 006", "Single") == "Promo"

    def test_proof_sample(self):
        """Should detect Proof/Sample."""
        assert _detect_treatment("Character Proof Sample Card", "Single") == "Proof/Sample"

    def test_error_errata(self):
        """Should detect Error/Errata."""
        assert _detect_treatment("Progo Error Card Misprint", "Single") == "Error/Errata"

    # =========================================================================
    # Sealed Product Treatments (Simplified: Sealed, Open Box)
    # =========================================================================

    def test_sealed_default_for_box(self):
        """Default treatment for boxes should be Sealed."""
        assert _detect_treatment("Collector Booster Box", "Box") == "Sealed"

    def test_factory_sealed_maps_to_sealed(self):
        """Factory Sealed should map to Sealed."""
        assert _detect_treatment("Collector Box Factory Sealed", "Box") == "Sealed"

    def test_sealed_explicit(self):
        """Should detect explicit Sealed."""
        assert _detect_treatment("Play Bundle Sealed New", "Box") == "Sealed"

    def test_new_in_box_maps_to_sealed(self):
        """New in Box should map to Sealed."""
        assert _detect_treatment("Collector Box Brand New NIB", "Box") == "Sealed"

    def test_unopened_maps_to_sealed(self):
        """Unopened should map to Sealed."""
        assert _detect_treatment("Booster Box Unopened", "Box") == "Sealed"

    def test_open_box(self):
        """Should detect Open Box."""
        assert _detect_treatment("Collector Box Open Box", "Box") == "Open Box"

    def test_used_maps_to_open_box(self):
        """Used should map to Open Box."""
        assert _detect_treatment("Starter Set Used", "Box") == "Open Box"

    def test_opened_maps_to_open_box(self):
        """Opened should map to Open Box."""
        assert _detect_treatment("Booster Box Opened", "Bundle") == "Open Box"

    def test_mint_maps_to_sealed(self):
        """Mint condition should map to Sealed."""
        assert _detect_treatment("Collector Box Mint Condition", "Box") == "Sealed"

    # =========================================================================
    # Treatment Priority
    # =========================================================================

    def test_serialized_takes_priority_over_foil(self):
        """Serialized should take priority over foil."""
        assert _detect_treatment("Progo Foil /50 Serialized", "Single") == "OCM Serialized"

    def test_stonefoil_takes_priority_over_classic_foil(self):
        """Stonefoil should take priority over classic foil."""
        assert _detect_treatment("Progo Stone Foil Holo", "Single") == "Stonefoil"

    def test_formless_takes_priority_over_classic_foil(self):
        """Formless Foil should take priority over classic foil."""
        assert _detect_treatment("Progo Formless Foil", "Single") == "Formless Foil"


class TestDetectQuantity:
    """Tests for the _detect_quantity function."""

    def test_default_quantity_is_one(self):
        """Default quantity should be 1."""
        assert _detect_quantity("Wonders of the First Progo", "Single") == 1

    def test_detects_2x_prefix(self):
        """Should detect 2x prefix."""
        assert _detect_quantity("2x Wonders of the First Progo", "Single") == 2

    def test_detects_3x_prefix(self):
        """Should detect 3x prefix."""
        assert _detect_quantity("3x Progo Classic Paper", "Single") == 3

    def test_detects_lot_of_pattern(self):
        """Should detect 'lot of X' pattern."""
        assert _detect_quantity("Lot of 5 WOTF Cards", "Single") == 5

    def test_detects_card_lot(self):
        """Should detect 'X card lot' pattern."""
        assert _detect_quantity("10 card lot Wonders of the First", "Single") == 10

    def test_sealed_product_quantity(self):
        """Should detect quantity for sealed products."""
        assert _detect_quantity("2 Wonders of the First Play Bundles", "Box") == 2

    def test_ignores_pack_contents(self):
        """Should not count pack contents as quantity."""
        # "6 Booster Packs" inside a bundle is contents, not quantity
        assert _detect_quantity("Play Bundle Blaster Box with 6 Booster Packs", "Box") == 1

    def test_detects_count_suffix(self):
        """Should detect 'Xct' or 'X count' patterns."""
        assert _detect_quantity("5ct Booster Pack Lot", "Pack") == 5


class TestDetectBundlePackCount:
    """Tests for the _detect_bundle_pack_count function."""

    def test_play_bundle_is_6_packs(self):
        """Play Bundle should be 6 packs."""
        assert _detect_bundle_pack_count("Wonders of the First Play Bundle") == 6

    def test_blaster_box_is_6_packs(self):
        """Blaster Box should be 6 packs."""
        assert _detect_bundle_pack_count("Existence Blaster Box") == 6

    def test_collector_booster_box_is_12_packs(self):
        """Collector Booster Box should be 12 packs."""
        assert _detect_bundle_pack_count("WOTF Collector Booster Box") == 12

    def test_serialized_advantage_is_4_packs(self):
        """Serialized Advantage should be 4 packs."""
        assert _detect_bundle_pack_count("Serialized Advantage Box") == 4

    def test_single_pack_returns_zero(self):
        """Single pack should return 0 (not a bundle)."""
        assert _detect_bundle_pack_count("Collector Booster Pack") == 0

    def test_pack_with_bonus_returns_zero(self):
        """Pack with bonus cards should return 0."""
        assert _detect_bundle_pack_count("COLLECTOR BOOSTER PACK Sealed +12 bonus cards") == 0


class TestDetectProductSubtype:
    """Tests for the _detect_product_subtype function."""

    # =========================================================================
    # Box Subtypes
    # =========================================================================

    def test_collector_booster_box(self):
        """Should detect Collector Booster Box."""
        assert _detect_product_subtype("Wonders of the First Collector Booster Box", "Box") == "Collector Booster Box"

    def test_collector_booster_box_shorthand(self):
        """Should detect booster box as Collector Booster Box."""
        assert _detect_product_subtype("WOTF Existence Booster Box Sealed", "Box") == "Collector Booster Box"

    def test_case(self):
        """Should detect Case."""
        assert _detect_product_subtype("Wonders of the First 6-Box Case", "Box") == "Case"

    def test_generic_box(self):
        """Should default to Box for unrecognized box types."""
        assert _detect_product_subtype("Some Random Box", "Box") == "Box"

    # =========================================================================
    # Bundle Subtypes
    # =========================================================================

    def test_play_bundle(self):
        """Should detect Play Bundle."""
        assert _detect_product_subtype("Wonders of the First Play Bundle", "Bundle") == "Play Bundle"

    def test_blaster_box(self):
        """Should detect Blaster Box."""
        assert _detect_product_subtype("WOTF Existence Blaster Box", "Bundle") == "Blaster Box"

    def test_serialized_advantage(self):
        """Should detect Serialized Advantage."""
        assert _detect_product_subtype("Wonders Serialized Advantage Box", "Bundle") == "Serialized Advantage"

    def test_starter_set(self):
        """Should detect Starter Set."""
        assert _detect_product_subtype("WOTF 2-Player Starter Set", "Bundle") == "Starter Set"

    def test_starter_kit(self):
        """Should detect Starter Kit as Starter Set."""
        assert _detect_product_subtype("Wonders of the First Starter Kit", "Bundle") == "Starter Set"

    def test_generic_bundle(self):
        """Generic bundle should default to Play Bundle."""
        assert _detect_product_subtype("WOTF Bundle Pack", "Bundle") == "Play Bundle"

    # =========================================================================
    # Pack Subtypes
    # =========================================================================

    def test_collector_booster_pack(self):
        """Should detect Collector Booster Pack."""
        assert _detect_product_subtype("Wonders Collector Booster Pack", "Pack") == "Collector Booster Pack"

    def test_play_booster_pack(self):
        """Should detect Play Booster Pack."""
        assert _detect_product_subtype("WOTF Play Booster Pack", "Pack") == "Play Booster Pack"

    def test_silver_pack(self):
        """Should detect Silver Pack."""
        assert _detect_product_subtype("Wonders of the First Silver Pack Promo", "Pack") == "Silver Pack"

    def test_generic_booster_pack(self):
        """Generic booster should default to Collector Booster Pack."""
        assert _detect_product_subtype("WOTF Booster Pack Sealed", "Pack") == "Collector Booster Pack"

    def test_generic_pack(self):
        """Generic pack should default to Pack."""
        assert _detect_product_subtype("Some Random Pack", "Pack") == "Pack"

    # =========================================================================
    # Lot Subtypes
    # =========================================================================

    def test_lot(self):
        """Should detect Lot."""
        assert _detect_product_subtype("WOTF Card Lot 50 Cards", "Lot") == "Lot"

    def test_bulk(self):
        """Should detect Bulk."""
        assert _detect_product_subtype("Wonders Bulk Cards 100ct", "Lot") == "Bulk"

    # =========================================================================
    # Singles (no subtype)
    # =========================================================================

    def test_single_returns_none(self):
        """Singles should return None for subtype."""
        assert _detect_product_subtype("Progo Stonefoil", "Single") is None


class TestQuantityYearExclusion:
    """Tests for year-exclusion in quantity detection."""

    def test_excludes_2024_as_quantity(self):
        """Should not detect 2024 as quantity (it's a year)."""
        assert _detect_quantity("2024 Wonders of the First Progo", "Single") == 1

    def test_excludes_2025_as_quantity(self):
        """Should not detect 2025 as quantity (it's a year)."""
        assert _detect_quantity("2025 Wonders of the First Collector Box", "Box") == 1

    def test_excludes_2023_as_quantity(self):
        """Should not detect 2023 as quantity (it's a year)."""
        assert _detect_quantity("2023 WOTF Existence Booster Pack", "Pack") == 1

    def test_still_detects_valid_quantities(self):
        """Should still detect valid small quantities."""
        assert _detect_quantity("2x Wonders of the First Play Bundle", "Bundle") == 2
        assert _detect_quantity("3 Wonders Booster Packs", "Pack") == 3
        assert _detect_quantity("5ct Collector Pack Lot", "Pack") == 5

    def test_lot_of_pattern_with_year(self):
        """Lot of pattern should work but not match years."""
        assert _detect_quantity("Lot of 10 WOTF Cards", "Single") == 10
        assert _detect_quantity("2024 Lot of 5 Cards", "Single") == 5

    def test_two_digit_quantity_at_start(self):
        """Two-digit quantity at start should work."""
        assert _detect_quantity("12 Wonders Booster Packs", "Pack") == 12
        assert _detect_quantity("50 Card Lot WOTF", "Single") == 50

    def test_four_digit_non_year_rejected(self):
        """Four-digit numbers that aren't years should still be rejected as too large."""
        # 1500 is not a year but also unreasonable as quantity
        assert _detect_quantity("1500 Card Lot", "Single") == 1


class TestContaminationFiltering:
    """Integration tests for contamination filtering."""

    def test_filters_all_yugioh_variants(self):
        """Should filter all common Yu-Gi-Oh card patterns."""
        yugioh_titles = [
            "Ruddy Rose Dragon MP22-EN077 1st Edition",
            "Blue-Eyes White Dragon MGED-EN001 Gold Rare",
            "Dark Magician Konami Official",
            "Exodia the Forbidden One Secret Rare",
            "Red-Eyes Black Dragon Tin of the Pharaoh's Gods",
        ]
        for title in yugioh_titles:
            assert _is_valid_match(title, "Dragon's Gold") is False, f"Failed to filter: {title}"

    def test_filters_yugioh_stax_en_codes(self):
        """Should filter Yu-Gi-Oh STAX-EN 2-Player Starter Set codes."""
        stax_titles = [
            "Divine Arsenal AA-ZEUS - Sky Thunder STAX-EN044 2-Player Starter Set",
            "Number 20: Giga-Brilliant STAX-EN042 2-Player Starter Set",
            "Castel, the Skyblaster Musketeer STAX-EN043 2-Player Starter Set",
            "Giant Soldier of Stone STAX-EN001 Common",
            "Burden of the Mighty STAX-EN032 2-Player Starter Set",
        ]
        for title in stax_titles:
            assert _is_valid_match(title, "2-Player Starter Set") is False, f"Failed to filter: {title}"

    def test_filters_yugioh_premium_gold_codes(self):
        """Should filter Yu-Gi-Oh Premium Gold set codes (PGL2, PGLD)."""
        pgl_titles = [
            "Five-Headed Dragon PGL2-EN078 Premium Gold: Return of the Bling",
            "The Winged Dragon of Ra PGLD-EN031 Premium Gold 1st Edition",
            "Debris Dragon PGL2-EN031 Premium Gold: Return of the Bling",
            "Dragocytos Corrupted Nethersoul Dragon PGL3-EN060",
        ]
        for title in pgl_titles:
            assert _is_valid_match(title, "Dragon's Gold") is False, f"Failed to filter: {title}"

    def test_filters_yugioh_specific_cards(self):
        """Should filter specific Yu-Gi-Oh cards that match WOTF names."""
        specific_titles = [
            "Divine Arsenal AA-ZEUS - Sky Thunder Ultra Rare",
            "Trishula, Dragon of the Ice Barrier Secret Rare",
            "Five-Headed Dragon Gold Rare",
            "Winged Dragon of Ra PGLD Gold",
            "Albion the Branded Dragon MP22",
            "Giga-Brilliant XYZ Monster",
        ]
        for title in specific_titles:
            assert _is_valid_match(title, "Dragon's Gold") is False, f"Failed to filter: {title}"

    def test_filters_all_dbz_variants(self):
        """Should filter all common Dragon Ball Z patterns."""
        dbz_titles = [
            "Dragonball Z CCG The Awakening Goku",
            "Dragon Ball Z Hercule WA-079 Gold",
            "DBZ Android 20 1st Edition",
            "Vegeta Level 5 The Awakening",
        ]
        for title in dbz_titles:
            assert _is_valid_match(title, "The Awakening") is False, f"Failed to filter: {title}"

    def test_filters_all_pokemon_variants(self):
        """Should filter all common Pokemon patterns."""
        pokemon_titles = [
            "Pokemon Charizard VMAX Rainbow",
            "Pikachu Evolving Skies Holo",
            "Scarlet Violet Booster Box",
            "Mewtwo GX Full Art",
        ]
        for title in pokemon_titles:
            assert _is_valid_match(title, "Charizard") is False, f"Failed to filter: {title}"

    def test_allows_legitimate_wotf_cards(self):
        """Should allow legitimate WOTF cards through."""
        wotf_titles = [
            "Wonders of the First Dragon's Gold Classic Foil",
            "WOTF Existence The Awakening Formless Foil",
            "Wonders of the First Progo /50 Serialized",
            "2024 WOTF Zeltona Stonefoil",
        ]
        for title in wotf_titles:
            card_name = "Dragon's Gold" if "Dragon" in title else "The Awakening" if "Awakening" in title else "Progo" if "Progo" in title else "Zeltona"
            assert _is_valid_match(title, card_name) is True, f"Incorrectly filtered: {title}"

    def test_allows_legitimate_wotf_sealed_products(self):
        """Should allow legitimate WOTF sealed products."""
        wotf_sealed = [
            ("Wonders of the First 2-Player Starter Set", "2-Player Starter Set"),
            ("WOTF Existence 2-Player Starter Kit", "2-Player Starter Kit"),
            ("Wonders of the First Collector Booster Box Sealed", "Collector Booster Box"),
            ("WOTF Play Bundle Blaster Box", "Play Bundle"),
            ("Wonders of the First Existence Booster Pack", "Booster Pack"),
        ]
        for title, card_name in wotf_sealed:
            assert _is_valid_match(title, card_name) is True, f"Incorrectly filtered: {title}"


class TestRealWorldContaminationCases:
    """Tests based on actual contamination cases found in production."""

    def test_dragons_gold_contamination_cases(self):
        """Real contamination cases that hit Dragon's Gold card."""
        # These exact titles were found in production contaminating Dragon's Gold
        contaminated_titles = [
            "Ruddy Rose Dragon MP22-EN077 2022 Tin of the Pharaoh's Gods 1st Edition",
            "Five-Headed Dragon PGL2-EN078 Premium Gold: Return of the Bling 1st Edition",
            "The Winged Dragon of Ra PGLD-EN031 Premium Gold 1st Edition",
            "Roxrose Dragon MP22-EN060 2022 Tin of the Pharaoh's Gods 1st Edition",
            "Trishula, Dragon of the Ice Barrier MGED-EN027 1st Edition Gold Rare LP",
            "Albion the Branded Dragon MP22-EN076 2022 Tin of the Pharaoh's Gods",
            "Debris Dragon PGL2-EN031 Premium Gold: Return of the Bling",
        ]
        for title in contaminated_titles:
            assert _is_valid_match(title, "Dragon's Gold") is False, \
                f"CRITICAL: Failed to filter known contamination: {title}"

    def test_starter_set_contamination_cases(self):
        """Real contamination cases that hit 2-Player Starter Set."""
        # These exact titles were found contaminating WOTF starter products
        contaminated_titles = [
            "Divine Arsenal AA-ZEUS - Sky Thunder STAX-EN044 2-Player Starter Set",
            "Number 20: Giga-Brilliant STAX-EN042 2-Player Starter Set",
            "2-Player Starter Set #STAX-EN043 Castel, the Skyblaster Musketeer",
            "2-Player Starter Set #STAX-EN032 Burden of the Mighty",
            "Giant Soldier of Stone Common 2-Player Starter Set STAX-EN",
            "Castel, the Skyblaster Musketeer STAX-EN043 2-Player Starter Set",
        ]
        for title in contaminated_titles:
            assert _is_valid_match(title, "2-Player Starter Set") is False, \
                f"CRITICAL: Failed to filter known contamination: {title}"

    def test_mtg_contamination_cases(self):
        """Real MTG contamination cases."""
        contaminated_titles = [
            "Magic: The Gathering Purphoros, God Of The Forge Lightly Played",
        ]
        for title in contaminated_titles:
            assert _is_valid_match(title, "Purphoros") is False, \
                f"CRITICAL: Failed to filter MTG contamination: {title}"

    def test_legitimate_wotf_with_dragon_keyword(self):
        """WOTF cards with 'Dragon' should NOT be filtered."""
        # These are legitimate WOTF listings
        legitimate_titles = [
            "Wonders of the First Dragon's Gold Classic Paper",
            "WOTF Existence Dragon's Gold 248/401 Formless Foil",
            "2x - Wonders of the First - Dragon's Gold 248/401 Primary Item!",
            "Wonders of the First Dragon's Gold Stonefoil",
        ]
        for title in legitimate_titles:
            assert _is_valid_match(title, "Dragon's Gold") is True, \
                f"CRITICAL: Incorrectly filtered legitimate WOTF: {title}"

    def test_legitimate_wotf_starter_products(self):
        """WOTF starter products should NOT be filtered."""
        legitimate_cases = [
            ("Wonders Of The First 2-Player Starter Box 1st Edition", "2-Player Starter Box"),
            ("Wonders of the First 2-Player Starter Kit includes PROMO", "2-Player Starter Kit"),
            ("WOTF Existence 2-Player Starter Set Sealed", "2-Player Starter Set"),
        ]
        for title, card_name in legitimate_cases:
            assert _is_valid_match(title, card_name) is True, \
                f"CRITICAL: Incorrectly filtered legitimate WOTF: {title}"


class TestAIExtractorValidation:
    """Tests for AI extractor validation (rule-based portion)."""

    def test_wotf_indicators_detected(self):
        """Test that WOTF indicators are properly detected."""
        from app.services.ai_extractor import get_ai_extractor

        extractor = get_ai_extractor()

        # Test WOTF indicators
        result = extractor.validate_wotf_listing(
            "Wonders of the First Progo Formless Foil",
            "Progo"
        )
        assert result["is_wotf"] is True
        assert result["confidence"] >= 0.9

    def test_yugioh_indicators_detected(self):
        """Test that Yu-Gi-Oh indicators are properly detected."""
        from app.services.ai_extractor import get_ai_extractor

        extractor = get_ai_extractor()

        result = extractor.validate_wotf_listing(
            "Ruddy Rose Dragon MP22-EN077 Tin of the Pharaoh's Gods",
            "Dragon's Gold"
        )
        assert result["is_wotf"] is False
        assert result["detected_tcg"] == "Yu-Gi-Oh"

    def test_dbz_indicators_detected(self):
        """Test that Dragon Ball Z indicators are properly detected."""
        from app.services.ai_extractor import get_ai_extractor

        extractor = get_ai_extractor()

        result = extractor.validate_wotf_listing(
            "Dragonball Z CCG The Awakening Hercule",
            "The Awakening"
        )
        assert result["is_wotf"] is False
        assert result["detected_tcg"] == "Dragon Ball Z"

    def test_pokemon_indicators_detected(self):
        """Test that Pokemon indicators are properly detected."""
        from app.services.ai_extractor import get_ai_extractor

        extractor = get_ai_extractor()

        result = extractor.validate_wotf_listing(
            "Pokemon Charizard VMAX Evolving Skies",
            "Charizard"
        )
        assert result["is_wotf"] is False
        assert result["detected_tcg"] == "Pokemon"

    def test_ambiguous_listing_without_indicators(self):
        """Test handling of ambiguous listings without clear indicators (no AI)."""
        from app.services.ai_extractor import get_ai_extractor

        extractor = get_ai_extractor()

        # Temporarily disable AI client to test rule-based fallback
        original_client = extractor.client
        extractor.client = None

        try:
            # Ambiguous - no clear TCG indicators
            result = extractor.validate_wotf_listing(
                "Dragon Card Foil Rare",
                "Dragon's Gold"
            )
            # Without AI, should return low confidence when ambiguous
            assert result["confidence"] <= 0.7
            assert "no AI available" in result["reason"].lower() or result["confidence"] == 0.5
        finally:
            # Restore client
            extractor.client = original_client


class TestTreatmentExtractionEdgeCases:
    """Edge case tests for treatment extraction."""

    def test_stone_foil_case_insensitive(self):
        """Stone foil detection should be case insensitive."""
        assert _detect_treatment("Deep Black Goop STONEFOIL", "Single") == "Stonefoil"
        assert _detect_treatment("Deep Black Goop StOnEfOiL", "Single") == "Stonefoil"

    def test_formless_without_foil_word(self):
        """Should detect formless even if 'foil' is implied."""
        assert _detect_treatment("Zeltona Formless Rare", "Single") == "Formless Foil"

    def test_multiple_treatment_keywords(self):
        """Should handle multiple treatment keywords correctly."""
        # Serialized should win over foil
        assert _detect_treatment("Progo Formless Foil /50 OCM", "Single") == "OCM Serialized"

    def test_prerelease_promo_distinction(self):
        """Should distinguish between prerelease and regular promo."""
        assert _detect_treatment("Skyrake Gearhawk Prerelease Event Card", "Single") == "Prerelease"
        assert _detect_treatment("Skyrake Gearhawk Store Promo", "Single") == "Promo"

    def test_refractor_detected_as_foil(self):
        """Refractor should be detected as foil variant."""
        assert _detect_treatment("Progo Refractor Rare", "Single") == "Classic Foil"


class TestAIExtractorEnhancements:
    """Tests for the enhanced AI extractor features."""

    def test_feedback_log_tracking(self):
        """Feedback log should track validation decisions."""
        from app.services.ai_extractor import get_ai_extractor

        extractor = get_ai_extractor()
        extractor.clear_feedback_log()

        # Make some validation calls
        extractor.validate_wotf_listing(
            "Wonders of the First Progo Stonefoil",
            "Progo"
        )
        extractor.validate_wotf_listing(
            "Yu-Gi-Oh MP22-EN060 Roxrose Dragon",
            "Dragon's Gold"
        )

        # Check feedback log
        log = extractor.get_feedback_log()
        assert len(log) >= 2

        # Check structure
        entry = log[-1]
        assert "timestamp" in entry
        assert "title" in entry
        assert "card_name" in entry
        assert "decision" in entry
        assert "method" in entry

    def test_rejection_log_filters_correctly(self):
        """Rejection log should only show rejected listings."""
        from app.services.ai_extractor import get_ai_extractor

        extractor = get_ai_extractor()
        extractor.clear_feedback_log()

        # Make one accept and one reject
        extractor.validate_wotf_listing(
            "Wonders of the First Progo Classic Paper",
            "Progo"
        )
        extractor.validate_wotf_listing(
            "Pokemon Pikachu VMAX",
            "The Awakening"
        )

        rejections = extractor.get_rejection_log()
        assert len(rejections) >= 1
        assert all(not r["decision"]["is_wotf"] for r in rejections)

    def test_confidence_tier_high_with_wotf_indicator(self):
        """High tier should be assigned when WOTF indicator present."""
        from app.services.ai_extractor import get_ai_extractor

        extractor = get_ai_extractor()
        result = extractor.validate_wotf_listing(
            "Progo Stonefoil Existence Set 123/401",
            "Progo"
        )

        assert result["is_wotf"] is True
        assert result["confidence"] >= 0.9
        assert result["tier"] == "HIGH"

    def test_confidence_tier_high_with_non_wotf_indicator(self):
        """High tier should be assigned when non-WOTF indicator present."""
        from app.services.ai_extractor import get_ai_extractor

        extractor = get_ai_extractor()
        result = extractor.validate_wotf_listing(
            "Konami Yu-Gi-Oh Dark Magician",
            "Dragon's Gold"
        )

        assert result["is_wotf"] is False
        assert result["confidence"] >= 0.9
        assert result["tier"] == "HIGH"

    def test_structured_extraction_basic(self):
        """Structured extraction should extract all fields."""
        from app.services.ai_extractor import get_ai_extractor

        extractor = get_ai_extractor()
        result = extractor.extract_structured_data(
            "Wonders of the First Progo Stonefoil 234/401 PSA 10",
            "Progo"
        )

        assert result["card_name"] == "Progo"
        assert result["treatment"] == "Stonefoil"
        assert result["card_number"] == "234/401"
        assert result["is_graded"] is True
        assert result["grading_info"]["service"] == "PSA"
        assert result["grading_info"]["grade"] == 10.0
        assert result["is_wotf"] is True

    def test_structured_extraction_set_detection(self):
        """Should detect set name from title."""
        from app.services.ai_extractor import get_ai_extractor

        extractor = get_ai_extractor()

        # Existence set
        result = extractor.extract_structured_data(
            "Progo Existence Formless Foil",
            "Progo"
        )
        assert result["set_name"] == "Existence"

        # Genesis set
        result = extractor.extract_structured_data(
            "Progo Genesis Classic Foil",
            "Progo"
        )
        assert result["set_name"] == "Genesis"

    def test_structured_extraction_treatments(self):
        """Should detect all treatment types."""
        from app.services.ai_extractor import get_ai_extractor

        extractor = get_ai_extractor()

        test_cases = [
            ("Progo Classic Paper WOTF", "Classic Paper"),
            ("Progo Classic Foil WOTF", "Classic Foil"),
            ("Progo Stonefoil WOTF", "Stonefoil"),
            ("Progo Formless Foil WOTF", "Formless Foil"),
            ("Progo OCM Serialized /50 WOTF", "OCM Serialized"),
            ("Progo Prerelease Event WOTF", "Prerelease"),
            ("Progo Promo Card WOTF", "Promo"),
        ]

        for title, expected_treatment in test_cases:
            result = extractor.extract_structured_data(title, "Progo")
            assert result["treatment"] == expected_treatment, f"Failed for: {title}"

    def test_grading_extraction(self):
        """Should extract grading info from various formats."""
        from app.services.ai_extractor import get_ai_extractor

        extractor = get_ai_extractor()

        # PSA grading
        result = extractor.extract_structured_data(
            "Progo WOTF PSA 10 Gem Mint",
            "Progo"
        )
        assert result["is_graded"] is True
        assert result["grading_info"]["service"] == "PSA"
        assert result["grading_info"]["grade"] == 10.0

        # CGC grading
        result = extractor.extract_structured_data(
            "Progo WOTF CGC 9.5",
            "Progo"
        )
        assert result["is_graded"] is True
        assert result["grading_info"]["service"] == "CGC"
        assert result["grading_info"]["grade"] == 9.5

        # BGS grading
        result = extractor.extract_structured_data(
            "Progo WOTF BGS 9",
            "Progo"
        )
        assert result["is_graded"] is True
        assert result["grading_info"]["service"] == "BGS"
        assert result["grading_info"]["grade"] == 9.0

    def test_metrics_tracking(self):
        """Should track validation metrics correctly."""
        from app.services.ai_extractor import get_ai_extractor

        extractor = get_ai_extractor()
        extractor.reset_metrics()

        # Make some validations
        extractor.validate_wotf_listing("Progo WOTF Stonefoil", "Progo")  # Accept
        extractor.validate_wotf_listing("Konami Yu-Gi-Oh Card", "Test")  # Reject

        metrics = extractor.get_metrics()
        assert metrics["rule_based_accepts"] >= 1
        assert metrics["rule_based_rejects"] >= 1

    def test_expanded_wotf_indicators(self):
        """Should recognize all expanded WOTF indicators."""
        from app.services.ai_extractor import get_ai_extractor

        extractor = get_ai_extractor()

        wotf_titles = [
            "Wonders of the First Progo",
            "WOTF Existence Booster Pack",
            "Genesis Set Collector Box",
            "Progo Formless Foil 123/401",
            "Stone-foil Variant Card",
            "Play Bundle 6 Packs",
            "Serialized Advantage Box",
            "2-Player Starter Set",
        ]

        for title in wotf_titles:
            result = extractor.validate_wotf_listing(title, "Progo")
            assert result["is_wotf"] is True, f"Failed for: {title}"

    def test_expanded_non_wotf_indicators(self):
        """Should recognize all expanded non-WOTF indicators."""
        from app.services.ai_extractor import get_ai_extractor

        extractor = get_ai_extractor()

        non_wotf_titles = [
            # Yu-Gi-Oh
            ("MP23-EN001 Card", "Yu-Gi-Oh"),
            ("Konami Official Card", "Yu-Gi-Oh"),
            ("Dark Magician Ultimate Rare", "Yu-Gi-Oh"),
            ("Starlight Rare Card", "Yu-Gi-Oh"),
            # Dragon Ball Z
            ("DBZ CCG Card WA-079", "Dragon Ball Z"),
            ("Goku Super Saiyan Card", "Dragon Ball Z"),
            ("Kamehameha Attack Card", "Dragon Ball Z"),
            # Pokemon
            ("Pokemon Scarlet Violet Card", "Pokemon"),
            ("Charizard VMAX Rainbow", "Pokemon"),
            ("Evolving Skies Booster", "Pokemon"),
            # One Piece
            ("One Piece TCG OP05", "One Piece"),
            ("Luffy Romance Dawn", "One Piece"),
            # MTG
            ("Magic the Gathering Planeswalker", "MTG"),
            ("MTG Commander Deck", "MTG"),
            # Sports
            ("Topps Chrome Rookie Card", "Sports Cards"),
            ("Panini Prizm NBA", "Sports Cards"),
            # Other TCGs
            ("Disney Lorcana Starter", "Other TCGs"),
            ("Flesh and Blood Card", "Other TCGs"),
        ]

        for title, expected_tcg in non_wotf_titles:
            result = extractor.validate_wotf_listing(title, "Test Card")
            assert result["is_wotf"] is False, f"Should reject: {title}"
            assert result["detected_tcg"] == expected_tcg, f"Wrong TCG for: {title}"
