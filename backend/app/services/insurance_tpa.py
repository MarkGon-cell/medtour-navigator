"""
Hospital Insurance & TPA Network Resolver.

Addresses the critical medical tourism gap in India:
Foreign tourists arriving at hospitals expect their international insurance
(Allianz, Cigna, Bupa, GeoBlue, Aetna International) to work seamlessly.
In reality, Indian private hospitals operate through Third-Party Administrators (TPAs)
such as Medi Assist, Vidal Health, Paramount TPA, FHPL, and Heritage Health.

Large corporate/tertiary hospital networks (Apollo, Manipal, Fortis, Max, Lilavati,
Narayana, Medanta) maintain dedicated International Patient Desks with Direct Billing
and Cashless Tie-ups for international insurers. Smaller nursing homes and government
district hospitals operate strictly on a Cash/UPI Reimbursement basis.
"""

from typing import Dict, Any, List

# Prominent hospital chains known for accredited International Patient Desks & Cashless TPA networks
TIER_1_INTL_CHAINS = [
    "apollo", "fortis", "max healthcare", "manipal", "medanta",
    "lilavati", "hinduja", "kokilaben", "narayana", "artemis",
    "gleneagles", "aster", "sir ganga ram", "amrita", "yashoda",
    "continental", "ruby hall", "tata memorial"
]

MAJOR_GOVT_TERTIARY = [
    "aiims", "safdarjung", "pgimer", "jipmer", "civil hospital",
    "general hospital", "district hospital", "king george", "medical college"
]

def resolve_insurance_tpa_profile(hospital_name: str = "", category: str = "", accreditation: str = "") -> Dict[str, Any]:
    """
    Infers the real-world Insurance, TPA desk, and Deposit policy for a facility.
    Returns clear, honest guidance so a panicked tourist knows whether to bring
    their TPA card or be prepared with an upfront credit card deposit for reimbursement.
    """
    name_clean = (hospital_name or "").lower()
    cat_clean = (category or "").lower()
    acc_clean = (accreditation or "").lower()

    is_nabh_or_jci = "nabh" in acc_clean or "jci" in acc_clean or "joint commission" in acc_clean
    is_major_chain = any(chain in name_clean for chain in TIER_1_INTL_CHAINS)
    is_govt = any(govt in name_clean for govt in MAJOR_GOVT_TERTIARY) or "government" in cat_clean or "govt" in cat_clean

    if is_major_chain or is_nabh_or_jci:
        return {
            "cashless_available": True,
            "badge_label": "International Cashless & TPA Desk",
            "tier": "International Accredited",
            "accepted_tpas": ["Medi Assist", "Vidal Health", "Paramount", "FHPL"],
            "intl_insurers_supported": ["Allianz Care", "Cigna Global", "Bupa Global", "GeoBlue", "Aetna Intl"],
            "deposit_policy": "Cashless GOP (Guarantee of Payment) accepted at International Desk. For emergencies without immediate GOP, initial authorization deposit of INR 10,000 to INR 25,000 may be requested pending insurer clearance.",
            "instructions": "Present Passport and Travel Insurance Policy number at the International Patient / TPA desk for direct cashless billing.",
            "direct_billing": True
        }
    elif is_govt:
        return {
            "cashless_available": False,
            "badge_label": "Cash / Subsidized (Reimbursement Only)",
            "tier": "Government / Public Healthcare",
            "accepted_tpas": [],
            "intl_insurers_supported": ["Reimbursement standard receipt issued"],
            "deposit_policy": "Zero or nominal fees for Indian citizens; tourists pay government user fee charges upfront (Cash / UPI / Card).",
            "instructions": "Keep all stamped receipts and discharge summaries for overseas reimbursement claim filing.",
            "direct_billing": False
        }
    else:
        # Standard private clinic / local hospital
        return {
            "cashless_available": False,
            "badge_label": "Pay & Claim (Reimbursement)",
            "tier": "Private Clinic / Secondary Facility",
            "accepted_tpas": ["Select Domestic TPAs only"],
            "intl_insurers_supported": ["Reimbursement invoice provided via MedTour QR"],
            "deposit_policy": "Upfront payment required prior to admission. Credit Cards / Debit / UPI accepted. Scan MedTour discharge QR to generate insurance claim PDF.",
            "instructions": "Pay clinic directly, request detailed medical itemized invoice, and generate MedTour verified claim certificate for foreign insurer reimbursement.",
            "direct_billing": False
        }
