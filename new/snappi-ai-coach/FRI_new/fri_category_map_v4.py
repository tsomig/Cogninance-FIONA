"""
FRI Category Map v4 — Simplified Direction-Based Taxonomy
==========================================================
Maps Snappi transactions to FRI roles using ONLY:
  - TransactionType (the label)
  - Direction (inflow / outflow / neutral)

Direction is derived from the raw data:
  - CreditAmountLC > 0  → 'inflow'
  - DebitAmountLC  > 0  → 'outflow'
  - otherwise           → 'neutral'  (zero-amount or negative reversal)

This eliminates the need for TransactionSubSubType entirely, reducing
the map from 178 entries (v3) to ~45 entries.

Trade-offs vs v3
-----------------
Some TransactionTypes carry multiple semantic roles within the same
direction. In those cases the DOMINANT role (by €-volume) is used:

  Deposit Transaction (inflow):
    93% Youth Pass (STABILITY_BENEFIT) + 7% cashback (REWARD_CASHBACK)
    → STABILITY_BENEFIT.  Cashback treated as benefit = minor income inflation.

  Withdrawal Transaction (outflow):
    99%+ POS/ATM spending + <1% ATM fees + <0.1% tips
    → BUFFER_SPENDING_UNCLASSIFIED.  ATM fees absorbed into spending bucket.

  Create Credit Transfer * (outflow):
    99%+ transfers + <0.1% commissions
    → BUFFER_SPENDING_UNCLASSIFIED.  Commissions absorbed into spending.

Maintained by: George Tsomidis, PhD — University of Piraeus
Created: February 2026
"""


# ============================================================================
# ROLE SETS — unchanged from v3, used by the calculator for filtering
# ============================================================================

INCOME_ROLES = frozenset({'STABILITY_INCOME', 'STABILITY_BENEFIT'})

ESSENTIAL_SPENDING_ROLES = frozenset({
    'BUFFER_ESSENTIAL', 'FEE_BANK', 'TAX_LEVY',
})

DEBT_SERVICE_ROLES = frozenset({'MOMENTUM_DEBT_REPAY'})

UNCLASSIFIED_SPENDING_ROLES = frozenset({'BUFFER_SPENDING_UNCLASSIFIED'})

EXCLUDED_ROLES = frozenset({'INTERNAL_TRANSFER', 'SYSTEM_OPERATION'})

DEBT_INCREASE_ROLES = frozenset({'MOMENTUM_DEBT_NEW'})
DEBT_DECREASE_ROLES = frozenset({'MOMENTUM_DEBT_REPAY'})
DEBT_COST_ROLES = frozenset({'MOMENTUM_DEBT_COST'})

REWARD_ROLES = frozenset({'REWARD_CASHBACK'})


# ============================================================================
# DIRECTION-BASED MAP: (TransactionType, direction) → FRI role
# ============================================================================
# direction: 'inflow' | 'outflow' | 'neutral'

FRI_CATEGORY_MAP = {

    # ── Income ───────────────────────────────────────────────────────────

    ('Receive Credit Transfer', 'inflow'):          'STABILITY_INCOME',
    ('Receive Credit Transfer Instant', 'inflow'):  'STABILITY_INCOME',
    ('Receive Credit Transfer Iris', 'inflow'):     'STABILITY_INCOME',
    ('Card Top Up', 'inflow'):                      'STABILITY_INCOME',

    # ── Government Benefits + Cashback (93% Youth Pass by €-volume) ──────

    ('Deposit Transaction', 'inflow'):              'STABILITY_BENEFIT',

    # ── Rewards / Cashback ───────────────────────────────────────────────

    ('Pay Debt', 'inflow'):                         'REWARD_CASHBACK',
    ('Interest Transaction', 'inflow'):             'REWARD_CASHBACK',

    # ── Debt Disbursement (new debt) ─────────────────────────────────────

    ('Create Bnpl Account', 'inflow'):              'MOMENTUM_DEBT_NEW',
    ('Create Flex Account', 'inflow'):              'MOMENTUM_DEBT_NEW',

    # ── Debt Repayment ───────────────────────────────────────────────────

    ('Full Refund On Bnpl Account', 'inflow'):      'MOMENTUM_DEBT_REPAY',
    ('Partial Refund On Bnpl Account', 'inflow'):   'MOMENTUM_DEBT_REPAY',
    ('Bnpl Account Payment', 'outflow'):            'MOMENTUM_DEBT_REPAY',
    ('Payment Flex Account', 'outflow'):            'MOMENTUM_DEBT_REPAY',

    # ── Debt Costs ───────────────────────────────────────────────────────

    ('Create Flex Account', 'outflow'):             'MOMENTUM_DEBT_COST',
    ('Change Payment Date On Bnpl Account', 'outflow'): 'MOMENTUM_DEBT_COST',
    ('Interest Transaction', 'outflow'):            'TAX_LEVY',

    # ── Consumer Spending ────────────────────────────────────────────────

    ('Withdrawal Transaction', 'outflow'):          'BUFFER_SPENDING_UNCLASSIFIED',
    ('Create Credit Transfer', 'outflow'):          'BUFFER_SPENDING_UNCLASSIFIED',
    ('Create Credit Transfer Instant', 'outflow'):  'BUFFER_SPENDING_UNCLASSIFIED',
    ('Create Credit Transfer Iris', 'outflow'):     'BUFFER_SPENDING_UNCLASSIFIED',
    ('Product Payment Credit Transfer', 'outflow'): 'BUFFER_SPENDING_UNCLASSIFIED',
    ('Product Payment Credit Transfer Instant', 'outflow'): 'BUFFER_SPENDING_UNCLASSIFIED',
    ('Create Bnpl Account', 'outflow'):             'BUFFER_SPENDING_UNCLASSIFIED',
    ('Reconciliation Of Paymentology File', 'outflow'): 'BUFFER_SPENDING_UNCLASSIFIED',

    # ── Essential Spending ───────────────────────────────────────────────

    ('Direct Debit Payment', 'outflow'):            'BUFFER_ESSENTIAL',

    # ── Bank Fees ────────────────────────────────────────────────────────

    ('Charges For Card Issuance', 'outflow'):       'FEE_BANK',
    ('Receive Credit Transfer Instant', 'outflow'): 'FEE_BANK',

    # ── Internal Transfers ───────────────────────────────────────────────

    ('Savings Account Transfer', 'inflow'):         'INTERNAL_TRANSFER',
    ('Savings Account Transfer', 'outflow'):        'INTERNAL_TRANSFER',
    ('Savings Transfers (To My Account)', 'inflow'): 'INTERNAL_TRANSFER',
    ('Savings Transfers (To My Account)', 'outflow'): 'INTERNAL_TRANSFER',
    ('Savings Account Closing', 'inflow'):          'INTERNAL_TRANSFER',
    ('Savings Account Closing', 'outflow'):         'INTERNAL_TRANSFER',
    ('Transfer Transaction', 'inflow'):             'INTERNAL_TRANSFER',

    # ── System Operations ────────────────────────────────────────────────

    ('Receive Return Credit Transfer', 'inflow'):   'SYSTEM_OPERATION',
    ('Reconciliation Of Chargeback File', 'inflow'): 'SYSTEM_OPERATION',
    ('Reconciliation Of Paymentology File', 'inflow'): 'SYSTEM_OPERATION',
    ('Full Refund On Bnpl Account', 'outflow'):     'SYSTEM_OPERATION',
    ('Partial Refund On Bnpl Account', 'outflow'):  'SYSTEM_OPERATION',
    ('Pay Demand', 'outflow'):                      'SYSTEM_OPERATION',
    ('Return Credit Transfer', 'outflow'):          'SYSTEM_OPERATION',
    ('Reversal of BNPL Account', 'inflow'):         'SYSTEM_OPERATION',
    ('Reversal of BNPL Account', 'outflow'):        'SYSTEM_OPERATION',
}

# ── Default role for unmapped (Type, direction) combinations ─────────
# Neutral direction (zero-amount) and any unknown TransactionTypes
# default to SYSTEM_OPERATION — safe because it's excluded from all
# FRI formula components.
DEFAULT_ROLE = 'SYSTEM_OPERATION'


# ============================================================================
# CLASSIFIER FUNCTION
# ============================================================================

def classify_transaction(tx_type: str, credit: float, debit: float) -> str:
    """
    Classify a single transaction into an FRI role.

    Parameters
    ----------
    tx_type : str
        TransactionType label.
    credit : float
        CreditAmountLC value.
    debit : float
        DebitAmountLC value.

    Returns
    -------
    str
        FRI role string.
    """
    if credit > 0:
        direction = 'inflow'
    elif debit > 0:
        direction = 'outflow'
    else:
        direction = 'neutral'

    return FRI_CATEGORY_MAP.get((tx_type, direction), DEFAULT_ROLE)


# ============================================================================
# VALIDATION UTILITIES
# ============================================================================

def validate_map_completeness(transactions_df: 'pd.DataFrame') -> dict:
    """
    Check how many transactions in a real dataset are covered by the map.
    Returns coverage stats and list of unmapped (TransactionType, direction) pairs.
    """
    mapped = 0
    unmapped = []
    total = 0

    for _, row in transactions_df.iterrows():
        credit = row.get('CreditAmountLC', 0) or 0
        debit = row.get('DebitAmountLC', 0) or 0

        if credit > 0:
            direction = 'inflow'
        elif debit > 0:
            direction = 'outflow'
        else:
            direction = 'neutral'

        key = (row.get('TransactionType'), direction)
        total += 1

        if key in FRI_CATEGORY_MAP:
            mapped += 1
        else:
            unmapped.append(key)

    unique_unmapped = sorted(set(unmapped))

    return {
        'total_transactions': total,
        'mapped': mapped,
        'unmapped': len(unmapped),
        'coverage_rate': mapped / total if total > 0 else 0,
        'unique_unmapped_pairs': unique_unmapped,
        'default_role_applied': DEFAULT_ROLE,
    }


def get_map_summary() -> dict:
    """Return summary statistics of the current map."""
    from collections import Counter
    roles = Counter(v for v in FRI_CATEGORY_MAP.values())
    directions = Counter(k[1] for k in FRI_CATEGORY_MAP.keys())

    return {
        'total_entries': len(FRI_CATEGORY_MAP),
        'role_distribution': dict(roles),
        'direction_distribution': dict(directions),
    }
