"""
Preslab name parser and card matcher.

Parses Blokpax preslab asset names like:
  "Kishral Vivasynth, ChronoTitan '24 9 MINT 109 (Cert: #C8498411)"

Into structured data:
  - card_name: "Kishral Vivasynth, ChronoTitan"
  - grade: "9 MINT"
  - grade_number: 9
  - serial: "109"
  - cert_id: "C8498411"
  - treatment: "Preslab TAG 9"
"""

import re
from typing import Optional, Dict, Any
from dataclasses import dataclass
from sqlmodel import Session, select

from app.core.typing import col
from app.models.card import Card, Rarity


@dataclass
class PreslabInfo:
    """Parsed preslab information."""

    card_name: str
    grade: Optional[str]  # e.g., "9 MINT", "8 NM MT"
    grade_number: Optional[int]  # Just the number: 9, 8, etc.
    serial: Optional[str]
    cert_id: Optional[str]
    treatment: str  # Computed: "Preslab TAG 9" or "Preslab TAG"
    grading: Optional[str]  # For MarketPrice.grading field: "TAG 9"
    raw_name: str  # Original asset name


def parse_preslab_name(asset_name: str) -> Optional[PreslabInfo]:
    """
    Parse a preslab asset name into components.

    Examples:
        "Kishral Vivasynth, ChronoTitan '24 9 MINT 109 (Cert: #C8498411)"
        "Sylira Shadowstalker '24 210 (Cert: #T4614216)"
        "Mold Warrior '24 8 NM MT 353 (Cert: #X4074354)"

    Pattern: [Card Name] '24 [Optional: Grade] [Serial] (Cert: #[ID])
    """
    # Extract cert ID first
    cert_match = re.search(r"\(Cert:\s*#([A-Z0-9]+)\)", asset_name)
    cert_id = cert_match.group(1) if cert_match else None

    # Remove cert portion for easier parsing
    name_without_cert = re.sub(r"\s*\(Cert:\s*#[A-Z0-9]+\)", "", asset_name).strip()

    # Pattern: [Card Name] '24 [stuff]
    # The '24 marks the year/set indicator
    year_match = re.search(r"^(.+?)\s+'24\s+(.*)$", name_without_cert)

    if not year_match:
        return None

    card_name = year_match.group(1).strip()
    remainder = year_match.group(2).strip()

    # Parse remainder: could be "[grade] [serial]" or just "[serial]"
    # Grades look like: "9 MINT", "8 NM MT", "10 GEM MINT", etc.
    # Serial is usually just a number at the end

    grade = None
    grade_number = None
    serial = None
    grading = None

    # Try to match grade pattern: number followed by grade text
    grade_match = re.match(
        r"^(\d+)\s+(MINT|NM MT|GEM MINT|NM|MT|EX|VG|GOOD|POOR)(?:\s+(.+))?$", remainder, re.IGNORECASE
    )

    if grade_match:
        grade_number = int(grade_match.group(1))
        grade_text = grade_match.group(2).upper()
        grade = f"{grade_number} {grade_text}"
        grading = f"TAG {grade_number}"  # For MarketPrice.grading field
        serial = grade_match.group(3).strip() if grade_match.group(3) else None
    else:
        # No grade, remainder is just serial
        serial = remainder if remainder else None

    # Compute treatment name
    if grade_number:
        treatment = f"Preslab TAG {grade_number}"
    else:
        treatment = "Preslab TAG"

    return PreslabInfo(
        card_name=card_name,
        grade=grade,
        grade_number=grade_number,
        serial=serial,
        cert_id=cert_id,
        treatment=treatment,
        grading=grading,
        raw_name=asset_name,
    )


def normalize_card_name(name: str) -> str:
    """Normalize card name for matching."""
    normalized = name.lower().strip()
    normalized = re.sub(r"\s+", " ", normalized)  # Collapse whitespace
    normalized = re.sub(r",\s*$", "", normalized)  # Remove trailing commas
    return normalized


# Cache for card name lookups
_card_cache: Dict[str, Optional[Dict[str, Any]]] = {}
_cards_loaded = False


def _load_cards_cache(session: Session) -> None:
    """Load all non-sealed cards into cache for fast lookup."""
    global _card_cache, _cards_loaded

    if _cards_loaded:
        return

    stmt = select(Card, Rarity.name).join(Rarity, col(Card.rarity_id) == col(Rarity.id)).where(Rarity.name != "SEALED")
    results = session.exec(stmt).all()

    for card, rarity_name in results:
        normalized = normalize_card_name(card.name)
        _card_cache[normalized] = {"id": card.id, "name": card.name, "set_name": card.set_name, "rarity": rarity_name}

    _cards_loaded = True
    print(f"[Preslab] Loaded {len(_card_cache)} cards into cache")


def find_matching_card(preslab_name: str, session: Session) -> Optional[Dict[str, Any]]:
    """
    Find a matching card for a preslab card name.

    Returns dict with card info: {id, name, set_name, rarity} or None
    """
    _load_cards_cache(session)

    normalized = normalize_card_name(preslab_name)

    # Direct match
    if normalized in _card_cache:
        return _card_cache[normalized]

    # Try without trailing parts (some cards have subtitles)
    # e.g., "Kishral Vivasynth, ChronoTitan" might match "Kishral Vivasynth"
    parts = normalized.split(",")
    if len(parts) > 1:
        base_name = parts[0].strip()
        if base_name in _card_cache:
            return _card_cache[base_name]

    # Fuzzy match: check if preslab name contains or is contained by card name
    for card_normalized, card_info in _card_cache.items():
        if card_normalized in normalized or normalized in card_normalized:
            return card_info

    return None


def clear_card_cache() -> None:
    """Clear the card cache (useful for testing or after card updates)."""
    global _card_cache, _cards_loaded
    _card_cache = {}
    _cards_loaded = False
