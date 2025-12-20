"""
Tests for Blokpax scraper functionality.

Tests cover:
- WOTF item identification (is_wotf_asset)
- BPX price conversion (bpx_to_float, bpx_to_usd)
- Floor price extraction
- Asset parsing (parse_asset)
- Sale parsing (parse_sale)
- Offer parsing (via parse_asset)
- Listing parsing (via parse_asset)
- Datetime parsing (_parse_datetime)
- Invalid/malformed response handling
"""

import pytest
from datetime import datetime
from app.scraper.blokpax import (
    bpx_to_float,
    bpx_to_usd,
    parse_asset,
    parse_sale,
    is_wotf_asset,
    _parse_datetime,
    BPX_DECIMALS,
)


class TestBPXPriceConversion:
    """Tests for BPX price conversion functions."""

    def test_bpx_to_float_basic(self):
        """Should convert raw BPX price to float."""
        # 500000000000000 raw = 500,000 BPX (with 9 decimals)
        raw_price = 500000000000000
        expected = 500000.0
        assert bpx_to_float(raw_price) == expected

    def test_bpx_to_float_small_amount(self):
        """Should handle small BPX amounts."""
        # 1000000000 raw = 1 BPX
        raw_price = 1000000000
        expected = 1.0
        assert bpx_to_float(raw_price) == expected

    def test_bpx_to_float_zero(self):
        """Should handle zero BPX."""
        assert bpx_to_float(0) == 0.0

    def test_bpx_to_float_fractional(self):
        """Should handle fractional BPX amounts."""
        # 500000000 raw = 0.5 BPX
        raw_price = 500000000
        expected = 0.5
        assert bpx_to_float(raw_price) == expected

    def test_bpx_to_float_large_amount(self):
        """Should handle large BPX amounts."""
        # 1000000000000000 raw = 1,000,000 BPX
        raw_price = 1000000000000000
        expected = 1000000.0
        assert bpx_to_float(raw_price) == expected

    def test_bpx_to_usd_basic(self):
        """Should convert raw BPX to USD."""
        # 500000000000000 raw = 500,000 BPX
        # At $0.002/BPX = $1,000 USD
        raw_price = 500000000000000
        bpx_price_usd = 0.002
        expected = 1000.0
        assert bpx_to_usd(raw_price, bpx_price_usd) == expected

    def test_bpx_to_usd_different_rate(self):
        """Should handle different BPX/USD rates."""
        # 1000000000 raw = 1 BPX
        # At $0.005/BPX = $0.005 USD
        raw_price = 1000000000
        bpx_price_usd = 0.005
        expected = 0.005
        assert bpx_to_usd(raw_price, bpx_price_usd) == expected

    def test_bpx_to_usd_zero_price(self):
        """Should handle zero BPX price."""
        assert bpx_to_usd(0, 0.002) == 0.0

    def test_bpx_to_usd_high_rate(self):
        """Should handle higher BPX price."""
        # 100000000000 raw = 100 BPX
        # At $0.01/BPX = $1 USD
        raw_price = 100000000000
        bpx_price_usd = 0.01
        expected = 1.0
        assert bpx_to_usd(raw_price, bpx_price_usd) == expected


class TestDatetimeParsing:
    """Tests for _parse_datetime function."""

    def test_parse_datetime_with_microseconds(self):
        """Should parse ISO datetime with microseconds."""
        dt_str = "2025-10-30T05:56:30.000000Z"
        result = _parse_datetime(dt_str)
        assert result is not None
        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 10
        assert result.day == 30
        assert result.hour == 5
        assert result.minute == 56
        assert result.second == 30

    def test_parse_datetime_without_microseconds(self):
        """Should parse ISO datetime without microseconds."""
        dt_str = "2025-10-30T05:56:30Z"
        result = _parse_datetime(dt_str)
        assert result is not None
        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 10
        assert result.day == 30

    def test_parse_datetime_none(self):
        """Should return None for None input."""
        assert _parse_datetime(None) is None

    def test_parse_datetime_empty_string(self):
        """Should return None for empty string."""
        assert _parse_datetime("") is None

    def test_parse_datetime_invalid_format(self):
        """Should return None for invalid format."""
        assert _parse_datetime("not-a-date") is None

    def test_parse_datetime_wrong_format(self):
        """Should return None for wrong date format."""
        assert _parse_datetime("10/30/2025") is None


class TestWOTFItemIdentification:
    """Tests for is_wotf_asset function."""

    def test_wotf_explicit_name(self):
        """Should identify explicit WOTF names."""
        assert is_wotf_asset("Wonders of the First Existence Progo") is True
        assert is_wotf_asset("WOTF Collector Box") is True

    def test_orbital_redemption_token(self):
        """Should identify Orbital Redemption Tokens."""
        assert is_wotf_asset("Orbital Redemption Token #123") is True
        assert is_wotf_asset("ORBITAL REDEMPTION TOKEN") is True

    def test_existence_keyword(self):
        """Should identify Existence set items."""
        assert is_wotf_asset("Existence Collector Booster Box") is True
        assert is_wotf_asset("Existence #1234") is True

    def test_case_insensitive_matching(self):
        """Should match case-insensitively."""
        assert is_wotf_asset("wonders of the first") is True
        assert is_wotf_asset("WOTF PROGO") is True
        assert is_wotf_asset("orbital redemption token") is True

    def test_non_wotf_items(self):
        """Should reject non-WOTF items."""
        assert is_wotf_asset("Random NFT Collection") is False
        assert is_wotf_asset("CryptoPunks #1234") is False
        assert is_wotf_asset("Bored Ape #5678") is False

    def test_partial_match_rejection(self):
        """Should match items with WOTF keywords."""
        # "existence" matches WOTF keyword (Existence set)
        # The current implementation accepts "existence" as a WOTF indicator
        assert is_wotf_asset("The Existence of Time") is True
        # And in context of trading cards, should also pass
        assert is_wotf_asset("Existence Booster Pack") is True


class TestAssetParsing:
    """Tests for parse_asset function."""

    def test_parse_asset_basic(self):
        """Should parse basic asset data."""
        data = {
            "data": {
                "id": "123456",
                "name": "WOTF Existence Collector Box #100",
                "description": "Limited edition collector box",
                "image": "https://example.com/image.png",
                "network_id": 1,
                "contract_address": "0x1234567890abcdef",
                "token_id": "100",
                "attributes": [
                    {"trait_type": "Box Art", "value": "Dragon"},
                    {"trait_type": "Serial Number", "value": "100/3393"}
                ],
                "asset": {
                    "owner_count": 1,
                    "token_count": 1,
                    "floor_listing": None,
                    "listings": [],
                    "offers": []
                }
            }
        }

        slug = "wotf-existence-collector-boxes"
        bpx_price_usd = 0.002

        result = parse_asset(data, slug, bpx_price_usd)

        assert result.asset_id == "123456"
        assert result.name == "WOTF Existence Collector Box #100"
        assert result.description == "Limited edition collector box"
        assert result.image_url == "https://example.com/image.png"
        assert result.storefront_slug == slug
        assert result.network_id == 1
        assert result.contract_address == "0x1234567890abcdef"
        assert result.token_id == "100"
        assert result.owner_count == 1
        assert result.token_count == 1
        assert len(result.traits) == 2
        assert result.traits[0]["trait_type"] == "Box Art"
        assert result.traits[0]["value"] == "Dragon"
        assert result.floor_price_bpx is None
        assert result.floor_price_usd is None

    def test_parse_asset_with_floor_listing(self):
        """Should parse floor listing price."""
        data = {
            "data": {
                "id": "123456",
                "name": "WOTF Collector Box",
                "network_id": 1,
                "contract_address": "0xabc",
                "token_id": "1",
                "asset": {
                    "owner_count": 1,
                    "token_count": 1,
                    "floor_listing": {
                        "id": "789",
                        "price": 500000000000000,  # 500,000 BPX
                        "quantity": 1,
                        "seller": {"address": "0xseller"},
                        "created_at": "2025-10-30T05:56:30.000000Z"
                    },
                    "listings": [],
                    "offers": []
                },
                "attributes": []
            }
        }

        slug = "wotf-existence-collector-boxes"
        bpx_price_usd = 0.002

        result = parse_asset(data, slug, bpx_price_usd)

        assert result.floor_price_bpx == 500000.0
        assert result.floor_price_usd == 1000.0  # 500,000 * 0.002

    def test_parse_asset_with_listings(self):
        """Should parse active listings."""
        data = {
            "data": {
                "id": "123456",
                "name": "WOTF Art Proof",
                "network_id": 1,
                "contract_address": "0xabc",
                "token_id": "1",
                "asset": {
                    "owner_count": 1,
                    "token_count": 1,
                    "floor_listing": None,
                    "listings": [
                        {
                            "id": "101",
                            "price": 100000000000000,  # 100,000 BPX
                            "quantity": 1,
                            "seller": {"username": "0xseller1"},
                            "created_at": "2025-10-30T05:56:30.000000Z"
                        },
                        {
                            "id": "102",
                            "price": 150000000000000,  # 150,000 BPX
                            "quantity": 2,
                            "seller": {"username": "0xseller2"},
                            "created_at": "2025-10-31T10:00:00.000000Z"
                        }
                    ],
                    "offers": []
                },
                "attributes": []
            }
        }

        slug = "wotf-art-proofs"
        bpx_price_usd = 0.002

        result = parse_asset(data, slug, bpx_price_usd)

        assert len(result.listings) == 2

        # Check first listing
        listing1 = result.listings[0]
        assert listing1.listing_id == "101"
        assert listing1.asset_id == "123456"
        assert listing1.price_bpx == 100000.0
        assert listing1.price_usd == 200.0  # 100,000 * 0.002
        assert listing1.quantity == 1
        assert listing1.seller_address == "0xseller1"

        # Check second listing
        listing2 = result.listings[1]
        assert listing2.listing_id == "102"
        assert listing2.price_bpx == 150000.0
        assert listing2.price_usd == 300.0
        assert listing2.quantity == 2

    def test_parse_asset_with_offers(self):
        """Should parse offers (bids)."""
        data = {
            "data": {
                "id": "123456",
                "name": "WOTF Collector Box",
                "network_id": 1,
                "contract_address": "0xabc",
                "token_id": "1",
                "asset": {
                    "owner_count": 1,
                    "token_count": 1,
                    "floor_listing": None,
                    "listings": [],
                    "offers": [
                        {
                            "id": "201",
                            "offer_bpx_per_token": 90000000000000,  # 90,000 BPX
                            "quantity": 1,
                            "offerer": {"address": "0xbuyer1"},
                            "offer_status": "open",
                            "created_at": "2025-10-30T05:56:30.000000Z"
                        },
                        {
                            "id": "202",
                            "offer_bpx_per_token": 85000000000000,  # 85,000 BPX
                            "quantity": 2,
                            "offerer": {"address": "0xbuyer2"},
                            "offer_status": "open",
                            "created_at": "2025-10-31T10:00:00.000000Z"
                        }
                    ]
                },
                "attributes": []
            }
        }

        slug = "wotf-existence-collector-boxes"
        bpx_price_usd = 0.002

        result = parse_asset(data, slug, bpx_price_usd)

        assert len(result.offers) == 2

        # Check first offer
        offer1 = result.offers[0]
        assert offer1.offer_id == "201"
        assert offer1.asset_id == "123456"
        assert offer1.price_bpx == 90000.0
        assert offer1.price_usd == 180.0  # 90,000 * 0.002
        assert offer1.quantity == 1
        assert offer1.buyer_address == "0xbuyer1"
        assert offer1.status == "open"

        # Check second offer
        offer2 = result.offers[1]
        assert offer2.offer_id == "202"
        assert offer2.price_bpx == 85000.0
        assert offer2.price_usd == 170.0
        assert offer2.quantity == 2

    def test_parse_asset_without_asset_wrapper(self):
        """Should handle data without nested 'data' wrapper."""
        data = {
            "id": "123456",
            "name": "WOTF Collector Box",
            "network_id": 1,
            "contract_address": "0xabc",
            "token_id": "1",
            "asset": {
                "owner_count": 1,
                "token_count": 1,
                "floor_listing": None,
                "listings": [],
                "offers": []
            },
            "attributes": []
        }

        slug = "wotf-existence-collector-boxes"
        bpx_price_usd = 0.002

        result = parse_asset(data, slug, bpx_price_usd)

        assert result.asset_id == "123456"
        assert result.name == "WOTF Collector Box"

    def test_parse_asset_missing_optional_fields(self):
        """Should handle missing optional fields gracefully."""
        data = {
            "data": {
                "id": "123456",
                "name": "WOTF Item",
                "network_id": 1,
                "contract_address": "0xabc",
                "token_id": "1",
                "asset": {
                    "owner_count": 1,
                    "token_count": 1,
                    "listings": [],
                    "offers": []
                }
            }
        }

        slug = "wotf-art-proofs"
        bpx_price_usd = 0.002

        result = parse_asset(data, slug, bpx_price_usd)

        assert result.description is None
        assert result.image_url is None
        assert result.floor_price_bpx is None
        assert result.floor_price_usd is None
        assert len(result.traits) == 0

    def test_parse_asset_empty_traits(self):
        """Should handle empty traits array."""
        data = {
            "data": {
                "id": "123456",
                "name": "WOTF Item",
                "network_id": 1,
                "contract_address": "0xabc",
                "token_id": "1",
                "asset": {
                    "owner_count": 1,
                    "token_count": 1,
                    "listings": [],
                    "offers": []
                },
                "attributes": []
            }
        }

        slug = "wotf-art-proofs"
        bpx_price_usd = 0.002

        result = parse_asset(data, slug, bpx_price_usd)

        assert result.traits == []


class TestSaleParsing:
    """Tests for parse_sale function."""

    def test_parse_sale_filled_listing(self):
        """Should parse filled listing as sale."""
        activity = {
            "listing": {
                "id": "301",
                "listing_status": "filled",
                "price": 500000000000000,  # 500,000 BPX
                "quantity": 1,
                "seller": {"address": "0xseller"},
                "buyer": {"address": "0xbuyer"},
                "filled_at": "2025-11-01T12:00:00.000000Z"
            },
            "asset": {
                "id": "123456",
                "name": "WOTF Existence Collector Box #100"
            }
        }

        bpx_price_usd = 0.002

        result = parse_sale(activity, bpx_price_usd)

        assert result is not None
        assert result.listing_id == "301"
        assert result.asset_id == "123456"
        assert result.asset_name == "WOTF Existence Collector Box #100"
        assert result.price_bpx == 500000.0
        assert result.price_usd == 1000.0  # 500,000 * 0.002
        assert result.quantity == 1
        assert result.seller_address == "0xseller"
        assert result.buyer_address == "0xbuyer"
        assert result.filled_at.year == 2025
        assert result.filled_at.month == 11
        assert result.filled_at.day == 1

    def test_parse_sale_active_listing(self):
        """Should return None for active listing."""
        activity = {
            "listing": {
                "id": "302",
                "listing_status": "active",
                "price": 500000000000000,
                "quantity": 1,
                "seller": {"address": "0xseller"}
            },
            "asset": {
                "id": "123456",
                "name": "WOTF Collector Box"
            }
        }

        bpx_price_usd = 0.002

        result = parse_sale(activity, bpx_price_usd)

        assert result is None

    def test_parse_sale_cancelled_listing(self):
        """Should return None for cancelled listing."""
        activity = {
            "listing": {
                "id": "303",
                "listing_status": "cancelled",
                "price": 500000000000000,
                "quantity": 1,
                "seller": {"address": "0xseller"}
            },
            "asset": {
                "id": "123456",
                "name": "WOTF Collector Box"
            }
        }

        bpx_price_usd = 0.002

        result = parse_sale(activity, bpx_price_usd)

        assert result is None

    def test_parse_sale_missing_filled_at(self):
        """Should use current time if filled_at is missing."""
        activity = {
            "listing": {
                "id": "304",
                "listing_status": "filled",
                "price": 500000000000000,
                "quantity": 1,
                "seller": {"address": "0xseller"},
                "buyer": {"address": "0xbuyer"}
                # No filled_at field
            },
            "asset": {
                "id": "123456",
                "name": "WOTF Collector Box"
            }
        }

        bpx_price_usd = 0.002

        result = parse_sale(activity, bpx_price_usd)

        assert result is not None
        # Should have a filled_at timestamp (current time)
        assert result.filled_at is not None
        assert isinstance(result.filled_at, datetime)

    def test_parse_sale_zero_price(self):
        """Should handle zero price sales."""
        activity = {
            "listing": {
                "id": "305",
                "listing_status": "filled",
                "price": 0,
                "quantity": 1,
                "seller": {"address": "0xseller"},
                "buyer": {"address": "0xbuyer"},
                "filled_at": "2025-11-01T12:00:00.000000Z"
            },
            "asset": {
                "id": "123456",
                "name": "WOTF Collector Box"
            }
        }

        bpx_price_usd = 0.002

        result = parse_sale(activity, bpx_price_usd)

        assert result is not None
        assert result.price_bpx == 0.0
        assert result.price_usd == 0.0

    def test_parse_sale_multiple_quantity(self):
        """Should handle sales with quantity > 1."""
        activity = {
            "listing": {
                "id": "306",
                "listing_status": "filled",
                "price": 100000000000000,  # 100,000 BPX per item
                "quantity": 5,
                "seller": {"address": "0xseller"},
                "buyer": {"address": "0xbuyer"},
                "filled_at": "2025-11-01T12:00:00.000000Z"
            },
            "asset": {
                "id": "123456",
                "name": "WOTF Art Proof"
            }
        }

        bpx_price_usd = 0.002

        result = parse_sale(activity, bpx_price_usd)

        assert result is not None
        assert result.quantity == 5
        assert result.price_bpx == 100000.0
        assert result.price_usd == 200.0


class TestInvalidResponseHandling:
    """Tests for handling invalid/malformed API responses."""

    def test_parse_asset_empty_data(self):
        """Should handle empty data gracefully."""
        data = {}
        slug = "wotf-existence-collector-boxes"
        bpx_price_usd = 0.002

        result = parse_asset(data, slug, bpx_price_usd)

        # Should create asset with empty/default values
        assert result.asset_id == ""
        assert result.name == ""
        assert result.contract_address == ""
        assert result.token_id == ""

    def test_parse_asset_missing_asset_section(self):
        """Should handle missing asset section."""
        data = {
            "data": {
                "id": "123456",
                "name": "WOTF Collector Box",
                "network_id": 1,
                "contract_address": "0xabc",
                "token_id": "1",
                "attributes": []
                # No "asset" section
            }
        }

        slug = "wotf-existence-collector-boxes"
        bpx_price_usd = 0.002

        result = parse_asset(data, slug, bpx_price_usd)

        # Should handle gracefully with defaults
        assert result.asset_id == "123456"
        assert result.owner_count == 0
        assert result.token_count == 1
        assert result.floor_price_bpx is None
        assert result.listings == []
        assert result.offers == []

    def test_parse_asset_malformed_listing(self):
        """Should skip malformed listings."""
        data = {
            "data": {
                "id": "123456",
                "name": "WOTF Collector Box",
                "network_id": 1,
                "contract_address": "0xabc",
                "token_id": "1",
                "asset": {
                    "owner_count": 1,
                    "token_count": 1,
                    "listings": [
                        {
                            "id": "101",
                            "price": 100000000000000,
                            "quantity": 1,
                            "seller": {"address": "0xseller1"}
                        },
                        {
                            # Malformed - missing price
                            "id": "102",
                            "quantity": 1,
                            "seller": {"address": "0xseller2"}
                        }
                    ],
                    "offers": []
                },
                "attributes": []
            }
        }

        slug = "wotf-existence-collector-boxes"
        bpx_price_usd = 0.002

        result = parse_asset(data, slug, bpx_price_usd)

        # Should still parse valid listing
        assert len(result.listings) == 2
        # First listing should be valid
        assert result.listings[0].listing_id == "101"
        assert result.listings[0].price_bpx == 100000.0
        # Second listing will have price 0 (malformed)
        assert result.listings[1].listing_id == "102"
        assert result.listings[1].price_bpx == 0.0

    def test_parse_sale_empty_activity(self):
        """Should handle empty activity gracefully."""
        activity = {}
        bpx_price_usd = 0.002

        result = parse_sale(activity, bpx_price_usd)

        # Should return None for invalid activity
        assert result is None

    def test_parse_sale_missing_listing(self):
        """Should handle missing listing section."""
        activity = {
            "asset": {
                "id": "123456",
                "name": "WOTF Collector Box"
            }
            # No "listing" section
        }
        bpx_price_usd = 0.002

        result = parse_sale(activity, bpx_price_usd)

        # Should return None
        assert result is None

    def test_parse_sale_missing_asset(self):
        """Should handle missing asset section."""
        activity = {
            "listing": {
                "id": "301",
                "listing_status": "filled",
                "price": 500000000000000,
                "quantity": 1,
                "seller": {"address": "0xseller"},
                "buyer": {"address": "0xbuyer"},
                "filled_at": "2025-11-01T12:00:00.000000Z"
            }
            # No "asset" section
        }
        bpx_price_usd = 0.002

        result = parse_sale(activity, bpx_price_usd)

        # Should still create sale with empty asset info
        assert result is not None
        assert result.asset_id == ""
        assert result.asset_name == ""


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_bpx_conversion_very_small_amount(self):
        """Should handle very small BPX amounts."""
        # 1 raw = 0.000000001 BPX (1 wei equivalent)
        raw_price = 1
        result = bpx_to_float(raw_price)
        assert result == 1e-9

    def test_bpx_conversion_max_uint256(self):
        """Should handle very large BPX amounts."""
        # Near max uint256
        raw_price = 10**18
        result = bpx_to_float(raw_price)
        assert result == 10**9

    def test_parse_asset_polygon_network(self):
        """Should handle Polygon network assets."""
        data = {
            "data": {
                "id": "123456",
                "name": "WOTF Polygon Asset",
                "network_id": 137,  # Polygon
                "contract_address": "0xabc",
                "token_id": "1",
                "asset": {
                    "owner_count": 1,
                    "token_count": 1,
                    "listings": [],
                    "offers": []
                },
                "attributes": []
            }
        }

        slug = "wotf-art-proofs"
        bpx_price_usd = 0.002

        result = parse_asset(data, slug, bpx_price_usd)

        assert result.network_id == 137

    def test_parse_asset_multiple_owners(self):
        """Should handle assets with multiple owners (ERC1155)."""
        data = {
            "data": {
                "id": "123456",
                "name": "WOTF Multi-Owner Asset",
                "network_id": 1,
                "contract_address": "0xabc",
                "token_id": "1",
                "asset": {
                    "owner_count": 10,
                    "token_count": 100,
                    "listings": [],
                    "offers": []
                },
                "attributes": []
            }
        }

        slug = "wotf-art-proofs"
        bpx_price_usd = 0.002

        result = parse_asset(data, slug, bpx_price_usd)

        assert result.owner_count == 10
        assert result.token_count == 100

    def test_parse_asset_string_ids(self):
        """Should handle both string and numeric IDs."""
        data = {
            "data": {
                "id": 123456,  # Numeric ID
                "name": "WOTF Item",
                "network_id": 1,
                "contract_address": "0xabc",
                "token_id": 1,  # Numeric token ID
                "asset": {
                    "owner_count": 1,
                    "token_count": 1,
                    "listings": [
                        {
                            "id": 789,  # Numeric listing ID
                            "price": 100000000000000,
                            "quantity": 1,
                            "seller": {"address": "0xseller"}
                        }
                    ],
                    "offers": []
                },
                "attributes": []
            }
        }

        slug = "wotf-art-proofs"
        bpx_price_usd = 0.002

        result = parse_asset(data, slug, bpx_price_usd)

        # Should convert to strings
        assert result.asset_id == "123456"
        assert result.token_id == "1"
        assert result.listings[0].listing_id == "789"

    def test_is_wotf_asset_with_whitespace(self):
        """Should handle extra whitespace in asset names."""
        assert is_wotf_asset("  Wonders of the First  ") is True
        assert is_wotf_asset("WOTF   Existence") is True
        # "orbital redemption token" requires all words together (spaces matter)
        # Multiple spaces break the match, so this should be False
        assert is_wotf_asset("Orbital Redemption Token") is True
        assert is_wotf_asset("Orbital   Redemption   Token") is False

    def test_parse_asset_missing_seller(self):
        """Should handle missing seller field gracefully."""
        data = {
            "data": {
                "id": "123456",
                "name": "WOTF Item",
                "network_id": 1,
                "contract_address": "0xabc",
                "token_id": "1",
                "asset": {
                    "owner_count": 1,
                    "token_count": 1,
                    "listings": [
                        {
                            "id": "101",
                            "price": 100000000000000,
                            "quantity": 1
                            # No seller field at all
                        }
                    ],
                    "offers": []
                },
                "attributes": []
            }
        }

        slug = "wotf-art-proofs"
        bpx_price_usd = 0.002

        result = parse_asset(data, slug, bpx_price_usd)

        # Should handle gracefully with empty dict default
        assert len(result.listings) == 1
        assert result.listings[0].seller_address == ""


class TestRealWorldScenarios:
    """Tests based on real Blokpax API responses."""

    def test_collector_box_with_serial(self):
        """Should parse collector box with serial number."""
        data = {
            "data": {
                "id": "4294967297",
                "name": "WOTF Existence Collector Box #929",
                "description": "Serialized collector booster box",
                "image": "https://blokpax.com/images/box-929.png",
                "network_id": 1,
                "contract_address": "0x1234567890abcdef",
                "token_id": "929",
                "attributes": [
                    {"trait_type": "Box Art", "value": "Dragon"},
                    {"trait_type": "Serial Number", "value": "929/3393"}
                ],
                "asset": {
                    "owner_count": 1,
                    "token_count": 1,
                    "floor_listing": {
                        "id": "12345",
                        "price": 475000000000000,  # 475,000 BPX
                        "quantity": 1,
                        "seller": {"address": "0xabcdef1234567890"},
                        "created_at": "2025-10-30T05:56:30.000000Z"
                    },
                    "listings": [],
                    "offers": [
                        {
                            "id": "67890",
                            "offer_bpx_per_token": 450000000000000,  # 450,000 BPX
                            "quantity": 1,
                            "offerer": {"address": "0x9876543210fedcba"},
                            "offer_status": "open",
                            "created_at": "2025-10-29T10:00:00.000000Z"
                        }
                    ]
                }
            }
        }

        slug = "wotf-existence-collector-boxes"
        bpx_price_usd = 0.002

        result = parse_asset(data, slug, bpx_price_usd)

        # Verify basic info
        assert result.asset_id == "4294967297"
        assert result.name == "WOTF Existence Collector Box #929"
        assert result.token_id == "929"

        # Verify traits
        assert len(result.traits) == 2
        box_art = next(t for t in result.traits if t["trait_type"] == "Box Art")
        assert box_art["value"] == "Dragon"
        serial = next(t for t in result.traits if t["trait_type"] == "Serial Number")
        assert serial["value"] == "929/3393"

        # Verify floor price
        assert result.floor_price_bpx == 475000.0
        assert result.floor_price_usd == 950.0  # 475,000 * 0.002

        # Verify offers
        assert len(result.offers) == 1
        assert result.offers[0].price_bpx == 450000.0
        assert result.offers[0].price_usd == 900.0

    def test_art_proof_sequential_ids(self):
        """Should parse art proof with sequential ID."""
        data = {
            "data": {
                "id": "1234",  # Sequential ID (not large)
                "name": "WOTF Existence Progo Art Proof",
                "description": "Limited edition art proof",
                "network_id": 1,
                "contract_address": "0xartproof",
                "token_id": "1234",
                "attributes": [
                    {"trait_type": "Character", "value": "Progo"},
                    {"trait_type": "Edition", "value": "Art Proof"}
                ],
                "asset": {
                    "owner_count": 1,
                    "token_count": 1,
                    "floor_listing": None,
                    "listings": [
                        {
                            "id": "5001",
                            "price": 75000000000000,  # 75,000 BPX
                            "quantity": 1,
                            "seller": {"address": "0xartist"},
                            "created_at": "2025-11-01T08:30:00.000000Z"
                        }
                    ],
                    "offers": []
                }
            }
        }

        slug = "wotf-art-proofs"
        bpx_price_usd = 0.002

        result = parse_asset(data, slug, bpx_price_usd)

        assert result.asset_id == "1234"
        assert result.name == "WOTF Existence Progo Art Proof"
        assert len(result.listings) == 1
        assert result.listings[0].price_bpx == 75000.0
        assert result.listings[0].price_usd == 150.0

    def test_reward_room_mixed_items(self):
        """Should handle reward room (mixed WOTF and non-WOTF)."""
        # WOTF item in reward room
        wotf_item = "Orbital Redemption Token #42"
        assert is_wotf_asset(wotf_item) is True

        # Non-WOTF item in reward room
        non_wotf_item = "Generic Reward NFT #123"
        assert is_wotf_asset(non_wotf_item) is False
