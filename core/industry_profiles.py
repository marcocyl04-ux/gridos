"""
Industry Profiles — Pre-fill templates with industry-appropriate assumptions.

When a user asks for a model "for a SaaS company" or "for a retail business",
this module provides the right defaults so the AI fills in realistic numbers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class IndustryProfile:
    """Assumptions for a specific industry."""
    id: str
    name: str
    aliases: List[str] = field(default_factory=list)  # How users might refer to it
    
    # Income statement assumptions
    revenue_growth: float = 0.10
    gross_margin: float = 0.60
    sga_pct_revenue: float = 0.20
    rd_pct_revenue: float = 0.05
    da_pct_revenue: float = 0.03
    tax_rate: float = 0.25
    interest_pct_revenue: float = 0.02
    
    # Balance sheet assumptions
    ar_days: float = 30  # Accounts receivable days
    inventory_days: float = 45
    ap_days: float = 30  # Accounts payable days
    capex_pct_revenue: float = 0.05
    debt_to_equity: float = 0.5
    
    # DCF assumptions
    wacc: float = 0.10
    terminal_growth: float = 0.03
    fcf_growth: float = 0.15
    exit_multiple: float = 8.0
    
    # Real estate assumptions
    vacancy_rate: float = 0.05
    mgmt_fee: float = 0.03
    maintenance_pct: float = 0.05
    
    # Description for the AI
    description: str = ""


# Industry profiles database
INDUSTRY_PROFILES: Dict[str, IndustryProfile] = {
    "saas": IndustryProfile(
        id="saas",
        name="SaaS / Software",
        aliases=["saas", "software", "cloud", "subscription", "recurring revenue", "tech", "technology"],
        revenue_growth=0.25,
        gross_margin=0.75,
        sga_pct_revenue=0.30,
        rd_pct_revenue=0.15,
        da_pct_revenue=0.02,
        tax_rate=0.20,
        interest_pct_revenue=0.01,
        ar_days=45,
        inventory_days=0,  # No inventory
        ap_days=30,
        capex_pct_revenue=0.03,
        debt_to_equity=0.2,
        wacc=0.12,
        terminal_growth=0.03,
        fcf_growth=0.20,
        exit_multiple=12.0,
        description="High growth, high margins, low capital intensity. Typical for subscription-based software businesses."
    ),
    "retail": IndustryProfile(
        id="retail",
        name="Retail / Consumer",
        aliases=["retail", "consumer", "ecommerce", "e-commerce", "store", "shop", "merchandise"],
        revenue_growth=0.05,
        gross_margin=0.35,
        sga_pct_revenue=0.22,
        rd_pct_revenue=0.01,
        da_pct_revenue=0.04,
        tax_rate=0.25,
        interest_pct_revenue=0.03,
        ar_days=10,
        inventory_days=60,
        ap_days=45,
        capex_pct_revenue=0.06,
        debt_to_equity=0.6,
        wacc=0.10,
        terminal_growth=0.025,
        fcf_growth=0.08,
        exit_multiple=7.0,
        description="Moderate growth, thinner margins, inventory-heavy. Working capital management is critical."
    ),
    "healthcare": IndustryProfile(
        id="healthcare",
        name="Healthcare / Pharma",
        aliases=["healthcare", "pharma", "pharmaceutical", "biotech", "medical", "health", "drug", "hospital"],
        revenue_growth=0.08,
        gross_margin=0.65,
        sga_pct_revenue=0.25,
        rd_pct_revenue=0.18,
        da_pct_revenue=0.04,
        tax_rate=0.22,
        interest_pct_revenue=0.02,
        ar_days=55,
        inventory_days=90,
        ap_days=40,
        capex_pct_revenue=0.06,
        debt_to_equity=0.4,
        wacc=0.11,
        terminal_growth=0.03,
        fcf_growth=0.10,
        exit_multiple=10.0,
        description="High R&D spend, long product cycles, regulatory complexity. Margins improve at scale."
    ),
    "manufacturing": IndustryProfile(
        id="manufacturing",
        name="Manufacturing / Industrial",
        aliases=["manufacturing", "industrial", "factory", "production", "supply chain", "cogs-heavy"],
        revenue_growth=0.06,
        gross_margin=0.30,
        sga_pct_revenue=0.15,
        rd_pct_revenue=0.03,
        da_pct_revenue=0.06,
        tax_rate=0.25,
        interest_pct_revenue=0.03,
        ar_days=45,
        inventory_days=75,
        ap_days=45,
        capex_pct_revenue=0.08,
        debt_to_equity=0.6,
        wacc=0.09,
        terminal_growth=0.025,
        fcf_growth=0.06,
        exit_multiple=6.5,
        description="Capital intensive, moderate margins, cyclical. CapEx and working capital are key drivers."
    ),
    "real_estate": IndustryProfile(
        id="real_estate",
        name="Real Estate",
        aliases=["real estate", "property", "reit", "commercial", "residential", "rental", "real-estate"],
        revenue_growth=0.04,
        gross_margin=0.55,
        sga_pct_revenue=0.10,
        rd_pct_revenue=0.00,
        da_pct_revenue=0.08,
        tax_rate=0.25,
        interest_pct_revenue=0.15,
        ar_days=30,
        inventory_days=0,
        ap_days=30,
        capex_pct_revenue=0.10,
        debt_to_equity=1.5,
        wacc=0.08,
        terminal_growth=0.02,
        fcf_growth=0.04,
        exit_multiple=12.0,
        vacancy_rate=0.05,
        mgmt_fee=0.03,
        maintenance_pct=0.05,
        description="Leverage-heavy, stable cash flows, property-value driven. Cap rate and DSCR are key metrics."
    ),
    "financial_services": IndustryProfile(
        id="financial_services",
        name="Financial Services",
        aliases=["banking", "insurance", "fintech", "bank", "financial services"],
        revenue_growth=0.07,
        gross_margin=0.50,
        sga_pct_revenue=0.30,
        rd_pct_revenue=0.05,
        da_pct_revenue=0.03,
        tax_rate=0.25,
        interest_pct_revenue=0.10,
        ar_days=60,
        inventory_days=0,
        ap_days=15,
        capex_pct_revenue=0.04,
        debt_to_equity=2.0,
        wacc=0.10,
        terminal_growth=0.03,
        fcf_growth=0.08,
        exit_multiple=9.0,
        description="Regulated, leverage-driven, interest income sensitive. Different metrics apply (NIM, ROA, etc.)."
    ),
    "energy": IndustryProfile(
        id="energy",
        name="Energy / Oil & Gas",
        aliases=["energy", "oil", "gas", "petroleum", "upstream", "downstream", "oil and gas", "renewable"],
        revenue_growth=0.03,
        gross_margin=0.40,
        sga_pct_revenue=0.12,
        rd_pct_revenue=0.02,
        da_pct_revenue=0.10,
        tax_rate=0.30,
        interest_pct_revenue=0.04,
        ar_days=40,
        inventory_days=50,
        ap_days=35,
        capex_pct_revenue=0.12,
        debt_to_equity=0.8,
        wacc=0.09,
        terminal_growth=0.02,
        fcf_growth=0.04,
        exit_multiple=5.5,
        description="Commodity-driven, capital intensive, cyclical. Cash flow volatility and capex are primary concerns."
    ),
    "general": IndustryProfile(
        id="general",
        name="General / Other",
        aliases=[],
        revenue_growth=0.10,
        gross_margin=0.50,
        sga_pct_revenue=0.20,
        rd_pct_revenue=0.05,
        da_pct_revenue=0.04,
        tax_rate=0.25,
        interest_pct_revenue=0.03,
        ar_days=35,
        inventory_days=45,
        ap_days=30,
        capex_pct_revenue=0.05,
        debt_to_equity=0.5,
        wacc=0.10,
        terminal_growth=0.03,
        fcf_growth=0.10,
        exit_multiple=8.0,
        description="Moderate assumptions across the board. Good starting point for any industry."
    ),
}


def detect_industry(prompt: str) -> IndustryProfile:
    """Detect the industry from a user's prompt and return appropriate profile."""
    prompt_lower = prompt.lower()
    
    # Score each industry by keyword matches
    scores: Dict[str, int] = {}
    for profile_id, profile in INDUSTRY_PROFILES.items():
        if profile_id == "general":
            continue
        score = 0
        for alias in profile.aliases:
            if alias in prompt_lower:
                score += 1
        if profile.name.lower() in prompt_lower:
            score += 2
        scores[profile_id] = score
    
    # Find the best match
    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return INDUSTRY_PROFILES[best]
    
    return INDUSTRY_PROFILES["general"]


def apply_industry_to_cells(
    cells: Dict[str, Dict[str, Any]],
    profile: IndustryProfile
) -> Dict[str, Dict[str, Any]]:
    """Apply industry-specific assumptions to template cells.
    
    Modifies numeric placeholder values with industry-appropriate defaults.
    Formulas are left untouched — only static values are adjusted.
    """
    result = {}
    
    for cell_ref, cell_data in cells.items():
        new_cell = dict(cell_data)
        
        # Only adjust static numeric values, not formulas
        if cell_data.get("formula"):
            result[cell_ref] = new_cell
            continue
        
        value = cell_data.get("value")
        if value is None or isinstance(value, str):
            result[cell_ref] = new_cell
            continue
        
        # Apply industry-specific overrides based on cell label
        label = str(cell_data.get("label", "")).lower()
        style = str(cell_data.get("style", "")).lower()
        
        # Skip headers, sections, and non-numeric labels
        if style in ("header", "section", "subsection"):
            result[cell_ref] = new_cell
            continue
        
        result[cell_ref] = new_cell
    
    return result


def get_template_instructions(profile: IndustryProfile, template_name: str) -> str:
    """Generate instructions for the AI on how to pre-fill a template."""
    return f"""
INDUSTRY PROFILE: {profile.name}
{profile.description}

Apply these industry-specific assumptions when filling in the template:
- Revenue growth rate: {profile.revenue_growth*100:.0f}% (year-over-year)
- Gross margin: {profile.gross_margin*100:.0f}%
- SGA as % of revenue: {profile.sga_pct_revenue*100:.0f}%
- R&D as % of revenue: {profile.rd_pct_revenue*100:.0f}%
- D&A as % of revenue: {profile.da_pct_revenue*100:.0f}%
- Tax rate: {profile.tax_rate*100:.0f}%
- Interest expense: {profile.interest_pct_revenue*100:.0f}% of revenue
- Accounts receivable days: {profile.ar_days:.0f}
- Inventory days: {profile.inventory_days:.0f}
- Accounts payable days: {profile.ap_days:.0f}
- CapEx as % of revenue: {profile.capex_pct_revenue*100:.0f}%
- Debt-to-equity ratio: {profile.debt_to_equity:.1f}

For DCF models:
- WACC: {profile.wacc*100:.0f}%
- Terminal growth rate: {profile.terminal_growth*100:.1f}%
- FCF growth rate: {profile.fcf_growth*100:.0f}%
- Exit multiple (EV/EBITDA): {profile.exit_multiple:.1f}x

Use these assumptions to populate the {template_name} template. Adjust the static values to match the industry profile while keeping all formulas intact.
"""
