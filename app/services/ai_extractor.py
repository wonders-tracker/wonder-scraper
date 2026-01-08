"""
AI-powered listing data extraction service.

Uses GPT-4o-mini via OpenRouter to intelligently parse eBay listings for:
- Quantity detection (e.g., "3x", "Lot of 5", "Bundle")
- Product type classification (Single, Box, Pack, Lot)
- Condition detection (Sealed, Unsealed, Near Mint, etc.)
- Treatment identification (Foil, Serialized, Standard)
- WOTF validation (filtering out Yu-Gi-Oh, Pokemon, DBZ, etc.)
- Structured extraction (card name, set, treatment, condition, grading)
"""

from typing import Optional, Dict, Any, List, Union
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import json
import re
import os
import hashlib

# Ensure environment variables are loaded
load_dotenv()


# =============================================================================
# WOTF KNOWLEDGE BASE - Comprehensive patterns for rule-based filtering
# =============================================================================

# Strong WOTF indicators - if ANY present, it's definitely WOTF
WOTF_INDICATORS = [
    # Brand names
    "wonders of the first",
    "wotf",
    "wonders first",
    "wonder of the first",
    # Set names
    "existence set",
    "existence booster",
    "existence collector",
    "existence 1st",
    "existence classic",
    "existence formless",
    "genesis set",
    "genesis booster",
    "genesis collector",
    # WOTF-specific treatments (unique to this TCG)
    "formless foil",
    "stonefoil",
    "stone foil",
    "stone-foil",
    "classic paper",
    "classic foil",
    "ocm serialized",
    "ocm /10",
    "ocm /25",
    "ocm /50",
    "ocm /75",
    "ocm /99",
    # Serialized patterns
    "serialized /10",
    "serialized /25",
    "serialized /50",
    "serialized /75",
    "serialized /99",
    # WOTF product types
    "play bundle",
    "serialized advantage",
    "2-player starter",
    "collector booster box",
    "play booster pack",
    # Card number formats (Existence has 401 cards)
    "/401",
    "#/401",
    "001/401",
    "/301",
    "/201",
]

# Non-WOTF indicators by TCG - if ANY present, reject the listing
NON_WOTF_INDICATORS = {
    "Yu-Gi-Oh": [
        # Card set codes (most reliable)
        r"mp\d{2}-en",
        r"mged-en",
        r"mago-en",
        r"maze-en",
        r"lcyw-en",
        r"lckc-en",
        r"dude-en",
        r"dupo-en",
        r"led\d-en",
        r"blhr-en",
        r"toch-en",
        r"inch-en",
        "tin of the",
        "pharaoh's gods",
        "pharaohs gods",
        # Brand/game identifiers
        "konami",
        "yugioh",
        "yu-gi-oh",
        "yu gi oh",
        # Iconic cards/archetypes
        "dark magician",
        "blue-eyes",
        "red-eyes",
        "exodia",
        "ruddy rose dragon",
        "roxrose dragon",
        "albion the branded",
        "trishula",
        "ice barrier",
        "stardust dragon",
        "armed dragon",
        "thunder lv",
        "deep-eyes white",
        # Yu-Gi-Oh specific terms
        "duelist",
        "1st edition gold rare",
        "gold rare lp",
        "gold rare nm",
        "secret rare",
        "ultra rare",
        "super rare",
        "starlight rare",
        "collector rare",
        "ghost rare",
        "prismatic secret",
        "ultimate rare",
    ],
    "Dragon Ball Z": [
        # Game identifiers
        "dragonball",
        "dragon ball",
        "dbz ccg",
        "dbz tcg",
        " dbz ",
        "dbz card",
        # Card codes
        r"wa-\d{3}",
        "wa-066",
        "wa-079",
        "gold stamp",
        # Characters (unique to DBZ)
        "goku",
        "vegeta",
        "frieza",
        "gohan",
        "piccolo",
        "android 17",
        "android 18",
        "android 20",
        "hercule",
        "buu",
        "cell saga",
        "trunks",
        "krillin",
        "kamehameha",
        "saiyan",
        "namekian",
    ],
    "Pokemon": [
        # Game identifiers
        "pokemon",
        "pokémon",
        "pkmn",
        # Popular Pokemon (avoid overlap with WOTF card names)
        "pikachu",
        "charizard",
        "mewtwo",
        "eevee",
        "mew ",
        "blastoise",
        "venusaur",
        "gyarados",
        "dragonite",
        # Set names
        "evolving skies",
        "scarlet violet",
        "shining fates",
        "celebrations",
        "brilliant stars",
        "fusion strike",
        "crown zenith",
        "paldea evolved",
        "obsidian flames",
        "151 ",
        "temporal forces",
        "twilight masquerade",
        # Pokemon-specific terms
        "vmax",
        "vstar",
        " ex ",
        " gx ",
        "full art trainer",
        "rainbow rare",
        "alternate art",
        "special art rare",
        "illustration rare",
        "hyper rare",
    ],
    "One Piece": [
        # Game identifiers
        "one piece tcg",
        "one piece card",
        # Set codes
        r"op0\d-",
        "op01",
        "op02",
        "op03",
        "op04",
        "op05",
        "op06",
        "op07",
        "op08",
        # Characters/terms
        "luffy",
        "zoro",
        "straw hat",
        "nami",
        "sanji",
        "romance dawn",
        "paramount war",
        "pillars of strength",
        "kingdoms of intrigue",
    ],
    "MTG": [
        # Game identifiers
        "magic the gathering",
        "mtg ",
        " mtg",
        "wizards of the coast",
        "wotc",
        # MTG-specific terms
        "planeswalker",
        "mana",
        "commander",
        "edh",
        "modern horizons",
        "dominaria",
        "innistrad",
        "phyrexia",
        "ravnica",
        "zendikar",
        "mythic rare",
        "borderless",
        "showcase",
        "retro frame",
        "etched foil",
    ],
    "Sports Cards": [
        # Brands
        "topps",
        "panini",
        "upper deck",
        "bowman",
        "prizm",
        "donruss",
        "fleer",
        "score",
        "leaf",
        # Leagues
        "nba",
        "nfl",
        "mlb",
        "nhl",
        "ufc",
        "wwe",
        # Sports terms
        "rookie card",
        "auto ",
        "autograph",
        "game-used",
        "jersey card",
        "patch card",
        "numbered /99",
    ],
    "Other TCGs": [
        # Flesh and Blood
        "flesh and blood",
        "fab tcg",
        "welcome to rathe",
        # Digimon
        "digimon tcg",
        "digimon card",
        # Weiss Schwarz
        "weiss schwarz",
        "bushiroad",
        # Cardfight Vanguard
        "vanguard",
        "cardfight",
        # Lorcana
        "disney lorcana",
        "lorcana",
        # Union Arena
        "union arena",
    ],
}

# Grading services - not indicators of non-WOTF, but useful to extract
GRADING_SERVICES = ["psa", "cgc", "bgs", "sgc", "ace"]

# Condition keywords for extraction
CONDITION_KEYWORDS = {
    "mint": "Mint",
    "near mint": "Near Mint",
    "nm": "Near Mint",
    "excellent": "Excellent",
    "ex": "Excellent",
    "good": "Good",
    "gd": "Good",
    "light play": "Light Play",
    "lp": "Light Play",
    "moderate play": "Moderate Play",
    "mp": "Moderate Play",
    "heavy play": "Heavy Play",
    "hp": "Heavy Play",
    "damaged": "Damaged",
    "dmg": "Damaged",
}


class AIListingExtractor:
    """AI-powered listing data extractor using GPT-4o-mini."""

    # Cache configuration
    MAX_CACHE_SIZE = 10000
    CACHE_TTL_SECONDS = 3600  # 1 hour

    # Batch configuration (conservative to stay under token limits)
    MAX_BATCH_SIZE = 25  # Max listings per API call
    CHARS_PER_TOKEN = 4  # Rough estimate for tokenization
    MAX_PROMPT_CHARS = 12000  # ~3000 tokens, safe margin for gpt-4o-mini

    # Feedback log configuration
    FEEDBACK_LOG_DIR = Path("logs/ai_decisions")
    MAX_FEEDBACK_LOG_SIZE = 10000  # Max entries before rotation

    def __init__(self):
        """Initialize OpenRouter client with GPT-4o-mini."""
        api_key = os.getenv("OPENROUTER_API_KEY")

        # Title hash cache with LRU eviction (OrderedDict maintains insertion order)
        self._title_cache = OrderedDict()
        self._cache_timestamps = {}

        # Feedback loop - track AI decisions for review
        self._feedback_log: List[Dict[str, Any]] = []

        # Performance metrics
        self._metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "ai_calls": 0,
            "fallback_calls": 0,
            "batch_calls": 0,
            "cache_evictions": 0,
            "rule_based_accepts": 0,
            "rule_based_rejects": 0,
            "ai_accepts": 0,
            "ai_rejects": 0,
        }

        if not api_key:
            print("WARNING: OPENROUTER_API_KEY not set, AI extraction will fallback to rule-based")
            self.client = None
            self.model = None
        else:
            self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
            # Using gpt-4o-mini for reliable, fast extraction
            self.model = "openai/gpt-4o-mini"

    def _hash_title(self, title: str) -> str:
        """Generate SHA256 hash of normalized title for cache key."""
        normalized = title.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _evict_expired_cache_entries(self):
        """Remove expired entries based on TTL."""
        now = datetime.now(timezone.utc).timestamp()
        expired_keys = [key for key, ts in self._cache_timestamps.items() if now - ts > self.CACHE_TTL_SECONDS]

        for key in expired_keys:
            del self._title_cache[key]
            del self._cache_timestamps[key]
            self._metrics["cache_evictions"] += 1

    def _evict_if_cache_full(self):
        """Evict oldest entries if cache exceeds max size (LRU eviction)."""
        while len(self._title_cache) > self.MAX_CACHE_SIZE:
            # OrderedDict.popitem(last=False) removes oldest (FIFO/LRU)
            oldest_key, _ = self._title_cache.popitem(last=False)
            if oldest_key in self._cache_timestamps:
                del self._cache_timestamps[oldest_key]
            self._metrics["cache_evictions"] += 1

    def _cache_get(self, title_hash: str) -> Optional[Dict[str, Any]]:
        """Get from cache and track metrics."""
        # Evict expired entries periodically
        if len(self._cache_timestamps) % 100 == 0:  # Check every 100 accesses
            self._evict_expired_cache_entries()

        if title_hash in self._title_cache:
            # Check if expired
            now = datetime.now(timezone.utc).timestamp()
            if now - self._cache_timestamps[title_hash] > self.CACHE_TTL_SECONDS:
                # Expired, remove it
                del self._title_cache[title_hash]
                del self._cache_timestamps[title_hash]
                self._metrics["cache_misses"] += 1
                self._metrics["cache_evictions"] += 1
                return None

            self._metrics["cache_hits"] += 1
            # Move to end for LRU (most recently used)
            self._title_cache.move_to_end(title_hash)
            return self._title_cache[title_hash]
        else:
            self._metrics["cache_misses"] += 1
            return None

    def _cache_set(self, title_hash: str, value: Dict[str, Any]):
        """Set cache value and track timestamp."""
        self._evict_if_cache_full()
        self._title_cache[title_hash] = value
        self._cache_timestamps[title_hash] = datetime.now(timezone.utc).timestamp()

    def get_metrics(self) -> Dict[str, Union[int, float]]:
        """Get performance metrics."""
        return {
            **self._metrics,
            "cache_size": len(self._title_cache),
            "cache_hit_rate": (
                self._metrics["cache_hits"] / (self._metrics["cache_hits"] + self._metrics["cache_misses"])
                if (self._metrics["cache_hits"] + self._metrics["cache_misses"]) > 0
                else 0.0
            ),
        }

    def reset_metrics(self):
        """Reset metrics (useful for benchmarking)."""
        self._metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "ai_calls": 0,
            "fallback_calls": 0,
            "batch_calls": 0,
            "cache_evictions": 0,
            "rule_based_accepts": 0,
            "rule_based_rejects": 0,
            "ai_accepts": 0,
            "ai_rejects": 0,
        }

    # =========================================================================
    # FEEDBACK LOOP - Track AI decisions for review and improvement
    # =========================================================================

    def _log_decision(
        self,
        title: str,
        card_name: str,
        decision: Dict[str, Any],
        method: str,  # "rule_based" or "ai"
    ):
        """Log a validation decision for review."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "title": title,
            "card_name": card_name,
            "decision": decision,
            "method": method,
        }
        self._feedback_log.append(entry)

        # Rotate if too large
        if len(self._feedback_log) > self.MAX_FEEDBACK_LOG_SIZE:
            self._feedback_log = self._feedback_log[-self.MAX_FEEDBACK_LOG_SIZE // 2 :]

    def get_feedback_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent feedback log entries for review."""
        return self._feedback_log[-limit:]

    def get_rejection_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent rejections for review (potential false positives)."""
        rejections = [entry for entry in self._feedback_log if not entry["decision"].get("is_wotf", True)]
        return rejections[-limit:]

    def get_low_confidence_decisions(self, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Get decisions with low confidence for manual review."""
        return [entry for entry in self._feedback_log if entry["decision"].get("confidence", 1.0) < threshold]

    def export_feedback_log(self, filepath: Optional[str] = None) -> str:
        """Export feedback log to JSON file for analysis."""
        if filepath is None:
            self.FEEDBACK_LOG_DIR.mkdir(parents=True, exist_ok=True)
            filepath = str(
                self.FEEDBACK_LOG_DIR / f"decisions_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
            )

        with open(filepath, "w") as f:
            json.dump(self._feedback_log, f, indent=2)

        return filepath

    def clear_feedback_log(self):
        """Clear the feedback log."""
        self._feedback_log = []

    # =========================================================================
    # CONFIDENCE TIER CALCULATION
    # =========================================================================

    def _calculate_confidence_tier(
        self,
        title: str,
        card_name: str,
        has_wotf_indicator: bool,
        has_non_wotf_indicator: bool,
    ) -> Dict[str, Any]:
        """
        Calculate confidence tier based on match quality.

        Tiers:
        - HIGH (0.95): Strong WOTF indicator OR strong non-WOTF indicator
        - MEDIUM (0.75): Card name match, no conflicting indicators
        - LOW (0.5): Ambiguous, needs AI or manual review

        Returns:
            Dict with confidence, tier, and explanation
        """
        title_lower = title.lower()
        card_name_lower = card_name.lower()

        # HIGH TIER: Clear indicators
        if has_wotf_indicator:
            return {"confidence": 0.95, "tier": "HIGH", "reason": "Strong WOTF indicator present"}

        if has_non_wotf_indicator:
            return {"confidence": 0.95, "tier": "HIGH", "reason": "Strong non-WOTF indicator present"}

        # Check for exact card name match
        exact_match = card_name_lower in title_lower

        # Check for card number pattern
        card_number_match = bool(re.search(r"\d{1,3}/\d{3}", title_lower))

        # MEDIUM TIER: Card name match with supporting evidence
        if exact_match and card_number_match:
            return {"confidence": 0.85, "tier": "MEDIUM-HIGH", "reason": "Card name + number format match"}

        if exact_match:
            # Check for any WOTF-adjacent terms
            wotf_adjacent = any(
                term in title_lower
                for term in [
                    "foil",
                    "paper",
                    "existence",
                    "genesis",
                    "booster",
                    "collector",
                    "play",
                    "bundle",
                    "pack",
                    "box",
                ]
            )

            if wotf_adjacent:
                return {"confidence": 0.75, "tier": "MEDIUM", "reason": "Card name match with TCG context"}

            return {"confidence": 0.65, "tier": "MEDIUM-LOW", "reason": "Card name match only, no TCG context"}

        # LOW TIER: Ambiguous - needs AI
        return {"confidence": 0.5, "tier": "LOW", "reason": "Ambiguous listing, AI validation recommended"}

    def clear_cache(self):
        """Clear all cache entries (useful for testing)."""
        self._title_cache.clear()
        self._cache_timestamps.clear()

    def _estimate_batch_chars(self, listings: List[Dict[str, Any]]) -> int:
        """Estimate character count for batch prompt."""
        total_chars = 500  # Base prompt overhead
        for listing in listings:
            title = listing.get("title", "")
            desc = listing.get("description") or ""
            # Title + optional description + formatting
            total_chars += len(title) + len(desc[:200]) + 50
        return total_chars

    def _split_into_safe_batches(self, listings: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Split listings into batches that fit within token limits."""
        if not listings:
            return []

        batches = []
        current_batch = []
        current_chars = 500  # Base overhead

        for listing in listings:
            title = listing.get("title", "")
            desc = listing.get("description") or ""
            listing_chars = len(title) + len(desc[:200]) + 50

            # Check if adding this listing would exceed limits
            would_exceed_chars = (current_chars + listing_chars) > self.MAX_PROMPT_CHARS
            would_exceed_count = len(current_batch) >= self.MAX_BATCH_SIZE

            if current_batch and (would_exceed_chars or would_exceed_count):
                # Start new batch
                batches.append(current_batch)
                current_batch = []
                current_chars = 500

            current_batch.append(listing)
            current_chars += listing_chars

        # Don't forget last batch
        if current_batch:
            batches.append(current_batch)

        return batches

    def extract_listing_data(
        self, title: str, description: Optional[str] = None, price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Extract structured data from a listing using AI.

        Args:
            title: Listing title
            description: Optional listing description
            price: Optional price (helps with quantity inference)

        Returns:
            Dict with extracted fields:
                - quantity: int (number of items)
                - product_type: str (Single, Box, Pack, Lot)
                - condition: Optional[str] (Sealed, Unsealed, etc.)
                - treatment: str (Classic Paper, Foil, etc.)
                - confidence: float (0-1, extraction confidence)
        """
        # Check cache first to avoid redundant API calls
        title_hash = self._hash_title(title)
        cached_result = self._cache_get(title_hash)
        if cached_result is not None:
            return cached_result

        # If no API key configured, use fallback immediately
        if not self.client:
            self._metrics["fallback_calls"] += 1
            fallback_result = self._fallback_extraction(title, description)
            self._cache_set(title_hash, fallback_result)
            return fallback_result

        prompt = self._build_extraction_prompt(title, description, price)

        try:
            self._metrics["ai_calls"] += 1
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert at parsing TCG/CCG marketplace listings.
Extract structured data from listings for 'Wonders of the First' trading card game.
Always return valid JSON matching the schema exactly.""",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # Low temp for consistent extraction
                max_tokens=200,
            )

            # Parse JSON response
            extracted = json.loads(response.choices[0].message.content)

            # Validate and set defaults
            result = {
                "quantity": extracted.get("quantity", 1),
                "product_type": extracted.get("product_type", "Single"),
                "condition": extracted.get("condition"),
                "treatment": extracted.get("treatment"),  # None if AI couldn't determine
                "confidence": extracted.get("confidence", 0.8),
            }

            # Cache the result before returning
            self._cache_set(title_hash, result)
            return result

        except Exception as e:
            print(f"AI extraction failed: {e}, using fallback")
            self._metrics["fallback_calls"] += 1
            fallback_result = self._fallback_extraction(title, description)
            # Cache fallback to avoid repeated failed API calls for same title
            self._cache_set(title_hash, fallback_result)
            return fallback_result

    def extract_batch(self, listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract data for multiple listings efficiently.

        Args:
            listings: List of dicts with 'title', 'description' (opt), 'price' (opt)

        Returns:
            List of extraction results in same order as input
        """
        if not listings:
            return []

        results = []
        uncached_indices = []
        uncached_listings = []

        # Check cache for each listing
        for i, listing in enumerate(listings):
            title = listing.get("title", "")
            title_hash = self._hash_title(title)

            cached_result = self._cache_get(title_hash)
            if cached_result is not None:
                results.append(cached_result)
            else:
                results.append(None)  # Placeholder
                uncached_indices.append(i)
                uncached_listings.append(listing)

        # If all cached, return early
        if not uncached_listings:
            return results

        # If no API key, use fallback for uncached
        if not self.client:
            self._metrics["fallback_calls"] += len(uncached_listings)
            for i, listing in zip(uncached_indices, uncached_listings):
                fallback = self._fallback_extraction(listing.get("title", ""), listing.get("description"))
                results[i] = fallback
                title_hash = self._hash_title(listing.get("title", ""))
                self._cache_set(title_hash, fallback)
            return results

        # Split into safe sub-batches to avoid token limit issues
        sub_batches = self._split_into_safe_batches(uncached_listings)

        # Extract all sub-batches
        all_extractions = []
        for sub_batch in sub_batches:
            sub_extractions = self._extract_single_batch(sub_batch)
            all_extractions.extend(sub_extractions)

        # Map extractions back to results
        for i, extraction_idx in enumerate(uncached_indices):
            if i < len(all_extractions):
                extracted = all_extractions[i]
                if extracted is not None:
                    results[extraction_idx] = extracted
                    # Cache the result
                    title_hash = self._hash_title(uncached_listings[i].get("title", ""))
                    self._cache_set(title_hash, extracted)
                else:
                    # Fallback if extraction returned None
                    self._metrics["fallback_calls"] += 1
                    listing = uncached_listings[i]
                    fallback = self._fallback_extraction(listing.get("title", ""), listing.get("description"))
                    results[extraction_idx] = fallback
                    title_hash = self._hash_title(listing.get("title", ""))
                    self._cache_set(title_hash, fallback)
            else:
                # Fallback if index out of range
                self._metrics["fallback_calls"] += 1
                listing = uncached_listings[i]
                fallback = self._fallback_extraction(listing.get("title", ""), listing.get("description"))
                results[extraction_idx] = fallback
                title_hash = self._hash_title(listing.get("title", ""))
                self._cache_set(title_hash, fallback)

        return results

    def _extract_single_batch(self, listings: List[Dict[str, Any]]) -> List[Optional[Dict[str, Any]]]:
        """
        Extract data for a single batch of listings (internal method).

        Returns list of extraction results or None for failed extractions.
        """
        if not listings:
            return []

        try:
            self._metrics["batch_calls"] += 1
            self._metrics["ai_calls"] += 1
            batch_prompt = self._build_batch_extraction_prompt(listings)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert at parsing TCG/CCG marketplace listings.
Extract structured data from listings for 'Wonders of the First' trading card game.
Always return valid JSON matching the schema exactly.""",
                    },
                    {"role": "user", "content": batch_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=2000,
            )

            # Parse batch JSON response
            batch_data = json.loads(response.choices[0].message.content)
            raw_extractions = batch_data.get("listings", [])

            # Normalize extractions
            results = []
            for i, listing in enumerate(listings):
                if i < len(raw_extractions):
                    extracted = raw_extractions[i]
                    results.append(
                        {
                            "quantity": extracted.get("quantity", 1),
                            "product_type": extracted.get("product_type", "Single"),
                            "condition": extracted.get("condition"),
                            "treatment": extracted.get("treatment"),  # None if AI couldn't determine
                            "confidence": extracted.get("confidence", 0.8),
                        }
                    )
                else:
                    results.append(None)  # Will trigger fallback

            return results

        except Exception as e:
            print(f"Batch extraction failed: {e}")
            # Return None for all to trigger fallbacks
            return [None] * len(listings)

    def _build_batch_extraction_prompt(self, listings: List[Dict[str, Any]]) -> str:
        """Build extraction prompt for multiple listings."""
        listings_text = ""
        for i, listing in enumerate(listings, 1):
            title = listing.get("title", "")
            description = listing.get("description")
            price = listing.get("price")

            listings_text += f"\n{i}. **Title**: {title}"
            if description:
                listings_text += f"\n   **Description**: {description[:200]}"
            if price:
                listings_text += f"\n   **Price**: ${price}"
            listings_text += "\n"

        return f"""Extract listing data from these {len(listings)} TCG product listings:
{listings_text}

For EACH listing, extract the following into JSON format:
{{
  "listings": [
    {{
      "quantity": <number of items being sold, e.g., 1, 3, 24, 36>,
      "product_type": <"Single" | "Box" | "Pack" | "Lot" | "Bundle">,
      "treatment": <see treatment options below>,
      "confidence": <0.0-1.0, your confidence in this extraction>
    }},
    ... (one entry per listing in order)
  ]
}}

**Treatment Options - DEPENDS ON PRODUCT TYPE**:

For SEALED PRODUCTS (Box, Pack, Lot, Bundle):
- "Factory Sealed" - factory sealed, brand new sealed
- "Sealed" - sealed (default for boxes/packs if no indicator)
- "New" - brand new, new in box, NIB
- "Unopened" - unopened
- "Open Box" - opened, open box
- "Used" - used

For SINGLE CARDS:
- "Classic Paper" - standard non-foil card (default for singles)
- "Classic Foil" - foil, holo, refractor
- "Stonefoil" - stone foil variant
- "Formless Foil" - formless foil variant
- "OCM Serialized" - serialized /10, /25, /50, /75, /99, OCM
- "Prerelease" - prerelease promo
- "Promo" - promotional card
- "Proof/Sample" - proof or sample card
- "Error/Errata" - error or errata card

**Rules**:
- "Booster Box" = product_type: "Box", quantity: 24 (typical), treatment: "Sealed" or "Factory Sealed"
- "Collector Box" = product_type: "Box", quantity: variable, treatment: "Sealed"
- "Booster Pack" = product_type: "Pack", quantity: 1, treatment: "Sealed"
- "Lot of X" or "X Cards" = product_type: "Lot", quantity: X
- Single cards = product_type: "Single", quantity: 1 (unless "3x Name" or similar)
- If title says "3x" or "Lot of 5", set quantity accordingly
- For Boxes/Packs/Lots: use sealed product treatments (Factory Sealed, Sealed, New, etc.)
- For Singles: use card treatments (Classic Paper, Classic Foil, Stonefoil, etc.)
- Confidence should be lower if information is ambiguous

Return ONLY valid JSON with a "listings" array containing {len(listings)} entries in order, no markdown or extra text."""

    def _build_extraction_prompt(self, title: str, description: Optional[str], price: Optional[float]) -> str:
        """Build the extraction prompt for the AI."""
        return f"""Extract listing data from this TCG product listing:

**Title**: {title}
{f"**Description**: {description[:500]}" if description else ""}
{f"**Price**: ${price}" if price else ""}

Extract the following into JSON format:
{{
  "quantity": <number of items being sold, e.g., 1, 3, 24, 36>,
  "product_type": <"Single" | "Box" | "Pack" | "Lot" | "Bundle">,
  "treatment": <see treatment options below>,
  "confidence": <0.0-1.0, your confidence in this extraction>
}}

**Treatment Options - DEPENDS ON PRODUCT TYPE**:

For SEALED PRODUCTS (Box, Pack, Lot, Bundle):
- "Factory Sealed" - factory sealed, brand new sealed
- "Sealed" - sealed (default for boxes/packs if no indicator)
- "New" - brand new, new in box, NIB
- "Unopened" - unopened
- "Open Box" - opened, open box
- "Used" - used

For SINGLE CARDS:
- "Classic Paper" - standard non-foil card (default for singles)
- "Classic Foil" - foil, holo, refractor
- "Stonefoil" - stone foil variant
- "Formless Foil" - formless foil variant
- "OCM Serialized" - serialized /10, /25, /50, /75, /99, OCM
- "Prerelease" - prerelease promo
- "Promo" - promotional card
- "Proof/Sample" - proof or sample card
- "Error/Errata" - error or errata card

**Rules**:
- "Booster Box" = product_type: "Box", quantity: 24 (typical), treatment: "Sealed" or "Factory Sealed"
- "Collector Box" = product_type: "Box", quantity: variable, treatment: "Sealed"
- "Booster Pack" = product_type: "Pack", quantity: 1, treatment: "Sealed"
- "Lot of X" or "X Cards" = product_type: "Lot", quantity: X
- Single cards = product_type: "Single", quantity: 1 (unless "3x Name" or similar)
- If title says "3x" or "Lot of 5", set quantity accordingly
- For Boxes/Packs/Lots: use sealed product treatments (Factory Sealed, Sealed, New, etc.)
- For Singles: use card treatments (Classic Paper, Classic Foil, Stonefoil, etc.)
- Confidence should be lower if information is ambiguous

Return ONLY valid JSON, no markdown or extra text."""

    def _fallback_extraction(self, title: str, description: Optional[str]) -> Dict[str, Any]:
        """Fallback rule-based extraction if AI fails."""
        title_lower = title.lower()

        # Detect quantity
        quantity = 1
        quantity_match = re.search(r"(\d+)x|lot of (\d+)|bundle (\d+)", title_lower)
        if quantity_match:
            quantity = int(quantity_match.group(1) or quantity_match.group(2) or quantity_match.group(3))

        # Detect product type
        product_type = "Single"
        if "booster box" in title_lower or "collector box" in title_lower:
            product_type = "Box"
            quantity = quantity or 24  # Default box quantity
        elif "booster pack" in title_lower or "pack" in title_lower:
            product_type = "Pack"
        elif "lot" in title_lower or "bundle" in title_lower:
            product_type = "Lot"

        # Detect treatment based on product type
        is_sealed_product = product_type in ["Box", "Pack", "Lot", "Bundle"]

        if is_sealed_product:
            # Sealed product treatments
            if "factory sealed" in title_lower:
                treatment = "Factory Sealed"
            elif "sealed" in title_lower:
                treatment = "Sealed"
            elif "new in box" in title_lower or "nib" in title_lower or "brand new" in title_lower:
                treatment = "New"
            elif "unopened" in title_lower:
                treatment = "Unopened"
            elif "open box" in title_lower or "opened" in title_lower:
                treatment = "Open Box"
            elif "used" in title_lower:
                treatment = "Used"
            else:
                # Default for sealed products
                treatment = "Sealed"
        else:
            # Single card treatments
            if "foil" in title_lower and "stone" in title_lower:
                treatment = "Stonefoil"
            elif "foil" in title_lower and "formless" in title_lower:
                treatment = "Formless Foil"
            elif "foil" in title_lower or "holo" in title_lower:
                treatment = "Classic Foil"
            elif "serialized" in title_lower or re.search(r"/\d{2,3}\b", title_lower):
                treatment = "OCM Serialized"
            elif "prerelease" in title_lower:
                treatment = "Prerelease"
            elif "promo" in title_lower:
                treatment = "Promo"
            elif "proof" in title_lower or "sample" in title_lower:
                treatment = "Proof/Sample"
            elif "error" in title_lower or "errata" in title_lower:
                treatment = "Error/Errata"
            elif (
                "classic paper" in title_lower
                or "paper" in title_lower
                or "non-foil" in title_lower
                or "non foil" in title_lower
            ):
                treatment = "Classic Paper"
            else:
                # Unknown treatment - return None to distinguish from detected Classic Paper
                treatment = None

        return {
            "quantity": quantity,
            "product_type": product_type,
            "treatment": treatment,
            "confidence": 0.6,  # Lower confidence for fallback
        }

    # =========================================================================
    # RULE-BASED PATTERN MATCHING (Fast, no API cost)
    # =========================================================================

    def _check_wotf_indicators(self, title_lower: str) -> Optional[str]:
        """Check for WOTF indicators in title. Returns matched indicator or None."""
        for indicator in WOTF_INDICATORS:
            if indicator in title_lower:
                return indicator
        return None

    def _check_non_wotf_indicators(self, title_lower: str) -> Optional[tuple]:
        """Check for non-WOTF indicators. Returns (tcg, indicator) or None."""
        for tcg, patterns in NON_WOTF_INDICATORS.items():
            for pattern in patterns:
                # Check if it's a regex pattern (starts with r')
                if pattern.startswith("r'") or "\\d" in pattern or pattern.startswith(r"mp\d"):
                    # Try regex match
                    try:
                        if re.search(pattern, title_lower):
                            return (tcg, pattern)
                    except re.error:
                        # Fall back to string match
                        if pattern in title_lower:
                            return (tcg, pattern)
                else:
                    # Simple string match
                    if pattern in title_lower:
                        return (tcg, pattern)
        return None

    def _extract_grading_info(self, title_lower: str) -> Optional[Dict[str, Any]]:
        """Extract grading information from title."""
        for service in GRADING_SERVICES:
            # Look for patterns like "PSA 10", "CGC 9.5", "BGS 10"
            pattern = rf"\b{service}\s*(\d+(?:\.\d+)?)\b"
            match = re.search(pattern, title_lower)
            if match:
                return {"service": service.upper(), "grade": float(match.group(1))}
        return None

    def _extract_condition(self, title_lower: str) -> Optional[str]:
        """Extract condition from title."""
        for keyword, condition in CONDITION_KEYWORDS.items():
            if keyword in title_lower:
                return condition
        return None

    def _extract_card_number(self, title_lower: str) -> Optional[str]:
        """Extract card number from title (e.g., '123/401')."""
        match = re.search(r"(\d{1,3})/(\d{3})", title_lower)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
        return None

    # =========================================================================
    # STRUCTURED EXTRACTION - Full data extraction from listings
    # =========================================================================

    def extract_structured_data(self, title: str, card_name: str, description: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract comprehensive structured data from a listing.

        This goes beyond validation to extract all useful information:
        - Card identification (name, set, number)
        - Treatment/variant
        - Condition and grading
        - Confidence in extraction

        Args:
            title: The listing title
            card_name: The expected WOTF card name
            description: Optional listing description

        Returns:
            Dict with:
                - card_name: str - Extracted or confirmed card name
                - set_name: Optional[str] - Detected set (Existence, Genesis)
                - card_number: Optional[str] - Card number if found
                - treatment: str - Detected treatment
                - condition: Optional[str] - Detected condition
                - is_graded: bool - Whether card is graded
                - grading_info: Optional[Dict] - Grading service and grade
                - is_wotf: bool - Validation result
                - confidence: float - Overall confidence
                - extraction_method: str - "rule_based" or "ai"
        """
        title_lower = title.lower()

        # Start with rule-based extraction
        result = {
            "card_name": card_name,
            "set_name": None,
            "card_number": self._extract_card_number(title_lower),
            "treatment": None,  # None = unknown, set only if detected
            "condition": self._extract_condition(title_lower),
            "is_graded": False,
            "grading_info": None,
            "is_wotf": True,
            "confidence": 0.5,
            "extraction_method": "rule_based",
        }

        # Detect set
        if "existence" in title_lower:
            result["set_name"] = "Existence"
        elif "genesis" in title_lower:
            result["set_name"] = "Genesis"

        # Detect treatment
        if "stonefoil" in title_lower or "stone foil" in title_lower or "stone-foil" in title_lower:
            result["treatment"] = "Stonefoil"
        elif "formless" in title_lower:
            result["treatment"] = "Formless Foil"
        elif "serialized" in title_lower or re.search(r"/\d{2,3}\b", title_lower):
            result["treatment"] = "OCM Serialized"
        elif "classic foil" in title_lower or ("foil" in title_lower and "formless" not in title_lower):
            result["treatment"] = "Classic Foil"
        elif "holo" in title_lower or "refractor" in title_lower:
            result["treatment"] = "Classic Foil"
        elif "prerelease" in title_lower:
            result["treatment"] = "Prerelease"
        elif "promo" in title_lower:
            result["treatment"] = "Promo"
        elif "classic paper" in title_lower or "paper" in title_lower:
            result["treatment"] = "Classic Paper"

        # Check grading
        grading = self._extract_grading_info(title_lower)
        if grading:
            result["is_graded"] = True
            result["grading_info"] = grading

        # Validate WOTF status
        validation = self.validate_wotf_listing(title, card_name)
        result["is_wotf"] = validation["is_wotf"]
        result["confidence"] = validation["confidence"]

        # Use AI for enhanced extraction if available and confidence is low
        if self.client and result["confidence"] < 0.7:
            ai_result = self._ai_extract_structured(title, card_name, description)
            if ai_result:
                result.update(ai_result)
                result["extraction_method"] = "ai"

        return result

    def _ai_extract_structured(
        self, title: str, card_name: str, description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Use AI to extract structured data from ambiguous listings."""
        if not self.client:
            return None

        try:
            self._metrics["ai_calls"] += 1

            prompt = f"""Extract structured data from this TCG listing:

Title: "{title}"
Expected Card: "{card_name}"
{f'Description: "{description[:300]}"' if description else ''}

Extract the following into JSON:
{{
  "card_name": "confirmed card name or best guess",
  "set_name": "Existence" or "Genesis" or null,
  "card_number": "XXX/401" format or null,
  "treatment": "Classic Paper" | "Classic Foil" | "Stonefoil" | "Formless Foil" | "OCM Serialized" | "Prerelease" | "Promo",
  "condition": "Mint" | "Near Mint" | "Excellent" | "Good" | "Light Play" | "Moderate Play" | "Heavy Play" | "Damaged" | null,
  "is_graded": true/false,
  "grading_info": {{"service": "PSA/CGC/BGS", "grade": 10}} or null,
  "is_wotf": true/false,
  "confidence": 0.0-1.0
}}

Rules:
- Only return WOTF-related treatments for single cards
- Card numbers for Existence set are in XXX/401 format
- If you can't determine something, use null
- Confidence should reflect certainty about all extracted fields"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at parsing Wonders of the First TCG listings. Extract accurate structured data.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=300,
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            print(f"AI structured extraction failed: {e}")
            return None

    # =========================================================================
    # WOTF VALIDATION - Determine if listing is for WOTF product
    # =========================================================================

    def validate_wotf_listing(self, title: str, card_name: str) -> Dict[str, Any]:
        """
        Validate if a listing is actually for a Wonders of the First card.

        Uses a tiered approach:
        1. Rule-based checks (fast, no API cost)
        2. Confidence tier calculation
        3. AI validation for ambiguous cases (when available)

        Args:
            title: The eBay listing title
            card_name: The WOTF card name we're searching for

        Returns:
            Dict with:
                - is_wotf: bool - True if this is likely a WOTF listing
                - confidence: float - 0-1 confidence score
                - reason: str - Explanation for the decision
                - detected_tcg: Optional[str] - If not WOTF, what TCG was detected
                - tier: str - Confidence tier (HIGH, MEDIUM, LOW)
        """
        title_lower = title.lower()

        # STEP 1: Check for strong WOTF indicators (instant accept)
        wotf_indicator = self._check_wotf_indicators(title_lower)
        if wotf_indicator:
            result = {
                "is_wotf": True,
                "confidence": 0.95,
                "reason": f"Contains WOTF indicator: '{wotf_indicator}'",
                "detected_tcg": "WOTF",
                "tier": "HIGH",
            }
            self._metrics["rule_based_accepts"] += 1
            self._log_decision(title, card_name, result, "rule_based")
            return result

        # STEP 2: Check for strong non-WOTF indicators (instant reject)
        non_wotf = self._check_non_wotf_indicators(title_lower)
        if non_wotf:
            tcg, indicator = non_wotf
            result = {
                "is_wotf": False,
                "confidence": 0.95,
                "reason": f"Contains {tcg} indicator: '{indicator}'",
                "detected_tcg": tcg,
                "tier": "HIGH",
            }
            self._metrics["rule_based_rejects"] += 1
            self._log_decision(title, card_name, result, "rule_based")
            return result

        # STEP 3: Calculate confidence tier for ambiguous cases
        confidence_tier = self._calculate_confidence_tier(
            title, card_name, has_wotf_indicator=False, has_non_wotf_indicator=False
        )

        # STEP 4: For medium-high confidence, accept without AI
        if confidence_tier["confidence"] >= 0.75:
            result = {
                "is_wotf": True,
                "confidence": confidence_tier["confidence"],
                "reason": confidence_tier["reason"],
                "detected_tcg": "WOTF",
                "tier": confidence_tier["tier"],
            }
            self._metrics["rule_based_accepts"] += 1
            self._log_decision(title, card_name, result, "rule_based")
            return result

        # STEP 5: For low confidence, use AI if available
        if not self.client:
            result = {
                "is_wotf": True,  # Default to accept if uncertain and no AI
                "confidence": confidence_tier["confidence"],
                "reason": f"{confidence_tier['reason']} (no AI available)",
                "detected_tcg": None,
                "tier": confidence_tier["tier"],
            }
            self._log_decision(title, card_name, result, "rule_based")
            return result

        # STEP 6: AI validation for ambiguous cases
        return self._ai_validate_listing(title, card_name)

    def _ai_validate_listing(self, title: str, card_name: str) -> Dict[str, Any]:
        """Use AI to validate ambiguous listings."""
        try:
            self._metrics["ai_calls"] += 1

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert at identifying trading card game products.
Determine if an eBay listing is for "Wonders of the First" (WOTF) TCG or another game.

**WOTF Identifiers:**
- Brand: "Wonders of the First", "WOTF"
- Sets: "Existence" (401 cards), "Genesis"
- Treatments: Classic Paper, Classic Foil, Stonefoil, Formless Foil, OCM Serialized
- Products: Collector Booster Box, Play Bundle, Booster Pack, Serialized Advantage
- Card Numbers: XXX/401 format

**NON-WOTF (REJECT):**
- Yu-Gi-Oh: MP22-EN, MGED-EN, Konami, specific card names (Dark Magician, Blue-Eyes, etc.)
- Dragon Ball Z: WA-XXX codes, DBZ CCG, character names (Goku, Vegeta, Frieza)
- Pokemon: Pokemon names, set names (Evolving Skies, Scarlet Violet)
- One Piece: OP01-OP08 codes, character names (Luffy, Zoro)
- MTG: Planeswalker, Wizards of the Coast
- Sports: Topps, Panini, league names (NBA, NFL)

Return JSON only.""",
                    },
                    {
                        "role": "user",
                        "content": f"""Is this listing for a WOTF card "{card_name}"?

Title: "{title}"

Return:
{{"is_wotf": true/false, "confidence": 0.0-1.0, "reason": "explanation", "detected_tcg": "WOTF/Yu-Gi-Oh/Pokemon/Dragon Ball Z/One Piece/MTG/Sports/Unknown"}}""",
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=200,
            )

            ai_result = json.loads(response.choices[0].message.content)

            result = {
                "is_wotf": ai_result.get("is_wotf", True),
                "confidence": ai_result.get("confidence", 0.7),
                "reason": ai_result.get("reason", "AI validation"),
                "detected_tcg": ai_result.get("detected_tcg", "Unknown"),
                "tier": "AI",
            }

            # Track metrics
            if result["is_wotf"]:
                self._metrics["ai_accepts"] += 1
            else:
                self._metrics["ai_rejects"] += 1

            self._log_decision(title, card_name, result, "ai")
            return result

        except Exception as e:
            print(f"AI validation failed: {e}")
            result = {
                "is_wotf": True,  # Default to accepting if AI fails
                "confidence": 0.5,
                "reason": f"AI validation failed: {str(e)}",
                "detected_tcg": None,
                "tier": "FALLBACK",
            }
            self._log_decision(title, card_name, result, "ai_error")
            return result


# Singleton instance
_extractor_instance: Optional[AIListingExtractor] = None


def get_ai_extractor() -> AIListingExtractor:
    """Get or create the AI extractor singleton."""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = AIListingExtractor()
    return _extractor_instance
