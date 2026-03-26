import re

def normalize_drug_name(raw_name):
    """
    Standardizes drug names across different vocabularies (OMOP, MIMIC, PubMed)
    to ensure they resolve to the exact same canonical `lowercase_name` node in Neo4j.
    
    Transforms things like:
        "vancomycin 5 MG/ML Injection [Tyzavan]" -> "vancomycin"
        "Sodium Chloride 0.9%  Flush" -> "sodium chloride"
        "Aspirin 81 mg oral tablet" -> "aspirin"
    """
    if not isinstance(raw_name, str):
        return ""
        
    name = raw_name.lower().strip()
    
    # 1. Remove bracketed brand names e.g. [Tyzavan]
    name = re.sub(r'\[.*?\]', '', name)
    
    # 2. Remove common dosages (mg, ml, mcg, g, %, etc) and anything following them
    # This is an aggressive cutoff to drop formulations from OMOP
    match = re.search(r'\b(\d+(\.\d+)?\s*(mg|ml|mcg|g|%|iu|meq|unit|units|hr|cm))\b', name)
    if match:
        name = name[:match.start()]
        
    # 3. Strip common form/route words and salt suffixes
    forms = [
        r"injection", r"tablet", r"oral", r"flush", r"vial", r"bag", r"capsule", r"syrup", 
        r"solution", r"suspension", r"cream", r"ointment", r"iv", r"po", r"topical",
        r"product", r"liquid", r"pill", r"suppository", r"disintegrating", r"syringe", 
        r"prefilled", r"film", r"effervescent", r"extended release", r"delayed release", 
        r"immediate release", r"injectable", r"hydrochloride", r"anhydrous", r"hcl",
        r"acetate", r"sulfate", r"citrate", r"bismuth", r"tartrate", r"bromide", r"mesylate",
        r"maleate", r"succinate", r"phosphate", r"odt", r"release", r"delayed", r"extended",
        r"immediate", r"chewable", r"sublingual", r"inhalation", r"nasal", r"patch", r"gel",
        r"lotion", r"shampoo", r"spray", r"drop", r"drops", r"enema", r"kit", r"pack", r"pen",
        r"cartridge", r"base", r"salt"
    ]
    for form in forms:
        name = re.sub(rf'\b{form}\b', '', name)
        
    # 4. Final trim of leftover whitespace and punctuation
    name = re.sub(r'[^a-z0-9\s-]', ' ', name)
    name = " ".join(name.split())
    
    return name

# Quick test if run directly
if __name__ == "__main__":
    tests = [
        "vancomycin 5 MG/ML Injection [Tyzavan]",
        "Sodium Chloride 0.9%  Flush",
        "Aspirin 81 mg oral tablet",
        "Lorazepam",
        "Insulin Human, Regular 100 unit/mL"
    ]
    print("Normalizer Tests:")
    for t in tests:
        print(f"  {t:<40} -> {normalize_drug_name(t)}")
