"""
Blocklist loader for TCG contamination filtering.

Loads blocklist terms from blocklist.yaml and provides a flat list
of all terms for use in the scraper's _is_valid_match function.
"""

import os
from typing import List, Set
import yaml

# Path to the blocklist YAML file
BLOCKLIST_PATH = os.path.join(os.path.dirname(__file__), "blocklist.yaml")

# Cache for loaded blocklist
_blocklist_cache: Set[str] = set()
_blocklist_version: str = ""


def _flatten_yaml_values(data: dict) -> Set[str]:
    """Recursively flatten all string values from a nested dict/list structure."""
    terms = set()

    if isinstance(data, dict):
        for key, value in data.items():
            if key == "version":
                continue  # Skip version field
            if isinstance(value, str):
                terms.add(value.lower())
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        terms.add(item.lower())
                    elif isinstance(item, dict):
                        terms.update(_flatten_yaml_values(item))
            elif isinstance(value, dict):
                terms.update(_flatten_yaml_values(value))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                terms.add(item.lower())
            elif isinstance(item, dict):
                terms.update(_flatten_yaml_values(item))

    return terms


def load_blocklist(force_reload: bool = False) -> Set[str]:
    """
    Load the blocklist from YAML file.

    Args:
        force_reload: If True, reload from file even if cached.

    Returns:
        Set of lowercase blocklist terms.
    """
    global _blocklist_cache, _blocklist_version

    if _blocklist_cache and not force_reload:
        return _blocklist_cache

    try:
        with open(BLOCKLIST_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        _blocklist_version = data.get("version", "unknown")
        _blocklist_cache = _flatten_yaml_values(data)

        return _blocklist_cache
    except FileNotFoundError:
        print(f"WARNING: Blocklist file not found at {BLOCKLIST_PATH}")
        return set()
    except yaml.YAMLError as e:
        print(f"WARNING: Error parsing blocklist YAML: {e}")
        return set()


def get_blocklist_version() -> str:
    """Get the version of the currently loaded blocklist."""
    global _blocklist_version
    if not _blocklist_version:
        load_blocklist()
    return _blocklist_version


def get_blocklist_as_list() -> List[str]:
    """Get the blocklist as a sorted list (for debugging/testing)."""
    return sorted(load_blocklist())


def get_blocklist_stats() -> dict:
    """Get statistics about the loaded blocklist."""
    terms = load_blocklist()
    return {
        "version": get_blocklist_version(),
        "total_terms": len(terms),
        "sample_terms": sorted(list(terms))[:20],
    }


def is_blocked(title: str) -> bool:
    """
    Check if a title contains any blocklist term.

    Args:
        title: The listing title to check.

    Returns:
        True if the title contains a blocklist term, False otherwise.
    """
    title_lower = title.lower()
    blocklist = load_blocklist()

    for term in blocklist:
        if term in title_lower:
            return True

    return False


def get_blocking_terms(title: str) -> List[str]:
    """
    Get all blocklist terms found in a title (for debugging).

    Args:
        title: The listing title to check.

    Returns:
        List of blocklist terms found in the title.
    """
    title_lower = title.lower()
    blocklist = load_blocklist()

    found = []
    for term in blocklist:
        if term in title_lower:
            found.append(term)

    return found


# Pre-load the blocklist on module import
load_blocklist()
