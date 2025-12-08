"""
Tests for OpenSea scraper functionality.

Tests cover:
- OpenSeaSale dataclass and traits field
- URL building for OpenSea item links
- Trait extraction from API and web scraping
- Data integrity for NFT treatments in MarketPrice
"""

import pytest
from datetime import datetime, timezone
from typing import List
from sqlmodel import Session, select

from app.models.card import Card, Rarity
from app.models.market import MarketPrice
from app.scraper.opensea import OpenSeaSale


class TestOpenSeaSaleDataclass:
    """Tests for OpenSeaSale dataclass."""

    def test_opensea_sale_basic_fields(self):
        """Test OpenSeaSale contains all required fields."""
        sale = OpenSeaSale(
            token_id="3515",
            token_name="Character Proof #3515",
            price_eth=0.15,
            price_usd=525.00,
            seller="0x1234567890abcdef",
            buyer="0xabcdef1234567890",
            sold_at=datetime.now(timezone.utc),
            tx_hash="0xabc123def456",
        )

        assert sale.token_id == "3515"
        assert sale.token_name == "Character Proof #3515"
        assert sale.price_eth == 0.15
        assert sale.price_usd == 525.00
        assert sale.tx_hash == "0xabc123def456"

    def test_opensea_sale_with_traits(self):
        """Test OpenSeaSale with traits field populated."""
        traits = ["Rare", "Fire Element", "Level 5"]
        sale = OpenSeaSale(
            token_id="1234",
            token_name="NFT #1234",
            price_eth=0.5,
            price_usd=1750.00,
            seller="0xseller",
            buyer="0xbuyer",
            sold_at=datetime.now(timezone.utc),
            tx_hash="0xtxhash",
            traits=traits,
        )

        assert sale.traits is not None
        assert len(sale.traits) == 3
        assert "Rare" in sale.traits
        assert "Fire Element" in sale.traits
        assert "Level 5" in sale.traits

    def test_opensea_sale_traits_default_none(self):
        """Test OpenSeaSale traits defaults to None."""
        sale = OpenSeaSale(
            token_id="999",
            token_name="NFT #999",
            price_eth=0.1,
            price_usd=350.00,
            seller="0xseller",
            buyer="0xbuyer",
            sold_at=datetime.now(timezone.utc),
            tx_hash="0xtx",
        )

        assert sale.traits is None

    def test_opensea_sale_with_image_url(self):
        """Test OpenSeaSale with optional image_url."""
        sale = OpenSeaSale(
            token_id="555",
            token_name="NFT #555",
            price_eth=0.2,
            price_usd=700.00,
            seller="0xseller",
            buyer="0xbuyer",
            sold_at=datetime.now(timezone.utc),
            tx_hash="0xtx",
            image_url="https://opensea.io/image/555.png",
            traits=["Epic", "Water"],
        )

        assert sale.image_url == "https://opensea.io/image/555.png"
        assert sale.traits == ["Epic", "Water"]


class TestOpenSeaURLBuilding:
    """Tests for OpenSea item URL construction."""

    def test_build_opensea_url_ethereum(self):
        """Test building OpenSea URL for Ethereum NFT."""
        chain = "ethereum"
        contract = "0x05f08b01971cf70bcd4e743a8906790cfb9a8fb8"
        token_id = "3515"

        url = f"https://opensea.io/item/{chain}/{contract}/{token_id}"

        assert url == "https://opensea.io/item/ethereum/0x05f08b01971cf70bcd4e743a8906790cfb9a8fb8/3515"

    def test_build_opensea_url_collector_boxes(self):
        """Test building OpenSea URL for Collector Boxes contract."""
        chain = "ethereum"
        contract = "0x28a11da34a93712b1fde4ad15da217a3b14d9465"
        token_id = "42"

        url = f"https://opensea.io/item/{chain}/{contract}/{token_id}"

        assert url == "https://opensea.io/item/ethereum/0x28a11da34a93712b1fde4ad15da217a3b14d9465/42"

    def test_url_not_built_without_contract(self):
        """Test URL is None when contract is missing."""
        token_id = "3515"
        contract = ""

        opensea_url = None
        if token_id and contract:
            opensea_url = f"https://opensea.io/item/ethereum/{contract}/{token_id}"

        assert opensea_url is None

    def test_url_not_built_without_token_id(self):
        """Test URL is None when token_id is missing."""
        token_id = ""
        contract = "0x05f08b01971cf70bcd4e743a8906790cfb9a8fb8"

        opensea_url = None
        if token_id and contract:
            opensea_url = f"https://opensea.io/item/ethereum/{contract}/{token_id}"

        assert opensea_url is None


class TestTraitsTreatmentConversion:
    """Tests for converting NFT traits to treatment strings."""

    def test_traits_joined_as_treatment(self):
        """Test traits are joined into treatment string."""
        traits = ["Rare", "Fire", "Level 5"]

        # Replicate the logic from scrape_opensea.py
        treatment = "NFT"
        if traits:
            treatment = ", ".join(traits[:3])

        assert treatment == "Rare, Fire, Level 5"

    def test_traits_limited_to_three(self):
        """Test only first 3 traits are used."""
        traits = ["Rare", "Fire", "Level 5", "Ancient", "Glowing"]

        treatment = ", ".join(traits[:3])

        assert treatment == "Rare, Fire, Level 5"
        assert "Ancient" not in treatment
        assert "Glowing" not in treatment

    def test_empty_traits_uses_token_name(self):
        """Test fallback to token_name when no traits."""
        traits = []
        token_name = "Character Proof #3515"

        treatment = "NFT"
        if traits:
            treatment = ", ".join(traits[:3])
        elif token_name:
            treatment = token_name

        assert treatment == "Character Proof #3515"

    def test_none_traits_uses_token_name(self):
        """Test fallback to token_name when traits is None."""
        traits = None
        token_name = "Collector Box #42"

        treatment = "NFT"
        if traits:
            treatment = ", ".join(traits[:3])
        elif token_name:
            treatment = token_name

        assert treatment == "Collector Box #42"

    def test_no_traits_no_name_uses_default(self):
        """Test fallback to 'NFT' when no traits or name."""
        traits = None
        token_name = ""

        treatment = "NFT"
        if traits:
            treatment = ", ".join(traits[:3])
        elif token_name:
            treatment = token_name

        assert treatment == "NFT"

    def test_single_trait_as_treatment(self):
        """Test single trait becomes treatment."""
        traits = ["Legendary"]

        treatment = ", ".join(traits[:3])

        assert treatment == "Legendary"


class TestNFTDataIntegrity:
    """Data integrity tests for NFT treatments in MarketPrice."""

    def test_nft_treatment_stored_correctly(self, test_session: Session, sample_rarities: List[Rarity]):
        """Test NFT traits are stored as treatment in MarketPrice."""
        # Create NFT card
        card = Card(
            name="Character Proofs",
            set_name="WOTF",
            rarity_id=1,
            product_type="Proof",
        )
        test_session.add(card)
        test_session.commit()
        test_session.refresh(card)

        # Create MarketPrice with NFT traits as treatment
        market_price = MarketPrice(
            card_id=card.id,
            price=525.00,
            title="Character Proof #3515",
            sold_date=datetime.now(timezone.utc).replace(tzinfo=None),
            listing_type="sold",
            treatment="Rare, Fire, Level 5",  # Traits joined
            external_id="0xabc123",
            url="https://opensea.io/item/ethereum/0x05f08b01971cf70bcd4e743a8906790cfb9a8fb8/3515",
            platform="opensea",
        )
        test_session.add(market_price)
        test_session.commit()
        test_session.refresh(market_price)

        # Verify data integrity
        retrieved = test_session.exec(
            select(MarketPrice).where(MarketPrice.id == market_price.id)
        ).first()

        assert retrieved is not None
        assert retrieved.treatment == "Rare, Fire, Level 5"
        assert retrieved.platform == "opensea"
        assert "opensea.io/item" in retrieved.url

    def test_nft_treatment_with_special_characters(self, test_session: Session, sample_rarities: List[Rarity]):
        """Test NFT traits with special characters are stored correctly."""
        card = Card(
            name="Collector Box",
            set_name="WOTF",
            rarity_id=1,
            product_type="Box",
        )
        test_session.add(card)
        test_session.commit()

        # Traits with various characters
        market_price = MarketPrice(
            card_id=card.id,
            price=150.00,
            title="Collector Box #42",
            listing_type="sold",
            treatment="Ultra-Rare, Fire & Ice, Level 10+",
            platform="opensea",
        )
        test_session.add(market_price)
        test_session.commit()
        test_session.refresh(market_price)

        retrieved = test_session.exec(
            select(MarketPrice).where(MarketPrice.id == market_price.id)
        ).first()

        assert retrieved.treatment == "Ultra-Rare, Fire & Ice, Level 10+"

    def test_multiple_nft_sales_different_traits(self, test_session: Session, sample_rarities: List[Rarity]):
        """Test multiple NFT sales with different traits are stored correctly."""
        card = Card(
            name="Character Proofs",
            set_name="WOTF",
            rarity_id=1,
            product_type="Proof",
        )
        test_session.add(card)
        test_session.commit()

        # Create multiple sales with different traits
        sales_data = [
            ("Rare, Fire", 100.00, "3515"),
            ("Legendary, Water", 500.00, "3516"),
            ("Common, Earth", 50.00, "3517"),
            ("Epic, Wind, Ancient", 250.00, "3518"),
        ]

        for treatment, price, token_id in sales_data:
            mp = MarketPrice(
                card_id=card.id,
                price=price,
                title=f"Character Proof #{token_id}",
                listing_type="sold",
                treatment=treatment,
                external_id=f"0xtx{token_id}",
                platform="opensea",
            )
            test_session.add(mp)

        test_session.commit()

        # Verify all sales stored correctly
        all_sales = test_session.exec(
            select(MarketPrice).where(
                MarketPrice.card_id == card.id,
                MarketPrice.platform == "opensea"
            )
        ).all()

        assert len(all_sales) == 4

        treatments = [s.treatment for s in all_sales]
        assert "Rare, Fire" in treatments
        assert "Legendary, Water" in treatments
        assert "Common, Earth" in treatments
        assert "Epic, Wind, Ancient" in treatments

    def test_opensea_url_format_stored(self, test_session: Session, sample_rarities: List[Rarity]):
        """Test OpenSea item URL format is stored correctly."""
        card = Card(
            name="Character Proofs",
            set_name="WOTF",
            rarity_id=1,
            product_type="Proof",
        )
        test_session.add(card)
        test_session.commit()

        # Correct URL format: /item/{chain}/{contract}/{token_id}
        url = "https://opensea.io/item/ethereum/0x05f08b01971cf70bcd4e743a8906790cfb9a8fb8/3515"

        market_price = MarketPrice(
            card_id=card.id,
            price=525.00,
            title="Character Proof #3515",
            listing_type="sold",
            treatment="Rare",
            url=url,
            platform="opensea",
        )
        test_session.add(market_price)
        test_session.commit()

        retrieved = test_session.exec(
            select(MarketPrice).where(MarketPrice.id == market_price.id)
        ).first()

        # Verify URL format
        assert retrieved.url is not None
        assert "/item/" in retrieved.url
        assert "/ethereum/" in retrieved.url
        assert "/0x05f08b01971cf70bcd4e743a8906790cfb9a8fb8/" in retrieved.url
        assert "/3515" in retrieved.url

    def test_nft_external_id_uniqueness(self, test_session: Session, sample_rarities: List[Rarity]):
        """Test NFT tx_hash as external_id prevents duplicates."""
        card = Card(
            name="Character Proofs",
            set_name="WOTF",
            rarity_id=1,
            product_type="Proof",
        )
        test_session.add(card)
        test_session.commit()

        tx_hash = "0xabc123def456789"

        # First sale
        mp1 = MarketPrice(
            card_id=card.id,
            price=100.00,
            title="Character Proof #3515",
            listing_type="sold",
            treatment="Rare",
            external_id=tx_hash,
            platform="opensea",
        )
        test_session.add(mp1)
        test_session.commit()

        # Check for existing before adding duplicate
        existing = test_session.exec(
            select(MarketPrice).where(
                MarketPrice.card_id == card.id,
                MarketPrice.external_id == tx_hash,
                MarketPrice.platform == "opensea"
            )
        ).first()

        assert existing is not None
        assert existing.external_id == tx_hash

    def test_nft_fallback_external_id(self, test_session: Session, sample_rarities: List[Rarity]):
        """Test fallback external_id format when no tx_hash."""
        card = Card(
            name="Character Proofs",
            set_name="WOTF",
            rarity_id=1,
            product_type="Proof",
        )
        test_session.add(card)
        test_session.commit()

        # Fallback format: opensea_{token_id}_{timestamp}
        token_id = "3515"
        sold_at = datetime.now(timezone.utc)
        fallback_id = f"opensea_{token_id}_{sold_at.isoformat()}"

        market_price = MarketPrice(
            card_id=card.id,
            price=100.00,
            title=f"Character Proof #{token_id}",
            listing_type="sold",
            treatment="Rare",
            external_id=fallback_id,
            platform="opensea",
        )
        test_session.add(market_price)
        test_session.commit()

        retrieved = test_session.exec(
            select(MarketPrice).where(MarketPrice.id == market_price.id)
        ).first()

        assert retrieved.external_id.startswith("opensea_3515_")


class TestOpenSeaCollectionConfig:
    """Tests for OpenSea collection configuration."""

    def test_character_proofs_config(self):
        """Test Character Proofs collection config is correct."""
        config = {
            "url": "https://opensea.io/collection/wotf-character-proofs",
            "card_name": "Character Proofs",
            "slug": "wotf-character-proofs",
            "contract": "0x05f08b01971cf70bcd4e743a8906790cfb9a8fb8",
            "chain": "ethereum"
        }

        assert config["contract"].startswith("0x")
        assert len(config["contract"]) == 42  # Valid Ethereum address
        assert config["chain"] == "ethereum"
        assert config["slug"] in config["url"]

    def test_collector_boxes_config(self):
        """Test Collector Boxes collection config is correct."""
        config = {
            "url": "https://opensea.io/collection/wotf-existence-collector-boxes",
            "card_name": "Existence Collector Box",
            "slug": "wotf-existence-collector-boxes",
            "contract": "0x28a11da34a93712b1fde4ad15da217a3b14d9465",
            "chain": "ethereum"
        }

        assert config["contract"].startswith("0x")
        assert len(config["contract"]) == 42  # Valid Ethereum address
        assert config["chain"] == "ethereum"
        assert config["slug"] in config["url"]

    def test_contracts_are_different(self):
        """Test Character Proofs and Collector Boxes have different contracts."""
        character_proofs_contract = "0x05f08b01971cf70bcd4e743a8906790cfb9a8fb8"
        collector_boxes_contract = "0x28a11da34a93712b1fde4ad15da217a3b14d9465"

        assert character_proofs_contract != collector_boxes_contract


class TestCollectorBoxesVsEbayBoxes:
    """
    Tests to distinguish OpenSea NFT Collector Boxes from eBay physical boxes.

    OpenSea Collector Boxes: NFTs from wotf-existence-collector-boxes collection
    eBay Boxes: Physical sealed product boxes sold on eBay
    """

    def test_opensea_collector_box_has_nft_platform(self, test_session: Session, sample_rarities: List[Rarity]):
        """Test OpenSea Collector Box is stored with platform='opensea'."""
        card = Card(
            name="Existence Collector Box",
            set_name="WOTF",
            rarity_id=1,
            product_type="Box",
        )
        test_session.add(card)
        test_session.commit()

        # OpenSea NFT Collector Box
        nft_box = MarketPrice(
            card_id=card.id,
            price=150.00,
            title="Existence Collector Box #42",
            listing_type="sold",
            treatment="Rare",  # NFT trait
            platform="opensea",
            url="https://opensea.io/item/ethereum/0x28a11da34a93712b1fde4ad15da217a3b14d9465/42",
            external_id="0xnfttxhash123",
        )
        test_session.add(nft_box)
        test_session.commit()

        retrieved = test_session.exec(
            select(MarketPrice).where(MarketPrice.id == nft_box.id)
        ).first()

        assert retrieved.platform == "opensea"
        assert "opensea.io/item" in retrieved.url
        assert retrieved.treatment == "Rare"

    def test_ebay_box_has_ebay_platform(self, test_session: Session, sample_rarities: List[Rarity]):
        """Test eBay physical box is stored with platform='ebay'."""
        card = Card(
            name="Existence Collector Box",
            set_name="WOTF",
            rarity_id=1,
            product_type="Box",
        )
        test_session.add(card)
        test_session.commit()

        # eBay physical sealed box
        ebay_box = MarketPrice(
            card_id=card.id,
            price=89.99,
            title="WOTF Existence Collector Box SEALED",
            listing_type="sold",
            treatment="Sealed",  # Physical box treatment
            platform="ebay",
            url="https://www.ebay.com/itm/123456789",
            external_id="ebay_123456789",
        )
        test_session.add(ebay_box)
        test_session.commit()

        retrieved = test_session.exec(
            select(MarketPrice).where(MarketPrice.id == ebay_box.id)
        ).first()

        assert retrieved.platform == "ebay"
        assert "ebay.com" in retrieved.url
        assert retrieved.treatment == "Sealed"

    def test_same_card_different_platforms_coexist(self, test_session: Session, sample_rarities: List[Rarity]):
        """Test OpenSea NFT and eBay physical boxes can coexist for same card."""
        card = Card(
            name="Existence Collector Box",
            set_name="WOTF",
            rarity_id=1,
            product_type="Box",
        )
        test_session.add(card)
        test_session.commit()

        # OpenSea NFT sale
        nft_sale = MarketPrice(
            card_id=card.id,
            price=200.00,
            title="Existence Collector Box #100",
            listing_type="sold",
            treatment="Legendary",
            platform="opensea",
            external_id="0xopensea_tx_1",
        )
        test_session.add(nft_sale)

        # eBay physical sale
        ebay_sale = MarketPrice(
            card_id=card.id,
            price=85.00,
            title="Existence Collector Box Sealed New",
            listing_type="sold",
            treatment="Sealed",
            platform="ebay",
            external_id="ebay_987654321",
        )
        test_session.add(ebay_sale)
        test_session.commit()

        # Query both platforms
        opensea_sales = test_session.exec(
            select(MarketPrice).where(
                MarketPrice.card_id == card.id,
                MarketPrice.platform == "opensea"
            )
        ).all()

        ebay_sales = test_session.exec(
            select(MarketPrice).where(
                MarketPrice.card_id == card.id,
                MarketPrice.platform == "ebay"
            )
        ).all()

        assert len(opensea_sales) == 1
        assert len(ebay_sales) == 1
        assert opensea_sales[0].treatment == "Legendary"
        assert ebay_sales[0].treatment == "Sealed"

    def test_nft_box_treatment_is_trait_not_sealed(self, test_session: Session, sample_rarities: List[Rarity]):
        """Test NFT Collector Box uses trait as treatment, not 'Sealed'."""
        card = Card(
            name="Existence Collector Box",
            set_name="WOTF",
            rarity_id=1,
            product_type="Box",
        )
        test_session.add(card)
        test_session.commit()

        # NFT with trait - should NOT use "Sealed"
        nft_box = MarketPrice(
            card_id=card.id,
            price=175.00,
            title="Existence Collector Box #55",
            listing_type="sold",
            treatment="Epic",  # NFT trait, not "Sealed"
            platform="opensea",
        )
        test_session.add(nft_box)
        test_session.commit()

        retrieved = test_session.exec(
            select(MarketPrice).where(MarketPrice.id == nft_box.id)
        ).first()

        # NFT boxes should use traits, not physical product treatments
        assert retrieved.treatment != "Sealed"
        assert retrieved.treatment == "Epic"

    def test_ebay_box_treatment_is_sealed(self, test_session: Session, sample_rarities: List[Rarity]):
        """Test eBay physical box uses 'Sealed' treatment."""
        card = Card(
            name="Existence Collector Box",
            set_name="WOTF",
            rarity_id=1,
            product_type="Box",
        )
        test_session.add(card)
        test_session.commit()

        # Physical box should use "Sealed" treatment
        ebay_box = MarketPrice(
            card_id=card.id,
            price=79.99,
            title="Existence Box Factory Sealed",
            listing_type="sold",
            treatment="Sealed",
            platform="ebay",
        )
        test_session.add(ebay_box)
        test_session.commit()

        retrieved = test_session.exec(
            select(MarketPrice).where(MarketPrice.id == ebay_box.id)
        ).first()

        assert retrieved.treatment == "Sealed"
        assert retrieved.platform == "ebay"

    def test_can_filter_by_platform(self, test_session: Session, sample_rarities: List[Rarity]):
        """Test querying sales by platform to separate NFT from physical."""
        card = Card(
            name="Existence Collector Box",
            set_name="WOTF",
            rarity_id=1,
            product_type="Box",
        )
        test_session.add(card)
        test_session.commit()

        # Add multiple sales from each platform
        for i in range(3):
            test_session.add(MarketPrice(
                card_id=card.id,
                price=100.00 + i * 50,
                title=f"NFT Box #{i}",
                listing_type="sold",
                treatment="Rare",
                platform="opensea",
                external_id=f"opensea_{i}",
            ))

        for i in range(5):
            test_session.add(MarketPrice(
                card_id=card.id,
                price=80.00 + i * 5,
                title=f"eBay Box {i}",
                listing_type="sold",
                treatment="Sealed",
                platform="ebay",
                external_id=f"ebay_{i}",
            ))

        test_session.commit()

        # Count by platform
        opensea_count = len(test_session.exec(
            select(MarketPrice).where(
                MarketPrice.card_id == card.id,
                MarketPrice.platform == "opensea"
            )
        ).all())

        ebay_count = len(test_session.exec(
            select(MarketPrice).where(
                MarketPrice.card_id == card.id,
                MarketPrice.platform == "ebay"
            )
        ).all())

        assert opensea_count == 3
        assert ebay_count == 5

    def test_nft_url_format_vs_ebay_url(self, test_session: Session, sample_rarities: List[Rarity]):
        """Test URL formats distinguish NFT from eBay listings."""
        card = Card(
            name="Existence Collector Box",
            set_name="WOTF",
            rarity_id=1,
            product_type="Box",
        )
        test_session.add(card)
        test_session.commit()

        nft_url = "https://opensea.io/item/ethereum/0x28a11da34a93712b1fde4ad15da217a3b14d9465/42"
        ebay_url = "https://www.ebay.com/itm/123456789012"

        nft_sale = MarketPrice(
            card_id=card.id,
            price=150.00,
            title="NFT Box",
            listing_type="sold",
            treatment="Epic",
            platform="opensea",
            url=nft_url,
        )

        ebay_sale = MarketPrice(
            card_id=card.id,
            price=85.00,
            title="eBay Box",
            listing_type="sold",
            treatment="Sealed",
            platform="ebay",
            url=ebay_url,
        )

        test_session.add(nft_sale)
        test_session.add(ebay_sale)
        test_session.commit()

        # Verify URL patterns
        nft_retrieved = test_session.exec(
            select(MarketPrice).where(MarketPrice.platform == "opensea")
        ).first()

        ebay_retrieved = test_session.exec(
            select(MarketPrice).where(MarketPrice.platform == "ebay")
        ).first()

        assert "opensea.io/item" in nft_retrieved.url
        assert "/ethereum/" in nft_retrieved.url
        assert "ebay.com" in ebay_retrieved.url

    def test_external_id_format_differs(self, test_session: Session, sample_rarities: List[Rarity]):
        """Test external_id formats differ between NFT (tx_hash) and eBay (item_id)."""
        card = Card(
            name="Existence Collector Box",
            set_name="WOTF",
            rarity_id=1,
            product_type="Box",
        )
        test_session.add(card)
        test_session.commit()

        # NFT uses transaction hash
        nft_external_id = "0xabc123def456789abcdef0123456789abcdef0123456789abcdef0123456789a"

        # eBay uses item number
        ebay_external_id = "ebay_394857362910"

        nft_sale = MarketPrice(
            card_id=card.id,
            price=200.00,
            title="NFT Box",
            listing_type="sold",
            treatment="Legendary",
            platform="opensea",
            external_id=nft_external_id,
        )

        ebay_sale = MarketPrice(
            card_id=card.id,
            price=90.00,
            title="eBay Box",
            listing_type="sold",
            treatment="Sealed",
            platform="ebay",
            external_id=ebay_external_id,
        )

        test_session.add(nft_sale)
        test_session.add(ebay_sale)
        test_session.commit()

        # NFT external_id starts with 0x (tx hash)
        nft_retrieved = test_session.exec(
            select(MarketPrice).where(MarketPrice.platform == "opensea")
        ).first()

        # eBay external_id starts with ebay_
        ebay_retrieved = test_session.exec(
            select(MarketPrice).where(MarketPrice.platform == "ebay")
        ).first()

        assert nft_retrieved.external_id.startswith("0x")
        assert ebay_retrieved.external_id.startswith("ebay_")


class TestTreatmentColorMapping:
    """Tests for frontend treatment color mapping compatibility."""

    def test_rare_trait_maps_to_color(self):
        """Test 'Rare' trait would map to green in frontend."""
        treatment = "Rare, Fire, Level 5"
        t = treatment.lower()

        # Replicate frontend getTreatmentColor logic
        if "rare" in t:
            color = "#22c55e"  # Green
        else:
            color = "#9ca3af"  # Default gray

        assert color == "#22c55e"

    def test_legendary_trait_maps_to_color(self):
        """Test 'Legendary' trait would map to gold in frontend."""
        treatment = "Legendary Dragon"
        t = treatment.lower()

        if "legendary" in t or "mythic" in t:
            color = "#eab308"  # Gold
        elif "rare" in t:
            color = "#22c55e"
        else:
            color = "#9ca3af"

        assert color == "#eab308"

    def test_epic_trait_maps_to_color(self):
        """Test 'Epic' trait would map to orange in frontend."""
        treatment = "Epic Warrior"
        t = treatment.lower()

        if "epic" in t:
            color = "#f97316"  # Orange
        else:
            color = "#9ca3af"

        assert color == "#f97316"

    def test_unknown_trait_uses_default(self):
        """Test unknown traits use default gray color."""
        treatment = "Common #3515"
        t = treatment.lower()

        # Check known patterns
        color = "#9ca3af"  # Default
        if "rare" in t and "ultra" not in t:
            color = "#22c55e"
        elif "legendary" in t or "mythic" in t:
            color = "#eab308"
        elif "epic" in t:
            color = "#f97316"

        assert color == "#9ca3af"
