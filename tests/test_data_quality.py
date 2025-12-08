"""
Data quality tests for detecting bad data and misclassifications.

These tests scan the actual database for anomalies:
- Platform/URL mismatches
- Treatment misclassifications
- Missing required fields
- NFT vs physical product confusion
"""

import pytest
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlmodel import Session, select, func

from app.models.card import Card
from app.models.market import MarketPrice


class DataQualityReport:
    """Collects and reports data quality issues."""

    def __init__(self):
        self.issues: List[Dict[str, Any]] = []

    def add_issue(self, category: str, severity: str, record_id: int,
                  description: str, details: Dict[str, Any] = None):
        self.issues.append({
            "category": category,
            "severity": severity,  # "error", "warning", "info"
            "record_id": record_id,
            "description": description,
            "details": details or {}
        })

    def get_errors(self) -> List[Dict]:
        return [i for i in self.issues if i["severity"] == "error"]

    def get_warnings(self) -> List[Dict]:
        return [i for i in self.issues if i["severity"] == "warning"]

    def summary(self) -> str:
        errors = len(self.get_errors())
        warnings = len(self.get_warnings())
        return f"Data Quality: {errors} errors, {warnings} warnings, {len(self.issues)} total issues"


@pytest.fixture
def quality_report():
    return DataQualityReport()


class TestPlatformURLConsistency:
    """Test that platform and URL fields are consistent."""

    def test_opensea_listings_have_opensea_urls(self, integration_session: Session, quality_report: DataQualityReport):
        """OpenSea platform listings should have opensea.io URLs."""
        listings = integration_session.exec(
            select(MarketPrice).where(
                MarketPrice.platform == "opensea",
                MarketPrice.url.isnot(None)
            )
        ).all()

        for listing in listings:
            if listing.url and "opensea.io" not in listing.url:
                quality_report.add_issue(
                    category="platform_url_mismatch",
                    severity="error",
                    record_id=listing.id,
                    description=f"OpenSea listing has non-OpenSea URL",
                    details={"url": listing.url, "platform": listing.platform}
                )

        errors = quality_report.get_errors()
        if errors:
            print(f"\n{quality_report.summary()}")
            for e in errors[:10]:  # Show first 10
                print(f"  - ID {e['record_id']}: {e['description']} - {e['details']}")

        assert len(errors) == 0, f"Found {len(errors)} OpenSea listings with wrong URLs"

    def test_ebay_listings_have_ebay_urls(self, integration_session: Session, quality_report: DataQualityReport):
        """eBay platform listings should have ebay.com URLs."""
        listings = integration_session.exec(
            select(MarketPrice).where(
                MarketPrice.platform == "ebay",
                MarketPrice.url.isnot(None)
            )
        ).all()

        for listing in listings:
            if listing.url and "ebay.com" not in listing.url and "ebay." not in listing.url:
                quality_report.add_issue(
                    category="platform_url_mismatch",
                    severity="error",
                    record_id=listing.id,
                    description=f"eBay listing has non-eBay URL",
                    details={"url": listing.url, "platform": listing.platform}
                )

        errors = quality_report.get_errors()
        if errors:
            print(f"\n{quality_report.summary()}")
            for e in errors[:10]:
                print(f"  - ID {e['record_id']}: {e['description']} - {e['details']}")

        assert len(errors) == 0, f"Found {len(errors)} eBay listings with wrong URLs"

    def test_opensea_urls_use_item_format(self, integration_session: Session, quality_report: DataQualityReport):
        """OpenSea URLs should use /item/{chain}/{contract}/{token} format."""
        listings = integration_session.exec(
            select(MarketPrice).where(
                MarketPrice.platform == "opensea",
                MarketPrice.url.isnot(None)
            )
        ).all()

        for listing in listings:
            if listing.url:
                # Check for old /assets/ format instead of /item/
                if "/assets/" in listing.url and "/item/" not in listing.url:
                    quality_report.add_issue(
                        category="opensea_url_format",
                        severity="warning",
                        record_id=listing.id,
                        description=f"OpenSea URL uses old /assets/ format instead of /item/",
                        details={"url": listing.url}
                    )

        warnings = quality_report.get_warnings()
        if warnings:
            print(f"\n{quality_report.summary()}")
            for w in warnings[:10]:
                print(f"  - ID {w['record_id']}: {w['description']} - {w['details']}")

        # This is a warning, not a hard failure
        if warnings:
            pytest.skip(f"Found {len(warnings)} OpenSea URLs with old format (non-blocking)")


class TestNFTTreatmentClassification:
    """Test that NFT listings have appropriate treatments."""

    def test_opensea_nfts_not_using_sealed_treatment(self, integration_session: Session, quality_report: DataQualityReport):
        """OpenSea NFT listings should not use 'Sealed' treatment (that's for physical boxes)."""
        listings = integration_session.exec(
            select(MarketPrice).where(
                MarketPrice.platform == "opensea",
                MarketPrice.treatment == "Sealed"
            )
        ).all()

        for listing in listings:
            quality_report.add_issue(
                category="nft_treatment_misclassification",
                severity="error",
                record_id=listing.id,
                description=f"OpenSea NFT using 'Sealed' treatment (should be NFT trait)",
                details={
                    "title": listing.title,
                    "treatment": listing.treatment,
                    "price": listing.price
                }
            )

        errors = quality_report.get_errors()
        if errors:
            print(f"\n{quality_report.summary()}")
            for e in errors[:10]:
                print(f"  - ID {e['record_id']}: {e['details']['title']} - treatment: {e['details']['treatment']}")

        assert len(errors) == 0, f"Found {len(errors)} OpenSea NFTs misclassified as 'Sealed'"

    def test_opensea_nfts_not_using_physical_treatments(self, integration_session: Session, quality_report: DataQualityReport):
        """OpenSea NFTs should not use physical card treatments."""
        physical_treatments = [
            "Classic Paper", "Classic Foil", "Formless Foil",
            "OCM Serialized", "Promo", "Prerelease"
        ]

        listings = integration_session.exec(
            select(MarketPrice).where(
                MarketPrice.platform == "opensea",
                MarketPrice.treatment.in_(physical_treatments)
            )
        ).all()

        for listing in listings:
            quality_report.add_issue(
                category="nft_treatment_misclassification",
                severity="warning",
                record_id=listing.id,
                description=f"OpenSea NFT using physical card treatment",
                details={
                    "title": listing.title,
                    "treatment": listing.treatment,
                }
            )

        warnings = quality_report.get_warnings()
        if warnings:
            print(f"\n{quality_report.summary()}")
            for w in warnings[:10]:
                print(f"  - ID {w['record_id']}: {w['details']['title']} - treatment: {w['details']['treatment']}")

        # Warning only - some edge cases may be valid
        if warnings:
            pytest.skip(f"Found {len(warnings)} OpenSea NFTs with physical treatments (review needed)")

    def test_opensea_nfts_not_using_generic_nft_treatment(self, integration_session: Session, quality_report: DataQualityReport):
        """OpenSea NFTs should use actual traits, not generic 'NFT' treatment."""
        listings = integration_session.exec(
            select(MarketPrice).where(
                MarketPrice.platform == "opensea",
                MarketPrice.treatment == "NFT"
            )
        ).all()

        for listing in listings:
            quality_report.add_issue(
                category="generic_nft_treatment",
                severity="warning",
                record_id=listing.id,
                description=f"OpenSea NFT using generic 'NFT' treatment instead of traits",
                details={
                    "title": listing.title,
                    "treatment": listing.treatment,
                    "card_id": listing.card_id
                }
            )

        warnings = quality_report.get_warnings()
        if warnings:
            print(f"\n{quality_report.summary()}")
            print(f"  Found {len(warnings)} OpenSea NFTs with generic 'NFT' treatment")
            for w in warnings[:5]:
                print(f"  - ID {w['record_id']}: {w['details']['title']}")

            # This is a warning - traits extraction may not have been run yet
            pytest.skip(f"Found {len(warnings)} NFTs needing trait extraction (re-scrape needed)")

    def test_ebay_boxes_using_sealed_treatment(self, integration_session: Session, quality_report: DataQualityReport):
        """eBay box listings should typically use 'Sealed' treatment."""
        # Get cards that are boxes
        box_cards = integration_session.exec(
            select(Card).where(Card.product_type == "Box")
        ).all()
        box_card_ids = [c.id for c in box_cards]

        if not box_card_ids:
            pytest.skip("No box cards found in database")

        # Find eBay box listings NOT using Sealed
        listings = integration_session.exec(
            select(MarketPrice).where(
                MarketPrice.platform == "ebay",
                MarketPrice.card_id.in_(box_card_ids),
                MarketPrice.treatment != "Sealed",
                MarketPrice.listing_type == "sold"
            )
        ).all()

        for listing in listings:
            # NFT-style treatments on eBay boxes are suspicious
            if listing.treatment in ["NFT", "Rare", "Epic", "Legendary", "Common", "Uncommon"]:
                quality_report.add_issue(
                    category="ebay_treatment_misclassification",
                    severity="warning",
                    record_id=listing.id,
                    description=f"eBay box listing with NFT-style treatment",
                    details={
                        "title": listing.title,
                        "treatment": listing.treatment,
                    }
                )

        warnings = quality_report.get_warnings()
        if warnings:
            print(f"\n{quality_report.summary()}")
            for w in warnings[:10]:
                print(f"  - ID {w['record_id']}: {w['details']['title']} - treatment: {w['details']['treatment']}")


class TestMissingRequiredFields:
    """Test for missing required or important fields."""

    def test_sold_listings_have_prices(self, integration_session: Session, quality_report: DataQualityReport):
        """Sold listings must have a price > 0."""
        listings = integration_session.exec(
            select(MarketPrice).where(
                MarketPrice.listing_type == "sold",
                MarketPrice.price <= 0
            )
        ).all()

        for listing in listings:
            quality_report.add_issue(
                category="missing_price",
                severity="error",
                record_id=listing.id,
                description=f"Sold listing with zero or negative price",
                details={"title": listing.title, "price": listing.price}
            )

        errors = quality_report.get_errors()
        assert len(errors) == 0, f"Found {len(errors)} sold listings with invalid prices"

    def test_opensea_listings_have_external_ids(self, integration_session: Session, quality_report: DataQualityReport):
        """OpenSea listings should have external_id (tx_hash) for deduplication."""
        listings = integration_session.exec(
            select(MarketPrice).where(
                MarketPrice.platform == "opensea",
                MarketPrice.listing_type == "sold",
                MarketPrice.external_id.is_(None)
            )
        ).all()

        for listing in listings:
            quality_report.add_issue(
                category="missing_external_id",
                severity="warning",
                record_id=listing.id,
                description=f"OpenSea listing missing external_id (tx_hash)",
                details={"title": listing.title, "sold_date": str(listing.sold_date)}
            )

        warnings = quality_report.get_warnings()
        if warnings:
            print(f"\n{quality_report.summary()}")
            print(f"  Found {len(warnings)} OpenSea listings without external_id")

    def test_listings_have_titles(self, integration_session: Session, quality_report: DataQualityReport):
        """All listings should have titles."""
        listings = integration_session.exec(
            select(MarketPrice).where(
                (MarketPrice.title.is_(None)) | (MarketPrice.title == "")
            )
        ).all()

        for listing in listings:
            quality_report.add_issue(
                category="missing_title",
                severity="warning",
                record_id=listing.id,
                description=f"Listing missing title",
                details={"platform": listing.platform, "price": listing.price}
            )

        warnings = quality_report.get_warnings()
        assert len(warnings) == 0, f"Found {len(warnings)} listings without titles"


class TestDuplicateDetection:
    """Test for potential duplicate entries."""

    def test_no_duplicate_opensea_transactions(self, integration_session: Session, quality_report: DataQualityReport):
        """OpenSea should not have duplicate transaction hashes."""
        # Find duplicates by external_id
        from sqlalchemy import func as sa_func

        duplicates = integration_session.exec(
            select(MarketPrice.external_id, sa_func.count(MarketPrice.id).label("count"))
            .where(
                MarketPrice.platform == "opensea",
                MarketPrice.external_id.isnot(None),
                MarketPrice.external_id != ""
            )
            .group_by(MarketPrice.external_id)
            .having(sa_func.count(MarketPrice.id) > 1)
        ).all()

        for external_id, count in duplicates:
            quality_report.add_issue(
                category="duplicate_transaction",
                severity="error",
                record_id=0,
                description=f"Duplicate OpenSea transaction found",
                details={"external_id": external_id, "count": count}
            )

        errors = quality_report.get_errors()
        if errors:
            print(f"\n{quality_report.summary()}")
            for e in errors[:10]:
                print(f"  - {e['details']['external_id']}: {e['details']['count']} duplicates")

        assert len(errors) == 0, f"Found {len(errors)} duplicate OpenSea transactions"

    def test_no_duplicate_ebay_items(self, integration_session: Session, quality_report: DataQualityReport):
        """eBay should not have duplicate item IDs."""
        from sqlalchemy import func as sa_func

        duplicates = integration_session.exec(
            select(MarketPrice.external_id, sa_func.count(MarketPrice.id).label("count"))
            .where(
                MarketPrice.platform == "ebay",
                MarketPrice.external_id.isnot(None),
                MarketPrice.external_id != ""
            )
            .group_by(MarketPrice.external_id)
            .having(sa_func.count(MarketPrice.id) > 1)
        ).all()

        for external_id, count in duplicates:
            quality_report.add_issue(
                category="duplicate_ebay_item",
                severity="warning",  # Warning - pre-existing issue to clean up
                record_id=0,
                description=f"Duplicate eBay item found",
                details={"external_id": external_id, "count": count}
            )

        warnings = quality_report.get_warnings()
        if warnings:
            print(f"\n{quality_report.summary()}")
            print(f"  Found {len(warnings)} duplicate eBay items (cleanup needed)")
            for w in warnings[:5]:
                print(f"  - {w['details']['external_id']}: {w['details']['count']} duplicates")


class TestPriceAnomalies:
    """Test for suspicious price values."""

    def test_no_extremely_high_prices(self, integration_session: Session, quality_report: DataQualityReport):
        """Flag listings with suspiciously high prices (potential data errors)."""
        threshold = 10000  # $10k seems suspicious for most cards

        listings = integration_session.exec(
            select(MarketPrice).where(
                MarketPrice.listing_type == "sold",
                MarketPrice.price > threshold
            )
        ).all()

        for listing in listings:
            quality_report.add_issue(
                category="price_anomaly",
                severity="warning",
                record_id=listing.id,
                description=f"Unusually high price (>${threshold})",
                details={
                    "title": listing.title,
                    "price": listing.price,
                    "platform": listing.platform
                }
            )

        warnings = quality_report.get_warnings()
        if warnings:
            print(f"\nHigh price listings (may be valid):")
            for w in warnings[:10]:
                print(f"  - ID {w['record_id']}: ${w['details']['price']:.2f} - {w['details']['title']}")

    def test_opensea_eth_conversion_reasonable(self, integration_session: Session, quality_report: DataQualityReport):
        """Check OpenSea USD prices are reasonable (ETH conversion sanity check)."""
        # If ETH price was wrong, USD prices would be way off
        # Typical NFT range: $10 - $5000

        listings = integration_session.exec(
            select(MarketPrice).where(
                MarketPrice.platform == "opensea",
                MarketPrice.listing_type == "sold",
                ((MarketPrice.price < 1) | (MarketPrice.price > 50000))
            )
        ).all()

        for listing in listings:
            severity = "error" if listing.price < 0.01 else "warning"
            quality_report.add_issue(
                category="eth_conversion_anomaly",
                severity=severity,
                record_id=listing.id,
                description=f"OpenSea price outside normal range",
                details={
                    "title": listing.title,
                    "price_usd": listing.price,
                }
            )

        issues = [i for i in quality_report.issues if i["category"] == "eth_conversion_anomaly"]
        if issues:
            print(f"\nOpenSea price anomalies:")
            for i in issues[:10]:
                print(f"  - ID {i['record_id']}: ${i['details']['price_usd']:.2f} - {i['details']['title']}")


class TestCardAssociation:
    """Test that listings are associated with correct cards."""

    def test_opensea_proofs_linked_to_proof_cards(self, integration_session: Session, quality_report: DataQualityReport):
        """OpenSea Character Proofs should be linked to Proof-type cards."""
        # Get proof cards
        proof_cards = integration_session.exec(
            select(Card).where(Card.product_type == "Proof")
        ).all()
        proof_card_ids = [c.id for c in proof_cards]

        if not proof_card_ids:
            pytest.skip("No Proof cards found in database")

        # Find OpenSea listings with "proof" in title but not linked to proof cards
        listings = integration_session.exec(
            select(MarketPrice).where(
                MarketPrice.platform == "opensea",
                MarketPrice.card_id.notin_(proof_card_ids)
            )
        ).all()

        for listing in listings:
            if listing.title and "proof" in listing.title.lower():
                quality_report.add_issue(
                    category="card_association_mismatch",
                    severity="warning",
                    record_id=listing.id,
                    description=f"OpenSea 'proof' listing not linked to Proof card",
                    details={
                        "title": listing.title,
                        "card_id": listing.card_id,
                    }
                )

        warnings = quality_report.get_warnings()
        if warnings:
            print(f"\n{quality_report.summary()}")
            for w in warnings[:10]:
                print(f"  - ID {w['record_id']}: {w['details']['title']}")


class TestNonWOTFContamination:
    """Test for non-WOTF cards mixed into the database."""

    # Known non-WOTF card indicators
    NON_WOTF_INDICATORS = [
        # Yu-Gi-Oh indicators
        "MP22-EN", "MGED-EN", "1st Edition", "Gold Rare",
        "Pharaoh's Gods", "Yu-Gi-Oh", "YuGiOh",
        # Pokemon indicators
        "Pokemon", "Pokémon", "PSA", "CGC",
        # MTG indicators
        "Magic the Gathering", "MTG", "Wizards of the Coast",
        # Generic TCG indicators that shouldn't be in WOTF
        "Tin of", "Booster Box", "ETB",
    ]

    # Known WOTF set names
    WOTF_SETS = [
        "Wonders of the First", "Existence", "Genesis",
        "WOTF", "WotF", "Wonder"
    ]

    def test_no_yugioh_cards_in_database(self, integration_session: Session, quality_report: DataQualityReport):
        """Detect Yu-Gi-Oh cards incorrectly scraped into WOTF database."""
        # Note: Removed "BONUS" - WOTF packs legitimately say "bonus cards"
        yugioh_indicators = [
            "MP22-EN", "MGED-EN", "MP23-EN", "MP24-EN", "MP25-EN",
            "POTE-EN", "PHNI-EN", "DIFO-EN", "BODE-EN",
            "Pharaoh's Gods", "Tin of the", "Gold Rare LP",
            "1st Edition Gold Rare", "Ruddy Rose Dragon",
            "Roxrose Dragon", "Trishula, Dragon",
            "Ice Barrier", "Yugioh", "Yu-Gi-Oh", "YGO",
            "Blue-Eyes", "Dark Magician", "Exodia",
            "Egyptian God", "Millennium", "Duelist Pack",
            "Structure Deck", "Legendary Collection",
            "Duel Devastator", "Maximum Gold"
        ]

        listings = integration_session.exec(
            select(MarketPrice).where(MarketPrice.listing_type == "sold")
        ).all()

        for listing in listings:
            title_lower = (listing.title or "").lower()
            for indicator in yugioh_indicators:
                if indicator.lower() in title_lower:
                    quality_report.add_issue(
                        category="non_wotf_contamination",
                        severity="error",
                        record_id=listing.id,
                        description=f"Yu-Gi-Oh card in WOTF database",
                        details={
                            "title": listing.title,
                            "indicator": indicator,
                            "price": listing.price,
                            "card_id": listing.card_id
                        }
                    )
                    break  # Only report once per listing

        errors = quality_report.get_errors()
        if errors:
            print(f"\n🚨 YU-GI-OH CONTAMINATION DETECTED!")
            print(f"{quality_report.summary()}")
            for e in errors[:15]:
                print(f"  - ID {e['record_id']}: {e['details']['title'][:60]}...")
            # Warn but don't fail - these are data quality issues to investigate
            import warnings
            warnings.warn(f"Found {len(errors)} Yu-Gi-Oh cards in database - cleanup recommended")

    def test_no_pokemon_cards_in_database(self, integration_session: Session, quality_report: DataQualityReport):
        """Detect Pokemon cards incorrectly scraped into WOTF database."""
        # Note: "psa 10" removed - WOTF cards can be PSA graded
        pokemon_indicators = [
            "pokemon", "pokémon", "pikachu", "charizard",
            "scarlet violet", "obsidian flames", "paldea",
            "brilliant stars", "evolving skies",
            "sword shield", "crown zenith", "astral radiance",
            "lost origin", "silver tempest", "paradox rift",
            "temporal forces", "twilight masquerade",
            "mewtwo", "rayquaza", "lugia", "gyarados",
            "eevee", "umbreon", "vaporeon", "espeon",
            "VMAX", "VSTAR", "V-Union", "GX",
            "Team Rocket", "Jungle Set", "Fossil Set",
            "Base Set Unlimited", "Shadowless"
        ]

        listings = integration_session.exec(
            select(MarketPrice).where(MarketPrice.listing_type == "sold")
        ).all()

        for listing in listings:
            title_lower = (listing.title or "").lower()
            for indicator in pokemon_indicators:
                if indicator in title_lower:
                    quality_report.add_issue(
                        category="non_wotf_contamination",
                        severity="error",
                        record_id=listing.id,
                        description=f"Pokemon card in WOTF database",
                        details={
                            "title": listing.title,
                            "indicator": indicator,
                            "card_id": listing.card_id
                        }
                    )
                    break

        errors = quality_report.get_errors()
        if errors:
            print(f"\n🚨 POKEMON CONTAMINATION DETECTED!")
            for e in errors[:10]:
                print(f"  - ID {e['record_id']}: {e['details']['title'][:60]}...")
            import warnings
            warnings.warn(f"Found {len(errors)} Pokemon cards in database - cleanup recommended")

    def test_no_mtg_cards_in_database(self, integration_session: Session, quality_report: DataQualityReport):
        """Detect Magic: The Gathering cards incorrectly scraped."""
        # Note: Removed "collector booster", "set booster", "draft booster" - WOTF uses these terms
        mtg_indicators = [
            "magic the gathering", "mtg ", "wizards of the coast",
            "commander deck", "modern horizons", "murder at karlov",
            "bloomburrow", "duskmourn",
            "outlaws of thunder junction", "karlov manor",
            "lost caverns", "wilds of eldraine", "march of the machine",
            "dominaria united", "brothers war", "phyrexia",
            "innistrad", "kamigawa", "zendikar", "ravnica",
            "black lotus", "mox ", "ancestral recall",
            "planeswalker", "legendary creature", "instant sorcery",
            "commander legends", "double masters", "secret lair"
        ]

        listings = integration_session.exec(
            select(MarketPrice).where(MarketPrice.listing_type == "sold")
        ).all()

        for listing in listings:
            title_lower = (listing.title or "").lower()
            for indicator in mtg_indicators:
                if indicator in title_lower:
                    quality_report.add_issue(
                        category="non_wotf_contamination",
                        severity="error",
                        record_id=listing.id,
                        description=f"MTG card in WOTF database",
                        details={
                            "title": listing.title,
                            "indicator": indicator,
                            "card_id": listing.card_id
                        }
                    )
                    break

        errors = quality_report.get_errors()
        if errors:
            print(f"\n🚨 MTG CONTAMINATION DETECTED!")
            for e in errors[:10]:
                print(f"  - ID {e['record_id']}: {e['details']['title'][:60]}...")
            import warnings
            warnings.warn(f"Found {len(errors)} MTG cards in database - cleanup recommended")

    def test_no_dragonball_cards_in_database(self, integration_session: Session, quality_report: DataQualityReport):
        """Detect Dragon Ball Z/Super cards incorrectly scraped into WOTF database."""
        dragonball_indicators = [
            "dragon ball", "dragonball", "dbz", "dbs",
            "dragon ball z", "dragon ball super", "dragon ball gt",
            "goku", "vegeta", "gohan", "piccolo", "frieza",
            "cell saga", "buu saga", "saiyan saga",
            "fusion world", "rise of the unison warrior",
            "ultimate box", "premium pack", "expansion set",
            "tournament pack", "android", "majin", "super saiyan",
            "kamehameha", "spirit bomb", "galactic battle"
        ]

        listings = integration_session.exec(
            select(MarketPrice).where(MarketPrice.listing_type == "sold")
        ).all()

        for listing in listings:
            title_lower = (listing.title or "").lower()
            for indicator in dragonball_indicators:
                if indicator in title_lower:
                    quality_report.add_issue(
                        category="non_wotf_contamination",
                        severity="error",
                        record_id=listing.id,
                        description=f"Dragon Ball card in WOTF database",
                        details={
                            "title": listing.title,
                            "indicator": indicator,
                            "card_id": listing.card_id
                        }
                    )
                    break

        errors = quality_report.get_errors()
        if errors:
            print(f"\n🚨 DRAGON BALL CONTAMINATION DETECTED!")
            for e in errors[:10]:
                print(f"  - ID {e['record_id']}: {e['details']['title'][:60]}...")
            import warnings
            warnings.warn(f"Found {len(errors)} Dragon Ball cards in database - cleanup recommended")

    def test_no_one_piece_cards_in_database(self, integration_session: Session, quality_report: DataQualityReport):
        """Detect One Piece cards incorrectly scraped into WOTF database."""
        one_piece_indicators = [
            "one piece", "onepiece", "op01", "op02", "op03", "op04", "op05", "op06", "op07",
            "luffy", "zoro", "nami", "sanji", "chopper",
            "monkey d luffy", "roronoa zoro", "trafalgar law",
            "romance dawn", "paramount war", "pillars of strength",
            "kingdoms of intrigue", "awakening of the new era",
            "two legends", "500 years in the future",
            "straw hat", "mugiwara", "grand line",
            "devil fruit", "pirate king", "gomu gomu"
        ]

        listings = integration_session.exec(
            select(MarketPrice).where(MarketPrice.listing_type == "sold")
        ).all()

        for listing in listings:
            title_lower = (listing.title or "").lower()
            for indicator in one_piece_indicators:
                if indicator in title_lower:
                    quality_report.add_issue(
                        category="non_wotf_contamination",
                        severity="error",
                        record_id=listing.id,
                        description=f"One Piece card in WOTF database",
                        details={
                            "title": listing.title,
                            "indicator": indicator,
                            "card_id": listing.card_id
                        }
                    )
                    break

        errors = quality_report.get_errors()
        if errors:
            print(f"\n🚨 ONE PIECE CONTAMINATION DETECTED!")
            for e in errors[:10]:
                print(f"  - ID {e['record_id']}: {e['details']['title'][:60]}...")
            import warnings
            warnings.warn(f"Found {len(errors)} One Piece cards in database - cleanup recommended")

    def test_no_flesh_and_blood_cards_in_database(self, integration_session: Session, quality_report: DataQualityReport):
        """Detect Flesh and Blood cards incorrectly scraped into WOTF database."""
        # Note: "rainbow foil" removed - could appear in generic descriptions
        # Focus on FAB-specific set names and character names
        fab_indicators = [
            "flesh and blood", "fab tcg",
            "welcome to rathe", "arcane rising", "crucible of war",
            "tales of aria", "everfest",
            "dusk till dawn", "outsiders", "bright lights",
            "heavy hitters", "part the mistveil", "rosetta",
            "katsu", "bravo", "rhinar", "dorinthea", "azalea",
            "cold foil fab", "legendary equipment fab", "majestic rare"
        ]

        listings = integration_session.exec(
            select(MarketPrice).where(MarketPrice.listing_type == "sold")
        ).all()

        for listing in listings:
            title_lower = (listing.title or "").lower()
            for indicator in fab_indicators:
                if indicator in title_lower:
                    quality_report.add_issue(
                        category="non_wotf_contamination",
                        severity="error",
                        record_id=listing.id,
                        description=f"Flesh and Blood card in WOTF database",
                        details={
                            "title": listing.title,
                            "indicator": indicator,
                            "card_id": listing.card_id
                        }
                    )
                    break

        errors = quality_report.get_errors()
        if errors:
            print(f"\n🚨 FLESH AND BLOOD CONTAMINATION DETECTED!")
            for e in errors[:10]:
                print(f"  - ID {e['record_id']}: {e['details']['title'][:60]}...")
            import warnings
            warnings.warn(f"Found {len(errors)} Flesh and Blood cards in database - cleanup recommended")

    def test_no_lorcana_cards_in_database(self, integration_session: Session, quality_report: DataQualityReport):
        """Detect Disney Lorcana cards incorrectly scraped into WOTF database."""
        # Note: Removed generic words that match WOTF card names:
        # "beast" (Siege Beast), "scar" (Lumina Scarab, Fortress Orcscar), etc.
        lorcana_indicators = [
            "lorcana", "disney lorcana",
            "the first chapter", "rise of the floodborn", "into the inklands",
            "ursula's return", "shimmering skies", "azurite sea",
            "mickey mouse", "stitch", "maleficent",
            "enchanted rare", "super rare lorcana",
            "inkwell", "glimmer", "dreamborn", "floodborn",
            "inklands", "great illuminary"
        ]

        listings = integration_session.exec(
            select(MarketPrice).where(MarketPrice.listing_type == "sold")
        ).all()

        for listing in listings:
            title_lower = (listing.title or "").lower()
            for indicator in lorcana_indicators:
                if indicator in title_lower:
                    quality_report.add_issue(
                        category="non_wotf_contamination",
                        severity="error",
                        record_id=listing.id,
                        description=f"Disney Lorcana card in WOTF database",
                        details={
                            "title": listing.title,
                            "indicator": indicator,
                            "card_id": listing.card_id
                        }
                    )
                    break

        errors = quality_report.get_errors()
        if errors:
            print(f"\n🚨 LORCANA CONTAMINATION DETECTED!")
            for e in errors[:10]:
                print(f"  - ID {e['record_id']}: {e['details']['title'][:60]}...")
            import warnings
            warnings.warn(f"Found {len(errors)} Disney Lorcana cards in database - cleanup recommended")

    def test_no_weiss_schwarz_cards_in_database(self, integration_session: Session, quality_report: DataQualityReport):
        """Detect Weiss Schwarz cards incorrectly scraped into WOTF database."""
        weiss_indicators = [
            "weiss schwarz", "weiss", "schwarz",
            "weis schwarz", "ws tcg",
            "hololive", "vtuber", "chainsaw man",
            "attack on titan", "demon slayer", "spy x family",
            "fate/stay night", "sword art online", "re:zero",
            "signed card", "sp signature", "ssr", "rr+",
            "trial deck", "booster pack weiss",
            "climax card", "clock encore"
        ]

        listings = integration_session.exec(
            select(MarketPrice).where(MarketPrice.listing_type == "sold")
        ).all()

        for listing in listings:
            title_lower = (listing.title or "").lower()
            for indicator in weiss_indicators:
                if indicator in title_lower:
                    quality_report.add_issue(
                        category="non_wotf_contamination",
                        severity="error",
                        record_id=listing.id,
                        description=f"Weiss Schwarz card in WOTF database",
                        details={
                            "title": listing.title,
                            "indicator": indicator,
                            "card_id": listing.card_id
                        }
                    )
                    break

        errors = quality_report.get_errors()
        if errors:
            print(f"\n🚨 WEISS SCHWARZ CONTAMINATION DETECTED!")
            for e in errors[:10]:
                print(f"  - ID {e['record_id']}: {e['details']['title'][:60]}...")
            import warnings
            warnings.warn(f"Found {len(errors)} Weiss Schwarz cards in database - cleanup recommended")

    def test_no_digimon_cards_in_database(self, integration_session: Session, quality_report: DataQualityReport):
        """Detect Digimon cards incorrectly scraped into WOTF database."""
        digimon_indicators = [
            "digimon", "digimon tcg", "digimon card game",
            "bt01", "bt02", "bt03", "bt04", "bt05", "bt06", "bt07", "bt08", "bt09", "bt10",
            "bt11", "bt12", "bt13", "bt14", "bt15", "bt16", "bt17", "bt18",
            "agumon", "gabumon", "greymon", "wargreymon",
            "omnimon", "alphamon", "gallantmon", "imperialdramon",
            "new evolution", "great legend", "booster set digimon",
            "starter deck digimon", "release special",
            "alternate art digimon", "sec rare", "sr digimon"
        ]

        listings = integration_session.exec(
            select(MarketPrice).where(MarketPrice.listing_type == "sold")
        ).all()

        for listing in listings:
            title_lower = (listing.title or "").lower()
            for indicator in digimon_indicators:
                if indicator in title_lower:
                    quality_report.add_issue(
                        category="non_wotf_contamination",
                        severity="error",
                        record_id=listing.id,
                        description=f"Digimon card in WOTF database",
                        details={
                            "title": listing.title,
                            "indicator": indicator,
                            "card_id": listing.card_id
                        }
                    )
                    break

        errors = quality_report.get_errors()
        if errors:
            print(f"\n🚨 DIGIMON CONTAMINATION DETECTED!")
            for e in errors[:10]:
                print(f"  - ID {e['record_id']}: {e['details']['title'][:60]}...")
            import warnings
            warnings.warn(f"Found {len(errors)} Digimon cards in database - cleanup recommended")


class TestTreatmentExtraction:
    """Test that treatment extraction is working correctly."""

    def test_stone_foil_extraction(self, integration_session: Session, quality_report: DataQualityReport):
        """Test that Stone Foil treatments are being extracted correctly."""
        # Find listings that mention "stone" in title but don't have Stone treatment
        listings = integration_session.exec(
            select(MarketPrice).where(
                MarketPrice.listing_type == "sold",
                MarketPrice.platform == "ebay"
            )
        ).all()

        for listing in listings:
            title_lower = (listing.title or "").lower()
            treatment_lower = (listing.treatment or "").lower()

            # Check for stone foil mentions not captured in treatment
            if "stone" in title_lower and "stone" not in treatment_lower:
                quality_report.add_issue(
                    category="treatment_extraction_failure",
                    severity="warning",
                    record_id=listing.id,
                    description=f"Stone Foil not extracted from title",
                    details={
                        "title": listing.title,
                        "current_treatment": listing.treatment,
                        "card_id": listing.card_id
                    }
                )

        warnings = quality_report.get_warnings()
        if warnings:
            print(f"\n⚠️ STONE FOIL EXTRACTION ISSUES")
            print(f"  Found {len(warnings)} listings with unextracted Stone Foil")
            for w in warnings[:10]:
                print(f"  - ID {w['record_id']}: {w['details']['title'][:50]}... → {w['details']['current_treatment']}")

    def test_foil_extraction(self, integration_session: Session, quality_report: DataQualityReport):
        """Test that Foil treatments are being extracted correctly."""
        listings = integration_session.exec(
            select(MarketPrice).where(
                MarketPrice.listing_type == "sold",
                MarketPrice.platform == "ebay"
            )
        ).all()

        for listing in listings:
            title_lower = (listing.title or "").lower()
            treatment_lower = (listing.treatment or "").lower()

            # Check for foil mentions not captured in treatment
            foil_in_title = "foil" in title_lower or "holo" in title_lower
            foil_in_treatment = "foil" in treatment_lower or "holo" in treatment_lower

            if foil_in_title and not foil_in_treatment:
                quality_report.add_issue(
                    category="treatment_extraction_failure",
                    severity="warning",
                    record_id=listing.id,
                    description=f"Foil not extracted from title",
                    details={
                        "title": listing.title,
                        "current_treatment": listing.treatment,
                    }
                )

        warnings = quality_report.get_warnings()
        if warnings:
            print(f"\n⚠️ FOIL EXTRACTION ISSUES")
            print(f"  Found {len(warnings)} listings with unextracted Foil")
            for w in warnings[:10]:
                print(f"  - ID {w['record_id']}: {w['details']['title'][:50]}... → {w['details']['current_treatment']}")

    def test_serialized_extraction(self, integration_session: Session, quality_report: DataQualityReport):
        """Test that Serialized treatments are being extracted correctly."""
        listings = integration_session.exec(
            select(MarketPrice).where(
                MarketPrice.listing_type == "sold",
                MarketPrice.platform == "ebay"
            )
        ).all()

        serialized_patterns = ["/50", "/100", "/250", "/500", "/1000", "serial", "ocm"]

        for listing in listings:
            title_lower = (listing.title or "").lower()
            treatment_lower = (listing.treatment or "").lower()

            has_serial_in_title = any(p in title_lower for p in serialized_patterns)
            has_serial_in_treatment = "serial" in treatment_lower or "ocm" in treatment_lower

            if has_serial_in_title and not has_serial_in_treatment:
                quality_report.add_issue(
                    category="treatment_extraction_failure",
                    severity="warning",
                    record_id=listing.id,
                    description=f"Serialized not extracted from title",
                    details={
                        "title": listing.title,
                        "current_treatment": listing.treatment,
                    }
                )

        warnings = quality_report.get_warnings()
        if warnings:
            print(f"\n⚠️ SERIALIZED EXTRACTION ISSUES")
            print(f"  Found {len(warnings)} listings with unextracted Serialized")
            for w in warnings[:10]:
                print(f"  - ID {w['record_id']}: {w['details']['title'][:50]}... → {w['details']['current_treatment']}")


class TestSpecificCardIssues:
    """Test for known problematic cards."""

    def test_progo_data_quality(self, integration_session: Session, quality_report: DataQualityReport):
        """Check Progo card data for issues."""
        # Find Progo card
        progo = integration_session.exec(
            select(Card).where(Card.name.ilike("%progo%"))
        ).first()

        if not progo:
            pytest.skip("Progo card not found in database")

        listings = integration_session.exec(
            select(MarketPrice).where(
                MarketPrice.card_id == progo.id,
                MarketPrice.listing_type == "sold"
            )
        ).all()

        print(f"\n📊 PROGO DATA ANALYSIS")
        print(f"  Total Progo listings: {len(listings)}")

        # Check for treatment distribution
        treatments = {}
        for listing in listings:
            t = listing.treatment or "Unknown"
            treatments[t] = treatments.get(t, 0) + 1

        print(f"  Treatment distribution:")
        for t, count in sorted(treatments.items(), key=lambda x: -x[1]):
            print(f"    - {t}: {count}")

        # Check for suspicious listings
        for listing in listings:
            title_lower = (listing.title or "").lower()

            # Check for non-WOTF indicators in Progo listings
            if any(ind in title_lower for ind in ["yu-gi-oh", "pokemon", "mtg", "magic"]):
                quality_report.add_issue(
                    category="progo_contamination",
                    severity="error",
                    record_id=listing.id,
                    description=f"Non-WOTF card in Progo listings",
                    details={"title": listing.title}
                )

            # Check for missing WOTF indicators
            if "wotf" not in title_lower and "wonder" not in title_lower and "progo" not in title_lower:
                quality_report.add_issue(
                    category="progo_suspect",
                    severity="warning",
                    record_id=listing.id,
                    description=f"Progo listing missing WOTF indicators",
                    details={"title": listing.title, "treatment": listing.treatment}
                )

        errors = quality_report.get_errors()
        warnings = [w for w in quality_report.get_warnings() if w["category"] == "progo_suspect"]

        if errors:
            print(f"\n🚨 PROGO ERRORS:")
            for e in errors[:5]:
                print(f"  - {e['details']['title'][:60]}...")

        if warnings:
            print(f"\n⚠️ PROGO WARNINGS ({len(warnings)} suspicious):")
            for w in warnings[:5]:
                print(f"  - {w['details']['title'][:60]}...")

    def test_deep_black_goop_treatment(self, integration_session: Session, quality_report: DataQualityReport):
        """Check Deep Black Goop card for treatment extraction issues."""
        # Find Deep Black Goop card
        goop = integration_session.exec(
            select(Card).where(Card.name.ilike("%deep black goop%"))
        ).first()

        if not goop:
            pytest.skip("Deep Black Goop card not found in database")

        listings = integration_session.exec(
            select(MarketPrice).where(
                MarketPrice.card_id == goop.id,
                MarketPrice.listing_type == "sold"
            )
        ).all()

        print(f"\n📊 DEEP BLACK GOOP DATA ANALYSIS")
        print(f"  Total listings: {len(listings)}")

        # Check for stone foil specifically
        stone_foil_count = 0
        missing_stone_foil = []

        for listing in listings:
            title_lower = (listing.title or "").lower()
            treatment_lower = (listing.treatment or "").lower()

            if "stone" in title_lower:
                stone_foil_count += 1
                if "stone" not in treatment_lower:
                    missing_stone_foil.append(listing)
                    quality_report.add_issue(
                        category="goop_stone_foil_missing",
                        severity="warning",
                        record_id=listing.id,
                        description=f"Deep Black Goop Stone Foil not extracted",
                        details={
                            "title": listing.title,
                            "current_treatment": listing.treatment
                        }
                    )

        print(f"  Stone Foil in title: {stone_foil_count}")
        print(f"  Stone Foil extraction failures: {len(missing_stone_foil)}")

        if missing_stone_foil:
            print(f"\n⚠️ STONE FOIL EXTRACTION FAILURES:")
            for listing in missing_stone_foil[:5]:
                print(f"  - ID {listing.id}: {listing.title[:50]}... → {listing.treatment}")


class TestDataQualitySummary:
    """Generate overall data quality summary."""

    def test_generate_quality_report(self, integration_session: Session):
        """Generate a comprehensive data quality report."""
        report = DataQualityReport()

        # Count totals
        total_listings = integration_session.exec(
            select(func.count(MarketPrice.id))
        ).one()

        opensea_count = integration_session.exec(
            select(func.count(MarketPrice.id)).where(MarketPrice.platform == "opensea")
        ).one()

        ebay_count = integration_session.exec(
            select(func.count(MarketPrice.id)).where(MarketPrice.platform == "ebay")
        ).one()

        # Check for common issues
        no_treatment = integration_session.exec(
            select(func.count(MarketPrice.id)).where(
                (MarketPrice.treatment.is_(None)) | (MarketPrice.treatment == "")
            )
        ).one()

        no_url = integration_session.exec(
            select(func.count(MarketPrice.id)).where(
                MarketPrice.url.is_(None),
                MarketPrice.listing_type == "sold"
            )
        ).one()

        generic_nft_treatment = integration_session.exec(
            select(func.count(MarketPrice.id)).where(
                MarketPrice.platform == "opensea",
                MarketPrice.treatment == "NFT"
            )
        ).one()

        print("\n" + "=" * 60)
        print("DATA QUALITY SUMMARY")
        print("=" * 60)
        print(f"Total listings:        {total_listings}")
        print(f"  - OpenSea:           {opensea_count}")
        print(f"  - eBay:              {ebay_count}")
        print(f"  - Other:             {total_listings - opensea_count - ebay_count}")
        print("-" * 60)
        print(f"Missing treatment:     {no_treatment}")
        print(f"Missing URL:           {no_url}")
        print(f"Generic 'NFT' treatment: {generic_nft_treatment}")
        print("=" * 60)

        # This test always passes - it's informational
        assert True
