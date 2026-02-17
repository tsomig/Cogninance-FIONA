"""
FRI Category Map — Snappi Transaction → FRI Role Taxonomy
==========================================================
Maps Snappi's core banking transaction types to FRI component roles.

This is a CONFIGURATION MODULE, not business logic. It changes when:
  - Snappi launches new products (BNPL, Flex, Cash Now variants)
  - New reward campaigns are created (seasonal cashback, partnerships)
  - Transaction type codes are restructured by the core banking system
  - Paymentology or DIAS integration adds new settlement categories

It does NOT change when FRI formulas, weights, or thresholds are modified.

Maintained by: George Tsomidis, PhD — University of Piraeus
Last validated: February 2026 against Snappi production transaction export
Reviewed by: [Snappi data team — pending]

Schema
------
Key:   (TransactionType: str, TransactionSubSubType: str)
Value: {
    'fri_role': str,           # FRI role classification (see ROLES below)
    'essential': bool,         # True if this is an unavoidable financial obligation
    'needs_enrichment': bool,  # True if MCC/beneficiary data would improve classification
}

FRI Roles
---------
STABILITY_INCOME              Income for CV calculation + Buffer numerator
STABILITY_BENEFIT             Government benefits (stable income variant)
BUFFER_ESSENTIAL              Confirmed essential spending (Buffer denominator)
BUFFER_DISCRETIONARY          Confirmed discretionary spending (coaching, not Buffer denom)
BUFFER_SPENDING_UNCLASSIFIED  Spending needing MCC to split essential/discretionary
MOMENTUM_DEBT_NEW             New debt creation (increases D_i,t)
MOMENTUM_DEBT_REPAY           Debt repayment (decreases D_i,t)
MOMENTUM_DEBT_COST            Interest/fees on debt (burden signal)
INTERNAL_TRANSFER             Own-account movement (excluded from FRI, net zero)
SYSTEM_OPERATION              Reversals, cancellations, reconciliation (excluded)
FEE_BANK                      Bank fees and commissions (essential obligation)
TAX_LEVY                      Taxes and levies (essential obligation)
REWARD_CASHBACK               Rewards/cashback (minor Buffer positive, not income)
"""


# ============================================================================
# ROLE SETS — used by the calculator for filtering
# ============================================================================

INCOME_ROLES = frozenset({'STABILITY_INCOME', 'STABILITY_BENEFIT'})

ESSENTIAL_SPENDING_ROLES = frozenset({
    'BUFFER_ESSENTIAL', 'FEE_BANK', 'TAX_LEVY', 'MOMENTUM_DEBT_REPAY',
})

UNCLASSIFIED_SPENDING_ROLES = frozenset({'BUFFER_SPENDING_UNCLASSIFIED'})

EXCLUDED_ROLES = frozenset({'INTERNAL_TRANSFER', 'SYSTEM_OPERATION'})

DEBT_INCREASE_ROLES = frozenset({'MOMENTUM_DEBT_NEW'})
DEBT_DECREASE_ROLES = frozenset({'MOMENTUM_DEBT_REPAY'})
DEBT_COST_ROLES = frozenset({'MOMENTUM_DEBT_COST'})


# ============================================================================
# PRIMARY MAP: (TransactionType, TransactionSubSubType) → FRI role
# ============================================================================

FRI_CATEGORY_MAP = {

    # ── INFLOWS: Income ──────────────────────────────────────────────────

    ('Receive Credit Transfer', 'SAVINGS DEPOSIT'): {
        'fri_role': 'STABILITY_INCOME',
        'essential': True,
        'needs_enrichment': True,  # pattern analysis to separate salary vs one-off
    },
    ('Receive Credit Transfer Instant', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'STABILITY_INCOME',
        'essential': True,
        'needs_enrichment': True,
    },
    ('Receive Credit Transfer Iris', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'STABILITY_INCOME',
        'essential': True,
        'needs_enrichment': True,
    },
    ('Receive Return Credit Transfer', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Card Top Up', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ TOP UP'): {
        'fri_role': 'STABILITY_INCOME',
        'essential': True,
        'needs_enrichment': True,  # could be internal transfer if user has another bank
    },

    # ── INFLOWS: Government Benefits ─────────────────────────────────────

    ('Deposit Transaction', 'ΕΦΟΔΙΑΣΜΟΣ ΛΟΓΑΡΙΑΣΜΩΝ YOUTH PASS'): {
        'fri_role': 'STABILITY_BENEFIT',
        'essential': True,
        'needs_enrichment': False,
    },

    # ── INFLOWS: Commercial / Vodafone CU ────────────────────────────────

    ('Deposit Transaction', 'ΕΦΟΔΙΑΣΜΟΣ ΛΟΓΑΡΙΑΣΜΩΝ CU'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Deposit Transaction', 'VODAFONE CU Cash Back'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },

    # ── INFLOWS: POS/eCommerce Refunds ───────────────────────────────────

    ('Deposit Transaction', 'ΚΑΤΑΘΕΣΗ ΤΑΜΙΕΥΤΗΡΙΟΥ ΑΠΟ ΑΓΟΡΕΣ POS- ECOMMERCE'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Deposit Transaction', 'ΚΑΤΑΘΕΣΗ ΤΑΜΙΕΥΤΗΡΙΟΥ ΓΙΑ POS'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Deposit Transaction', 'Μερική Επιστροφή Συναλλαγής'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Deposit Transaction', 'Επιστροφή απο Αμφισβήτηση (Chargeback)'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Deposit Transaction', 'SAVINGS DEPOSIT'): {
        'fri_role': 'INTERNAL_TRANSFER',
        'essential': False,
        'needs_enrichment': True,
    },
    ('Deposit Transaction', 'Loyalty Rewards'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Deposit Transaction', 'Contest - Cashback Rewards'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },

    # ── INFLOWS: BNPL/Flex Debt Disbursement (MOMENTUM) ──────────────────

    ('Create Bnpl Account', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'MOMENTUM_DEBT_NEW',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Create Flex Account', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'MOMENTUM_DEBT_NEW',
        'essential': False,
        'needs_enrichment': False,
    },

    # ── INFLOWS: BNPL/Flex Refunds (reduce debt) ─────────────────────────

    ('Full Refund On Bnpl Account', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'MOMENTUM_DEBT_REPAY',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Partial Refund On Bnpl Account', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'MOMENTUM_DEBT_REPAY',
        'essential': False,
        'needs_enrichment': False,
    },

    # ── INFLOWS: Rewards / Cashback (all via Pay Debt mechanism) ─────────

    ('Pay Debt', 'Black Friday Reward'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Pay Debt', 'Card test transaction'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Pay Debt', 'Cash Now Cashback'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Pay Debt', 'Cash Now Early Repayment Cash Back'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Pay Debt', 'Cash Now Late Fees Cashback'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Pay Debt', 'Christmas BNPL Cashback'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Pay Debt', 'Christmas Village Reward'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Pay Debt', 'IRIS Campaign Cashback'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ("Pay Debt", "January '26 BNPL CashBack"): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Pay Debt', 'Loyalty Rewards'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Pay Debt', 'Pay Later Cashback'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Pay Debt', 'Transportation Reward'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Pay Debt', 'VODAFONE CU Cash Back'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Pay Debt', 'Vodafone Loyalty Rewards'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Pay Debt', 'Welcome Offer Reward'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Pay Debt', 'You.gr Cashback'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Pay Debt', 'ΑΒ Offer Reward'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Pay Debt', 'ΕΞΟΦΛΗΣΗ ΔΙΑΦΟΡΩΝ ΔΑΠΑΝΩΝ EUR ΜΕ ΚΑΤΑΘΕΣΗ ΣΕ ΤΑΜΙΕΥΤΗΡΙΟ'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Pay Debt', 'ΕΦΟΔΙΑΣΜΟΣ ΛΟΓΑΡΙΑΣΜΩΝ CU'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Pay Debt', 'Συμψηφιστική Κατάθεση'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },

    # ── INFLOWS: Interest ────────────────────────────────────────────────

    ('Interest Transaction', 'Credit Interest'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },

    # ── INFLOWS: Internal Transfers ──────────────────────────────────────

    ('Savings Account Transfer', 'ΚΑΤΑΘΕΣΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'INTERNAL_TRANSFER',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Savings Transfers (To My Account)', 'ΚΑΤΑΘΕΣΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'INTERNAL_TRANSFER',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Transfer Transaction', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'INTERNAL_TRANSFER',
        'essential': False,
        'needs_enrichment': True,  # could be external → income
    },
    ('Transfer Transaction', 'Mastercard Cards Chargeback'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Savings Account Closing', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'INTERNAL_TRANSFER',
        'essential': False,
        'needs_enrichment': False,
    },

    # ── INFLOWS: System / Reconciliation ─────────────────────────────────

    ('Reconciliation Of Paymentology File', 'ΚΑΤΑΘΕΣΗ ΑΠΟ ΕΠΙΣΤΡΟΦΕΣ POS - eCommerce - ATM OFFLINE'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Reconciliation Of Chargeback File', 'Mastercard Cards Chargeback'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Full Reversal', 'Πλήρης Αντιλογισμός Ταμιευτηρίου'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Full Reversal', 'Ακυρωτικό Ταμιευτηρίου'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Reversal of BNPL Account', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },

    # ── INFLOWS: Cancellations ───────────────────────────────────────────

    ('Cancellation- Second Step', 'ΑΝΑΛΗΨΗ ΓΙΑ ΑΓΟΡΕΣ POS - eCommerce - ATM OFFLINE'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Cancellation- Second Step', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Cancellation- Second Step', 'ΠΡΟΜΗΘΕΙΑ ΑΠΟ ΚΙΝΗΣΗ ΚΕΦΑΛΑΙΩΝ'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Cancellation- Second Step', 'ΠΡΟΜΗΘΕΙΑ ΑΠΟ ΚΙΝΗΣΗ ΚΕΦΑΛΑΙΩΝ (INSTANT)'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Cancellation- Second Step', 'Συμψηφιστική Αναληψη'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },

    # ══════════════════════════════════════════════════════════════════════
    # OUTFLOWS
    # ══════════════════════════════════════════════════════════════════════

    # ── Consumer Spending (POS/ATM — needs MCC enrichment) ───────────────

    ('Withdrawal Transaction', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ ΓΙΑ POS'): {
        'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED',
        'essential': True,
        'needs_enrichment': True,  # CRITICAL: 39% of all outflows, needs MCC
    },
    ('Withdrawal Transaction', 'ΑΝΑΛΗΨΗ ΑΠΟ ATM'): {
        'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED',
        'essential': True,
        'needs_enrichment': True,  # cash = black box
    },
    ('Reconciliation Of Paymentology File', 'ΑΝΑΛΗΨΗ ΓΙΑ ΑΓΟΡΕΣ POS - eCommerce - ATM OFFLINE'): {
        'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED',
        'essential': True,
        'needs_enrichment': True,
    },
    ('Reconciliation Of Paymentology File', 'PAYMENTOLOGY RECON (DEBIT)'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },

    # ── Outgoing Transfers (potential rent/utilities/P2P) ────────────────

    ('Create Credit Transfer', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED',
        'essential': True,
        'needs_enrichment': True,  # beneficiary IBAN → rent/utility detection
    },
    ('Create Credit Transfer Instant', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED',
        'essential': True,
        'needs_enrichment': True,
    },
    ('Create Credit Transfer Iris', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED',
        'essential': True,
        'needs_enrichment': True,
    },

    # ── Transfer Commissions ─────────────────────────────────────────────

    ('Create Credit Transfer', 'ΠΡΟΜΗΘΕΙΑ ΑΠΟ ΚΙΝΗΣΗ ΚΕΦΑΛΑΙΩΝ'): {
        'fri_role': 'FEE_BANK',
        'essential': True,
        'needs_enrichment': False,
    },
    ('Create Credit Transfer', 'ΠΡΟΜΗΘΕΙΑ ΑΠΟ ΚΙΝΗΣΗ ΚΕΦΑΛΑΙΩΝ (INSTANT)'): {
        'fri_role': 'FEE_BANK',
        'essential': True,
        'needs_enrichment': False,
    },
    ('Create Credit Transfer Instant', 'ΠΡΟΜΗΘΕΙΑ ΑΠΟ ΚΙΝΗΣΗ ΚΕΦΑΛΑΙΩΝ (INSTANT)'): {
        'fri_role': 'FEE_BANK',
        'essential': True,
        'needs_enrichment': False,
    },
    ('Receive Credit Transfer Instant', 'ΠΡΟΜΗΘΕΙΑ ΑΠΟ ΚΙΝΗΣΗ ΚΕΦΑΛΑΙΩΝ (INSTANT)'): {
        'fri_role': 'FEE_BANK',
        'essential': True,
        'needs_enrichment': False,
    },

    # ── Debt Repayment (MOMENTUM positive) ──────────────────────────────

    ('Bnpl Account Payment', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'MOMENTUM_DEBT_REPAY',
        'essential': True,
        'needs_enrichment': False,
    },
    ('Payment Flex Account', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'MOMENTUM_DEBT_REPAY',
        'essential': True,
        'needs_enrichment': False,
    },

    # ── BNPL-financed Purchases ──────────────────────────────────────────

    ('Create Bnpl Account', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED',
        'essential': True,
        'needs_enrichment': True,  # MCC of underlying purchase unknown
    },

    # ── Product Payments (subscriptions/recurring) ───────────────────────

    ('Product Payment Credit Transfer', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED',
        'essential': True,
        'needs_enrichment': True,
    },
    ('Product Payment Credit Transfer Instant', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED',
        'essential': True,
        'needs_enrichment': True,
    },

    # ── Direct Debit (essential in Greek context) ────────────────────────

    ('Direct Debit Payment', 'ΠΑΓΙΕΣ ΕΝΤΟΛΕΣ DIAS CREDIT DDD'): {
        'fri_role': 'BUFFER_ESSENTIAL',
        'essential': True,
        'needs_enrichment': False,
    },

    # ── Debt Product Costs (MOMENTUM negative) ──────────────────────────

    ('Create Flex Account', 'Cash Now COMMISSION / ΠΡΟΜΗΘΕΙΑ ΔΗΜΙΟΥΡΓΙΑΣ Cash Now'): {
        'fri_role': 'MOMENTUM_DEBT_COST',
        'essential': True,
        'needs_enrichment': False,
    },
    ('Create Flex Account', 'FLEX COMMISSION / ΠΡΟΜΗΘΕΙΑ ΔΗΜΙΟΥΡΓΙΑΣ FLEX'): {
        'fri_role': 'MOMENTUM_DEBT_COST',
        'essential': True,
        'needs_enrichment': False,
    },
    ('Change Payment Date On Bnpl Account', 'COMMISSION RECEIVING SNOOZE'): {
        'fri_role': 'MOMENTUM_DEBT_COST',
        'essential': True,
        'needs_enrichment': False,
    },

    # ── BNPL Refund Processing ───────────────────────────────────────────

    ('Full Refund On Bnpl Account', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Partial Refund On Bnpl Account', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },

    # ── Tax ──────────────────────────────────────────────────────────────

    ('Interest Transaction', 'Interest Tax'): {
        'fri_role': 'TAX_LEVY',
        'essential': True,
        'needs_enrichment': False,
    },

    # ── Internal Transfers ───────────────────────────────────────────────

    ('Savings Account Transfer', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'INTERNAL_TRANSFER',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Savings Transfers (To My Account)', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'INTERNAL_TRANSFER',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Savings Account Closing', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'INTERNAL_TRANSFER',
        'essential': False,
        'needs_enrichment': False,
    },

    # ── Bank Fees ────────────────────────────────────────────────────────

    ('Charges For Card Issuance', 'COMMISSION RECEIVING CARD ISSUANCE'): {
        'fri_role': 'FEE_BANK',
        'essential': True,
        'needs_enrichment': False,
    },
    ('Withdrawal Transaction', 'COMMISSION RECEIVING ATM'): {
        'fri_role': 'FEE_BANK',
        'essential': True,
        'needs_enrichment': False,
    },
    ('Withdrawal Transaction', 'FEES RECEIVING ATM'): {
        'fri_role': 'FEE_BANK',
        'essential': True,
        'needs_enrichment': False,
    },

    # ── Discretionary ────────────────────────────────────────────────────

    ('Withdrawal Transaction', 'MANUAL ΕΞΕΡΧΟΜΕΝΟ ΕΜΒΑΣΜΑ TIPS'): {
        'fri_role': 'BUFFER_DISCRETIONARY',
        'essential': False,
        'needs_enrichment': False,
    },

    # ── Demand/Settlement ────────────────────────────────────────────────

    ('Pay Demand', 'Συμψηφιστική Αναληψη'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': True,
    },
    ('Return Credit Transfer', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },

    # ── Outflow Cancellations ────────────────────────────────────────────

    ('Cancellation- Second Step', 'Christmas BNPL Cashback'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ("Cancellation- Second Step", "January '26 BNPL CashBack"): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Cancellation- Second Step', 'Mastercard Cards Chargeback'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Cancellation- Second Step', 'Pay Later Cashback'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Cancellation- Second Step', 'ΚΑΤΑΘΕΣΗ ΑΠΟ ΕΠΙΣΤΡΟΦΕΣ POS - eCommerce - ATM OFFLINE'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Cancellation- Second Step', 'Συμψηφιστική Κατάθεση'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Reversal of BNPL Account', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Full Reversal', 'Ακυρωτικό Ταμιευτηρίου'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Full Reversal', 'Πλήρης Αντιλογισμός Ταμιευτηρίου'): {
        'fri_role': 'SYSTEM_OPERATION',
        'essential': False,
        'needs_enrichment': False,
    },

    # ══════════════════════════════════════════════════════════════════════
    # ZERO-SUM (currently inactive — monitored for activation)
    # ══════════════════════════════════════════════════════════════════════

    ('Interest Transaction', 'Interest Levy'): {
        'fri_role': 'TAX_LEVY',
        'essential': True,
        'needs_enrichment': False,
    },
    ('Interest Transaction', 'Debit Interest (Χρεωστικοί Τόκοι)'): {
        'fri_role': 'MOMENTUM_DEBT_COST',
        'essential': True,
        'needs_enrichment': False,
    },
    ('Savings Account Closing', 'ΠΙΣΤΩΤΙΚΟΙ ΤΟΚΟΙ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'REWARD_CASHBACK',
        'essential': False,
        'needs_enrichment': False,
    },
    ('Savings Account Closing', 'ΦΟΡΟΙ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'TAX_LEVY',
        'essential': True,
        'needs_enrichment': False,
    },
    ('Savings Account Closing', 'ΕΙΣΦΟΡΑ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'TAX_LEVY',
        'essential': True,
        'needs_enrichment': False,
    },
    ('Savings Account Closing', 'ΧΡΕΩΣΤΙΚΟΙ ΤΟΚΟΙ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'MOMENTUM_DEBT_COST',
        'essential': True,
        'needs_enrichment': False,
    },
    ('Charges For Card Issuance', 'COMMISSION RECEIVING'): {
        'fri_role': 'FEE_BANK',
        'essential': True,
        'needs_enrichment': False,
    },
}


# ============================================================================
# FALLBACK MAPS — used when exact (Type, SubSubType) key is not found
# ============================================================================

TRANSACTION_TYPE_FALLBACK = {
    'Receive Credit Transfer':        {'fri_role': 'STABILITY_INCOME',              'essential': True,  'needs_enrichment': True},
    'Receive Credit Transfer Instant': {'fri_role': 'STABILITY_INCOME',             'essential': True,  'needs_enrichment': True},
    'Receive Credit Transfer Iris':   {'fri_role': 'STABILITY_INCOME',              'essential': True,  'needs_enrichment': True},
    'Withdrawal Transaction':         {'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED',  'essential': True,  'needs_enrichment': True},
    'Deposit Transaction':            {'fri_role': 'REWARD_CASHBACK',               'essential': False, 'needs_enrichment': True},
    'Pay Debt':                       {'fri_role': 'REWARD_CASHBACK',               'essential': False, 'needs_enrichment': False},
    'Cancellation- Second Step':      {'fri_role': 'SYSTEM_OPERATION',              'essential': False, 'needs_enrichment': False},
    'Full Reversal':                  {'fri_role': 'SYSTEM_OPERATION',              'essential': False, 'needs_enrichment': False},
}

TRANSACTION_DESC_FALLBACK = {
    'Commission':                {'fri_role': 'FEE_BANK',          'essential': True,  'needs_enrichment': False},
    'Tax':                       {'fri_role': 'TAX_LEVY',          'essential': True,  'needs_enrichment': False},
    'Levy':                      {'fri_role': 'TAX_LEVY',          'essential': True,  'needs_enrichment': False},
    'Credit Interests':          {'fri_role': 'REWARD_CASHBACK',   'essential': False, 'needs_enrichment': False},
    'Debit Interests':           {'fri_role': 'MOMENTUM_DEBT_COST','essential': True,  'needs_enrichment': False},
    'Full Reversal':             {'fri_role': 'SYSTEM_OPERATION',  'essential': False, 'needs_enrichment': False},
    'Cancellation':              {'fri_role': 'SYSTEM_OPERATION',  'essential': False, 'needs_enrichment': False},
    'Savings Account Deposit':   {'fri_role': 'INTERNAL_TRANSFER', 'essential': False, 'needs_enrichment': False},
    'Savings Account Withrawal': {'fri_role': 'INTERNAL_TRANSFER', 'essential': False, 'needs_enrichment': False},
    'Expenses':                  {'fri_role': 'FEE_BANK',          'essential': True,  'needs_enrichment': False},
    'Credit Account':            {'fri_role': 'SYSTEM_OPERATION',  'essential': False, 'needs_enrichment': False},
}


# ============================================================================
# MCC ENRICHMENT TABLES (for Paymentology data)
# ============================================================================

ESSENTIAL_MCC_CODES = frozenset({
    # Groceries / Supermarkets
    '5411', '5422', '5441', '5451', '5462',
    # Utilities
    '4900', '4814', '4812', '4813',
    # Transportation (essential)
    '4111', '4112', '4121', '4131', '5541', '5542',
    # Healthcare
    '5912', '8011', '8021', '8031', '8041', '8042', '8043',
    '8049', '8050', '8062', '8071', '8099',
    # Insurance
    '6300',
    # Education
    '8211', '8220', '8241', '8244', '8249', '8299',
    # Housing-adjacent (repair/maintenance)
    '1520', '1711', '1731', '1740', '1750', '1761', '1771',
})

DISCRETIONARY_MCC_CODES = frozenset({
    # Dining
    '5812', '5813', '5814',
    # Entertainment
    '7832', '7922', '7929', '7933', '7941',
    '7991', '7992', '7993', '7994', '7995', '7996',
    # Shopping (non-essential)
    '5611', '5621', '5631', '5641', '5651', '5661', '5691', '5699',
    '5732', '5733', '5734', '5735',
    '5944', '5945', '5947',
    # Travel
    '4511', '4722', '7011', '7012',
    # Personal care (discretionary)
    '7230', '7297', '7298',
    # Digital goods / subscriptions
    '5815', '5816', '5817', '5818',
})


# ============================================================================
# VALIDATION UTILITIES
# ============================================================================

def validate_map_completeness(transactions_df: 'pd.DataFrame') -> dict:
    """
    Check how many transaction types in a real dataset are covered by the map.
    Returns coverage stats and list of unmapped types.
    """
    unmapped = []
    mapped = 0
    total = 0

    for _, row in transactions_df.iterrows():
        key = (row.get('TransactionType'), row.get('TransactionSubSubType'))
        total += 1
        if key in FRI_CATEGORY_MAP:
            mapped += 1
        else:
            unmapped.append(key)

    unique_unmapped = list(set(unmapped))

    return {
        'total_transactions': total,
        'mapped': mapped,
        'unmapped': len(unmapped),
        'coverage_rate': mapped / total if total > 0 else 0,
        'unique_unmapped_types': unique_unmapped,
    }


def get_map_summary() -> dict:
    """Return summary statistics of the current map."""
    from collections import Counter
    roles = Counter(v['fri_role'] for v in FRI_CATEGORY_MAP.values())
    enrichment_needed = sum(1 for v in FRI_CATEGORY_MAP.values() if v['needs_enrichment'])

    return {
        'total_entries': len(FRI_CATEGORY_MAP),
        'role_distribution': dict(roles),
        'entries_needing_enrichment': enrichment_needed,
        'entries_production_ready': len(FRI_CATEGORY_MAP) - enrichment_needed,
    }
