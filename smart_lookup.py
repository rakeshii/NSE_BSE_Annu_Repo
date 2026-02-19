from difflib import get_close_matches

COMMON = {
    "reliance": "RELIANCE",
    "tcs": "TCS",
    "tata consultancy services": "TCS",
    "infosys": "INFY",
    "hcl": "HCLTECH",
    "hcl technologies": "HCLTECH",
    "icici bank": "ICICIBANK",
    "hdfc bank": "HDFCBANK"
}

def get_symbol(name: str):
    key = name.lower().strip()

    if key in COMMON:
        return COMMON[key]

    match = get_close_matches(key, COMMON.keys(), n=1, cutoff=0.6)
    if match:
        return COMMON[match[0]]

    return name.upper()
