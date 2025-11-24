"""
AI-powered listing data extraction service.

Uses GPT-5-nano via OpenRouter to intelligently parse eBay listings for:
- Quantity detection (e.g., "3x", "Lot of 5", "Bundle")
- Product type classification (Single, Box, Pack, Lot)
- Condition detection (Sealed, Unsealed, Near Mint, etc.)
- Treatment identification (Foil, Serialized, Standard)
"""

from typing import Optional, Dict, Any, List
from openai import OpenAI
import json
import re
import os
import hashlib


class AIListingExtractor:
    """AI-powered listing data extractor using GPT-5-nano."""

    def __init__(self):
        """Initialize OpenRouter client with GPT-5-nano."""
        api_key = os.getenv("OPENROUTER_API_KEY")

        # Title hash cache to prevent redundant AI calls for same titles
        self._title_cache = {}

        if not api_key:
            print("WARNING: OPENROUTER_API_KEY not set, AI extraction will fallback to rule-based")
            self.client = None
            self.model = None
        else:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key
            )
            # Using gpt-4o-mini instead of gpt-5-nano (which returns empty responses)
            self.model = "openai/gpt-4o-mini"

    def _hash_title(self, title: str) -> str:
        """Generate SHA256 hash of normalized title for cache key."""
        normalized = title.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()

    def extract_listing_data(
        self,
        title: str,
        description: Optional[str] = None,
        price: Optional[float] = None
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
        if title_hash in self._title_cache:
            return self._title_cache[title_hash]

        # If no API key configured, use fallback immediately
        if not self.client:
            return self._fallback_extraction(title, description)

        prompt = self._build_extraction_prompt(title, description, price)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert at parsing TCG/CCG marketplace listings.
Extract structured data from listings for 'Wonders of the First' trading card game.
Always return valid JSON matching the schema exactly."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # Low temp for consistent extraction
                max_tokens=200
            )

            # Parse JSON response
            extracted = json.loads(response.choices[0].message.content)

            # Validate and set defaults
            result = {
                "quantity": extracted.get("quantity", 1),
                "product_type": extracted.get("product_type", "Single"),
                "condition": extracted.get("condition"),
                "treatment": extracted.get("treatment", "Classic Paper"),
                "confidence": extracted.get("confidence", 0.8)
            }

            # Cache the result before returning
            self._title_cache[title_hash] = result
            return result

        except Exception as e:
            print(f"AI extraction failed: {e}, using fallback")
            fallback_result = self._fallback_extraction(title, description)
            # Cache fallback to avoid repeated failed API calls for same title
            self._title_cache[title_hash] = fallback_result
            return fallback_result

    def extract_batch(
        self,
        listings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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

            if title_hash in self._title_cache:
                results.append(self._title_cache[title_hash])
            else:
                results.append(None)  # Placeholder
                uncached_indices.append(i)
                uncached_listings.append(listing)

        # If all cached, return early
        if not uncached_listings:
            return results

        # If no API key, use fallback for uncached
        if not self.client:
            for i, listing in zip(uncached_indices, uncached_listings):
                fallback = self._fallback_extraction(
                    listing.get("title", ""),
                    listing.get("description")
                )
                results[i] = fallback
                title_hash = self._hash_title(listing.get("title", ""))
                self._title_cache[title_hash] = fallback
            return results

        # Extract uncached listings in batch
        try:
            batch_prompt = self._build_batch_extraction_prompt(uncached_listings)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert at parsing TCG/CCG marketplace listings.
Extract structured data from listings for 'Wonders of the First' trading card game.
Always return valid JSON matching the schema exactly."""
                    },
                    {
                        "role": "user",
                        "content": batch_prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=2000  # Higher limit for batch processing
            )

            # Parse batch JSON response
            batch_data = json.loads(response.choices[0].message.content)
            extractions = batch_data.get("listings", [])

            # Map extractions back to results
            for i, extraction_idx in enumerate(uncached_indices):
                if i < len(extractions):
                    extracted = extractions[i]
                    result = {
                        "quantity": extracted.get("quantity", 1),
                        "product_type": extracted.get("product_type", "Single"),
                        "condition": extracted.get("condition"),
                        "treatment": extracted.get("treatment", "Classic Paper"),
                        "confidence": extracted.get("confidence", 0.8)
                    }
                    results[extraction_idx] = result

                    # Cache the result
                    title_hash = self._hash_title(uncached_listings[i].get("title", ""))
                    self._title_cache[title_hash] = result
                else:
                    # Fallback if extraction missing
                    listing = uncached_listings[i]
                    fallback = self._fallback_extraction(
                        listing.get("title", ""),
                        listing.get("description")
                    )
                    results[extraction_idx] = fallback
                    title_hash = self._hash_title(listing.get("title", ""))
                    self._title_cache[title_hash] = fallback

        except Exception as e:
            print(f"Batch AI extraction failed: {e}, using fallback for uncached items")
            # Use fallback for all uncached
            for i, listing in zip(uncached_indices, uncached_listings):
                fallback = self._fallback_extraction(
                    listing.get("title", ""),
                    listing.get("description")
                )
                results[i] = fallback
                title_hash = self._hash_title(listing.get("title", ""))
                self._title_cache[title_hash] = fallback

        return results

    def _build_batch_extraction_prompt(
        self,
        listings: List[Dict[str, Any]]
    ) -> str:
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
      "product_type": <"Single" | "Box" | "Pack" | "Lot">,
      "condition": <"Sealed" | "Unsealed" | null (for singles)>,
      "treatment": <"Classic Paper" | "Classic Foil" | "Stonefoil" | "Formless Foil" | "OCM Serialized" | "Prerelease" | "Promo" | "Proof/Sample">,
      "confidence": <0.0-1.0, your confidence in this extraction>
    }},
    ... (one entry per listing in order)
  ]
}}

**Rules**:
- "Booster Box" = product_type: "Box", quantity: 24 (typical), condition: "Sealed"
- "Collector Box" = product_type: "Box", quantity: variable, condition: "Sealed"
- "Booster Pack" = product_type: "Pack", quantity: 1, condition: "Sealed"
- "Lot of X" or "X Cards" = product_type: "Lot", quantity: X
- Single cards = product_type: "Single", quantity: 1 (unless "3x Name" or similar)
- If title says "3x" or "Lot of 5", set quantity accordingly
- Foil/Serialized should be in treatment, not condition
- Confidence should be lower if information is ambiguous

Return ONLY valid JSON with a "listings" array containing {len(listings)} entries in order, no markdown or extra text."""

    def _build_extraction_prompt(
        self,
        title: str,
        description: Optional[str],
        price: Optional[float]
    ) -> str:
        """Build the extraction prompt for the AI."""
        return f"""Extract listing data from this TCG product listing:

**Title**: {title}
{f"**Description**: {description[:500]}" if description else ""}
{f"**Price**: ${price}" if price else ""}

Extract the following into JSON format:
{{
  "quantity": <number of items being sold, e.g., 1, 3, 24, 36>,
  "product_type": <"Single" | "Box" | "Pack" | "Lot">,
  "condition": <"Sealed" | "Unsealed" | null (for singles)>,
  "treatment": <"Classic Paper" | "Classic Foil" | "Stonefoil" | "Formless Foil" | "OCM Serialized" | "Prerelease" | "Promo" | "Proof/Sample">,
  "confidence": <0.0-1.0, your confidence in this extraction>
}}

**Rules**:
- "Booster Box" = product_type: "Box", quantity: 24 (typical), condition: "Sealed"
- "Collector Box" = product_type: "Box", quantity: variable, condition: "Sealed"
- "Booster Pack" = product_type: "Pack", quantity: 1, condition: "Sealed"
- "Lot of X" or "X Cards" = product_type: "Lot", quantity: X
- Single cards = product_type: "Single", quantity: 1 (unless "3x Name" or similar)
- If title says "3x" or "Lot of 5", set quantity accordingly
- Foil/Serialized should be in treatment, not condition
- Confidence should be lower if information is ambiguous

Return ONLY valid JSON, no markdown or extra text."""

    def _fallback_extraction(
        self,
        title: str,
        description: Optional[str]
    ) -> Dict[str, Any]:
        """Fallback rule-based extraction if AI fails."""
        title_lower = title.lower()

        # Detect quantity
        quantity = 1
        quantity_match = re.search(r'(\d+)x|lot of (\d+)|bundle (\d+)', title_lower)
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

        # Detect condition
        condition = None
        if product_type in ["Box", "Pack"]:
            if "sealed" in title_lower or "factory sealed" in title_lower:
                condition = "Sealed"
            elif "opened" in title_lower or "unsealed" in title_lower:
                condition = "Unsealed"

        # Detect treatment
        treatment = "Classic Paper"
        if "foil" in title_lower and "stone" in title_lower:
            treatment = "Stonefoil"
        elif "foil" in title_lower and "formless" in title_lower:
            treatment = "Formless Foil"
        elif "foil" in title_lower:
            treatment = "Classic Foil"
        elif "serialized" in title_lower:
            treatment = "OCM Serialized"
        elif "prerelease" in title_lower:
            treatment = "Prerelease"
        elif "promo" in title_lower:
            treatment = "Promo"
        elif "proof" in title_lower or "sample" in title_lower:
            treatment = "Proof/Sample"

        return {
            "quantity": quantity,
            "product_type": product_type,
            "condition": condition,
            "treatment": treatment,
            "confidence": 0.6  # Lower confidence for fallback
        }


# Singleton instance
_extractor_instance: Optional[AIListingExtractor] = None


def get_ai_extractor() -> AIListingExtractor:
    """Get or create the AI extractor singleton."""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = AIListingExtractor()
    return _extractor_instance
