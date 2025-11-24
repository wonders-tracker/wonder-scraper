"""
AI-powered listing data extraction service.

Uses GPT-5-nano via OpenRouter to intelligently parse eBay listings for:
- Quantity detection (e.g., "3x", "Lot of 5", "Bundle")
- Product type classification (Single, Box, Pack, Lot)
- Condition detection (Sealed, Unsealed, Near Mint, etc.)
- Treatment identification (Foil, Serialized, Standard)
"""

from typing import Optional, Dict, Any
from openai import OpenAI
import json
import re


class AIListingExtractor:
    """AI-powered listing data extractor using GPT-5-nano."""

    def __init__(self):
        """Initialize OpenRouter client with GPT-5-nano."""
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key="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"
        )
        self.model = "openai/gpt-5-nano"

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
            return {
                "quantity": extracted.get("quantity", 1),
                "product_type": extracted.get("product_type", "Single"),
                "condition": extracted.get("condition"),
                "treatment": extracted.get("treatment", "Classic Paper"),
                "confidence": extracted.get("confidence", 0.8)
            }

        except Exception as e:
            print(f"AI extraction failed: {e}, using fallback")
            return self._fallback_extraction(title, description)

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
