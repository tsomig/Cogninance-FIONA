"""
Financial Resilience Index (FRI) Calculator — Snappi Production Engine
======================================================================
Processes raw Snappi core banking transactions through the FRI Category Map
to compute Buffer (45%), Stability (30%), and Momentum (25%) components.

Input: pandas DataFrame with Snappi's transaction schema:
    - transaction_date (datetime)
    - TransactionType (str)
    - TransactionSubSubType (str)
    - CreditAmountLC (float)  — positive = money in
    - DebitAmountLC (float)   — positive = money out
    - balance_after (float)   — optional, account balance post-transaction
    - mcc_code (str)          — optional, Paymentology MCC enrichment
    - merchant_name (str)     — optional, Paymentology merchant enrichment
    - beneficiary_iban (str)  — optional, for transfer classification

Author: George Tsomidis, PhD — University of Piraeus
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# FRI CATEGORY MAP — derived from Snappi core banking transaction taxonomy
# ============================================================================
# Each key: (TransactionType, TransactionSubSubType)
# Each value: role, component, essential flag, needs MCC enrichment
#
# FRI Roles:
#   STABILITY_INCOME        → Stability CV calc + Buffer numerator
#   STABILITY_BENEFIT       → Government benefits (stable income variant)
#   BUFFER_ESSENTIAL        → Essential spending (Buffer denominator)
#   BUFFER_DISCRETIONARY    → Discretionary spending (coaching, not Buffer denom)
#   BUFFER_SPENDING_UNCLASSIFIED → Needs MCC to split essential/discretionary
#   MOMENTUM_DEBT_NEW       → New debt creation (increases D_i,t)
#   MOMENTUM_DEBT_REPAY     → Debt repayment (decreases D_i,t)
#   MOMENTUM_DEBT_COST      → Interest/fees on debt (burden signal)
#   INTERNAL_TRANSFER       → Own-account movement (excluded, net zero)
#   SYSTEM_OPERATION        → Reversals, reconciliation (excluded)
#   FEE_BANK                → Bank fees (essential obligation)
#   TAX_LEVY                → Tax/levies (essential obligation)
#   REWARD_CASHBACK         → Rewards/cashback (minor positive, not income)
# ============================================================================

FRI_CATEGORY_MAP = {
    # ── INFLOWS: Income ──────────────────────────────────────────────────
    ('Receive Credit Transfer', 'SAVINGS DEPOSIT'): {
        'fri_role': 'STABILITY_INCOME', 'essential': True, 'needs_enrichment': True,
    },
    ('Receive Credit Transfer Instant', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'STABILITY_INCOME', 'essential': True, 'needs_enrichment': True,
    },
    ('Receive Credit Transfer Iris', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'STABILITY_INCOME', 'essential': True, 'needs_enrichment': True,
    },
    ('Receive Return Credit Transfer', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Card Top Up', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ TOP UP'): {
        'fri_role': 'STABILITY_INCOME', 'essential': True, 'needs_enrichment': True,
    },

    # ── INFLOWS: Government Benefits ─────────────────────────────────────
    ('Deposit Transaction', 'ΕΦΟΔΙΑΣΜΟΣ ΛΟΓΑΡΙΑΣΜΩΝ YOUTH PASS'): {
        'fri_role': 'STABILITY_BENEFIT', 'essential': True, 'needs_enrichment': False,
    },

    # ── INFLOWS: Commercial / Vodafone CU ────────────────────────────────
    ('Deposit Transaction', 'ΕΦΟΔΙΑΣΜΟΣ ΛΟΓΑΡΙΑΣΜΩΝ CU'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Deposit Transaction', 'VODAFONE CU Cash Back'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },

    # ── INFLOWS: POS/eCommerce Refunds ───────────────────────────────────
    ('Deposit Transaction', 'ΚΑΤΑΘΕΣΗ ΤΑΜΙΕΥΤΗΡΙΟΥ ΑΠΟ ΑΓΟΡΕΣ POS- ECOMMERCE'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Deposit Transaction', 'ΚΑΤΑΘΕΣΗ ΤΑΜΙΕΥΤΗΡΙΟΥ ΓΙΑ POS'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Deposit Transaction', 'Μερική Επιστροφή Συναλλαγής'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Deposit Transaction', 'Επιστροφή απο Αμφισβήτηση (Chargeback)'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Deposit Transaction', 'SAVINGS DEPOSIT'): {
        'fri_role': 'INTERNAL_TRANSFER', 'essential': False, 'needs_enrichment': True,
    },
    ('Deposit Transaction', 'Loyalty Rewards'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Deposit Transaction', 'Contest - Cashback Rewards'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },

    # ── INFLOWS: BNPL/Flex Debt Disbursement (MOMENTUM) ──────────────────
    ('Create Bnpl Account', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'MOMENTUM_DEBT_NEW', 'essential': False, 'needs_enrichment': False,
    },
    ('Create Flex Account', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'MOMENTUM_DEBT_NEW', 'essential': False, 'needs_enrichment': False,
    },

    # ── INFLOWS: BNPL/Flex Refunds (reduce debt) ─────────────────────────
    ('Full Refund On Bnpl Account', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'MOMENTUM_DEBT_REPAY', 'essential': False, 'needs_enrichment': False,
    },
    ('Partial Refund On Bnpl Account', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'MOMENTUM_DEBT_REPAY', 'essential': False, 'needs_enrichment': False,
    },

    # ── INFLOWS: Rewards / Cashback (all via Pay Debt mechanism) ─────────
    ('Pay Debt', 'Black Friday Reward'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Pay Debt', 'Card test transaction'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Pay Debt', 'Cash Now Cashback'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Pay Debt', 'Cash Now Early Repayment Cash Back'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Pay Debt', 'Cash Now Late Fees Cashback'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Pay Debt', 'Christmas BNPL Cashback'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Pay Debt', 'Christmas Village Reward'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Pay Debt', 'IRIS Campaign Cashback'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ("Pay Debt", "January '26 BNPL CashBack"): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Pay Debt', 'Loyalty Rewards'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Pay Debt', 'Pay Later Cashback'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Pay Debt', 'Transportation Reward'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Pay Debt', 'VODAFONE CU Cash Back'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Pay Debt', 'Vodafone Loyalty Rewards'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Pay Debt', 'Welcome Offer Reward'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Pay Debt', 'You.gr Cashback'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Pay Debt', 'ΑΒ Offer Reward'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Pay Debt', 'ΕΞΟΦΛΗΣΗ ΔΙΑΦΟΡΩΝ ΔΑΠΑΝΩΝ EUR ΜΕ ΚΑΤΑΘΕΣΗ ΣΕ ΤΑΜΙΕΥΤΗΡΙΟ'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Pay Debt', 'ΕΦΟΔΙΑΣΜΟΣ ΛΟΓΑΡΙΑΣΜΩΝ CU'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Pay Debt', 'Συμψηφιστική Κατάθεση'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },

    # ── INFLOWS: Interest ────────────────────────────────────────────────
    ('Interest Transaction', 'Credit Interest'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },

    # ── INFLOWS: Internal Transfers ──────────────────────────────────────
    ('Savings Account Transfer', 'ΚΑΤΑΘΕΣΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'INTERNAL_TRANSFER', 'essential': False, 'needs_enrichment': False,
    },
    ('Savings Transfers (To My Account)', 'ΚΑΤΑΘΕΣΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'INTERNAL_TRANSFER', 'essential': False, 'needs_enrichment': False,
    },
    ('Transfer Transaction', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'INTERNAL_TRANSFER', 'essential': False, 'needs_enrichment': True,
    },
    ('Transfer Transaction', 'Mastercard Cards Chargeback'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Savings Account Closing', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'INTERNAL_TRANSFER', 'essential': False, 'needs_enrichment': False,
    },

    # ── INFLOWS: System / Reconciliation ─────────────────────────────────
    ('Reconciliation Of Paymentology File', 'ΚΑΤΑΘΕΣΗ ΑΠΟ ΕΠΙΣΤΡΟΦΕΣ POS - eCommerce - ATM OFFLINE'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Reconciliation Of Chargeback File', 'Mastercard Cards Chargeback'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Full Reversal', 'Πλήρης Αντιλογισμός Ταμιευτηρίου'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Full Reversal', 'Ακυρωτικό Ταμιευτηρίου'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Reversal of BNPL Account', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },

    # ── INFLOWS: Cancellations ───────────────────────────────────────────
    ('Cancellation- Second Step', 'ΑΝΑΛΗΨΗ ΓΙΑ ΑΓΟΡΕΣ POS - eCommerce - ATM OFFLINE'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Cancellation- Second Step', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Cancellation- Second Step', 'ΠΡΟΜΗΘΕΙΑ ΑΠΟ ΚΙΝΗΣΗ ΚΕΦΑΛΑΙΩΝ'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Cancellation- Second Step', 'ΠΡΟΜΗΘΕΙΑ ΑΠΟ ΚΙΝΗΣΗ ΚΕΦΑΛΑΙΩΝ (INSTANT)'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Cancellation- Second Step', 'Συμψηφιστική Αναληψη'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },

    # ── OUTFLOWS: Consumer Spending (POS/ATM — THE OPAQUE BLOB) ──────────
    ('Withdrawal Transaction', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ ΓΙΑ POS'): {
        'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED', 'essential': True, 'needs_enrichment': True,
    },
    ('Withdrawal Transaction', 'ΑΝΑΛΗΨΗ ΑΠΟ ATM'): {
        'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED', 'essential': True, 'needs_enrichment': True,
    },
    ('Reconciliation Of Paymentology File', 'ΑΝΑΛΗΨΗ ΓΙΑ ΑΓΟΡΕΣ POS - eCommerce - ATM OFFLINE'): {
        'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED', 'essential': True, 'needs_enrichment': True,
    },
    ('Reconciliation Of Paymentology File', 'PAYMENTOLOGY RECON (DEBIT)'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },

    # ── OUTFLOWS: Credit Transfers (potential rent/utilities/P2P) ────────
    ('Create Credit Transfer', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED', 'essential': True, 'needs_enrichment': True,
    },
    ('Create Credit Transfer Instant', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED', 'essential': True, 'needs_enrichment': True,
    },
    ('Create Credit Transfer Iris', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED', 'essential': True, 'needs_enrichment': True,
    },

    # ── OUTFLOWS: Transfer Commissions (bank fees) ───────────────────────
    ('Create Credit Transfer', 'ΠΡΟΜΗΘΕΙΑ ΑΠΟ ΚΙΝΗΣΗ ΚΕΦΑΛΑΙΩΝ'): {
        'fri_role': 'FEE_BANK', 'essential': True, 'needs_enrichment': False,
    },
    ('Create Credit Transfer', 'ΠΡΟΜΗΘΕΙΑ ΑΠΟ ΚΙΝΗΣΗ ΚΕΦΑΛΑΙΩΝ (INSTANT)'): {
        'fri_role': 'FEE_BANK', 'essential': True, 'needs_enrichment': False,
    },
    ('Create Credit Transfer Instant', 'ΠΡΟΜΗΘΕΙΑ ΑΠΟ ΚΙΝΗΣΗ ΚΕΦΑΛΑΙΩΝ (INSTANT)'): {
        'fri_role': 'FEE_BANK', 'essential': True, 'needs_enrichment': False,
    },
    ('Receive Credit Transfer Instant', 'ΠΡΟΜΗΘΕΙΑ ΑΠΟ ΚΙΝΗΣΗ ΚΕΦΑΛΑΙΩΝ (INSTANT)'): {
        'fri_role': 'FEE_BANK', 'essential': True, 'needs_enrichment': False,
    },

    # ── OUTFLOWS: Debt Repayment (MOMENTUM positive) ────────────────────
    ('Bnpl Account Payment', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'MOMENTUM_DEBT_REPAY', 'essential': True, 'needs_enrichment': False,
    },
    ('Payment Flex Account', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'MOMENTUM_DEBT_REPAY', 'essential': True, 'needs_enrichment': False,
    },

    # ── OUTFLOWS: BNPL-financed purchases (spending + debt) ──────────────
    ('Create Bnpl Account', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED', 'essential': True, 'needs_enrichment': True,
    },

    # ── OUTFLOWS: Product Payments (subscriptions/recurring) ─────────────
    ('Product Payment Credit Transfer', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED', 'essential': True, 'needs_enrichment': True,
    },
    ('Product Payment Credit Transfer Instant', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED', 'essential': True, 'needs_enrichment': True,
    },

    # ── OUTFLOWS: Direct Debit (highly likely essential in Greece) ───────
    ('Direct Debit Payment', 'ΠΑΓΙΕΣ ΕΝΤΟΛΕΣ DIAS CREDIT DDD'): {
        'fri_role': 'BUFFER_ESSENTIAL', 'essential': True, 'needs_enrichment': False,
    },

    # ── OUTFLOWS: Debt Product Costs (MOMENTUM negative) ────────────────
    ('Create Flex Account', 'Cash Now COMMISSION / ΠΡΟΜΗΘΕΙΑ ΔΗΜΙΟΥΡΓΙΑΣ Cash Now'): {
        'fri_role': 'MOMENTUM_DEBT_COST', 'essential': True, 'needs_enrichment': False,
    },
    ('Create Flex Account', 'FLEX COMMISSION / ΠΡΟΜΗΘΕΙΑ ΔΗΜΙΟΥΡΓΙΑΣ FLEX'): {
        'fri_role': 'MOMENTUM_DEBT_COST', 'essential': True, 'needs_enrichment': False,
    },
    ('Change Payment Date On Bnpl Account', 'COMMISSION RECEIVING SNOOZE'): {
        'fri_role': 'MOMENTUM_DEBT_COST', 'essential': True, 'needs_enrichment': False,
    },

    # ── OUTFLOWS: BNPL Refund Processing ─────────────────────────────────
    ('Full Refund On Bnpl Account', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Partial Refund On Bnpl Account', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },

    # ── OUTFLOWS: Tax ────────────────────────────────────────────────────
    ('Interest Transaction', 'Interest Tax'): {
        'fri_role': 'TAX_LEVY', 'essential': True, 'needs_enrichment': False,
    },

    # ── OUTFLOWS: Internal Transfers ─────────────────────────────────────
    ('Savings Account Transfer', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'INTERNAL_TRANSFER', 'essential': False, 'needs_enrichment': False,
    },
    ('Savings Transfers (To My Account)', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'INTERNAL_TRANSFER', 'essential': False, 'needs_enrichment': False,
    },
    ('Savings Account Closing', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'INTERNAL_TRANSFER', 'essential': False, 'needs_enrichment': False,
    },

    # ── OUTFLOWS: Bank Fees ──────────────────────────────────────────────
    ('Charges For Card Issuance', 'COMMISSION RECEIVING CARD ISSUANCE'): {
        'fri_role': 'FEE_BANK', 'essential': True, 'needs_enrichment': False,
    },
    ('Withdrawal Transaction', 'COMMISSION RECEIVING ATM'): {
        'fri_role': 'FEE_BANK', 'essential': True, 'needs_enrichment': False,
    },
    ('Withdrawal Transaction', 'FEES RECEIVING ATM'): {
        'fri_role': 'FEE_BANK', 'essential': True, 'needs_enrichment': False,
    },

    # ── OUTFLOWS: Discretionary ──────────────────────────────────────────
    ('Withdrawal Transaction', 'MANUAL ΕΞΕΡΧΟΜΕΝΟ ΕΜΒΑΣΜΑ TIPS'): {
        'fri_role': 'BUFFER_DISCRETIONARY', 'essential': False, 'needs_enrichment': False,
    },

    # ── OUTFLOWS: Demand/Settlement ──────────────────────────────────────
    ('Pay Demand', 'Συμψηφιστική Αναληψη'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': True,
    },
    ('Return Credit Transfer', 'ΑΝΑΛΗΨΗ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },

    # ── OUTFLOWS: Cancellations ──────────────────────────────────────────
    ('Cancellation- Second Step', 'Christmas BNPL Cashback'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ("Cancellation- Second Step", "January '26 BNPL CashBack"): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Cancellation- Second Step', 'Mastercard Cards Chargeback'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Cancellation- Second Step', 'Pay Later Cashback'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Cancellation- Second Step', 'ΚΑΤΑΘΕΣΗ ΑΠΟ ΕΠΙΣΤΡΟΦΕΣ POS - eCommerce - ATM OFFLINE'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Cancellation- Second Step', 'Συμψηφιστική Κατάθεση'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Reversal of BNPL Account', 'ΚΑΤΑΘΕΣΕΙΣ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Full Reversal', 'Ακυρωτικό Ταμιευτηρίου'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },
    ('Full Reversal', 'Πλήρης Αντιλογισμός Ταμιευτηρίου'): {
        'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False,
    },

    # ── ZERO-SUM (currently inactive, monitored for activation) ──────────
    ('Interest Transaction', 'Interest Levy'): {
        'fri_role': 'TAX_LEVY', 'essential': True, 'needs_enrichment': False,
    },
    ('Interest Transaction', 'Debit Interest (Χρεωστικοί Τόκοι)'): {
        'fri_role': 'MOMENTUM_DEBT_COST', 'essential': True, 'needs_enrichment': False,
    },
    ('Savings Account Closing', 'ΠΙΣΤΩΤΙΚΟΙ ΤΟΚΟΙ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False,
    },
    ('Savings Account Closing', 'ΦΟΡΟΙ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'TAX_LEVY', 'essential': True, 'needs_enrichment': False,
    },
    ('Savings Account Closing', 'ΕΙΣΦΟΡΑ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'TAX_LEVY', 'essential': True, 'needs_enrichment': False,
    },
    ('Savings Account Closing', 'ΧΡΕΩΣΤΙΚΟΙ ΤΟΚΟΙ ΤΑΜΙΕΥΤΗΡΙΟΥ'): {
        'fri_role': 'MOMENTUM_DEBT_COST', 'essential': True, 'needs_enrichment': False,
    },
    ('Charges For Card Issuance', 'COMMISSION RECEIVING'): {
        'fri_role': 'FEE_BANK', 'essential': True, 'needs_enrichment': False,
    },
}

# Roles that count as income for Stability
INCOME_ROLES = {'STABILITY_INCOME', 'STABILITY_BENEFIT'}

# Roles whose outflows feed the Buffer denominator (essential spending)
ESSENTIAL_SPENDING_ROLES = {'BUFFER_ESSENTIAL', 'FEE_BANK', 'TAX_LEVY', 'MOMENTUM_DEBT_REPAY'}

# Roles that are spending but need MCC to classify essential vs discretionary
UNCLASSIFIED_SPENDING_ROLES = {'BUFFER_SPENDING_UNCLASSIFIED'}

# Roles excluded from FRI arithmetic
EXCLUDED_ROLES = {'INTERNAL_TRANSFER', 'SYSTEM_OPERATION'}

# Roles contributing to debt stock changes
DEBT_INCREASE_ROLES = {'MOMENTUM_DEBT_NEW'}
DEBT_DECREASE_ROLES = {'MOMENTUM_DEBT_REPAY'}
DEBT_COST_ROLES = {'MOMENTUM_DEBT_COST'}


# ============================================================================
# MCC-BASED ENRICHMENT (when Paymentology data is available)
# ============================================================================
# Greek-context MCC → essential/discretionary mapping
# Source: ISO 18245 MCC codes + Greek consumption patterns

ESSENTIAL_MCC_RANGES = {
    # Groceries / Supermarkets
    '5411', '5422', '5441', '5451', '5462',  # grocery stores, bakeries, etc
    # Utilities
    '4900',  # electric, gas, water, sanitary
    '4814', '4812', '4813',  # telecom
    # Transportation (essential)
    '4111', '4112', '4121', '4131',  # local transport, buses, taxis
    '5541', '5542',  # fuel stations
    # Healthcare
    '5912', '8011', '8021', '8031', '8041', '8042', '8043', '8049', '8050', '8062', '8071', '8099',
    # Insurance
    '6300',
    # Education
    '8211', '8220', '8241', '8244', '8249', '8299',
    # Housing-adjacent
    '1520', '1711', '1731', '1740', '1750', '1761', '1771',  # contractors/repair
}

DISCRETIONARY_MCC_RANGES = {
    # Dining
    '5812', '5813', '5814',  # restaurants, bars, fast food
    # Entertainment
    '7832', '7922', '7929', '7933', '7941', '7991', '7992', '7993', '7994', '7995', '7996',
    # Shopping (non-essential)
    '5611', '5621', '5631', '5641', '5651', '5661', '5691', '5699',  # clothing, shoes
    '5732', '5733', '5734', '5735',  # electronics, music
    '5944', '5945', '5947',  # jewelry, gifts
    # Travel (discretionary)
    '4511', '4722', '7011', '7012',  # airlines, travel agencies, hotels
    # Personal care (discretionary)
    '7230', '7297', '7298',  # beauty, health spa
    # Subscriptions/digital
    '5815', '5816', '5817', '5818',  # digital goods
}

# Known Greek essential beneficiary IBAN patterns (for transfer classification)
KNOWN_ESSENTIAL_IBANS = {
    # Format: IBAN prefix or regex pattern → category
    # DEI (electricity) — placeholder, real IBANs from Snappi
    # EYDAP (water) — placeholder
    # OTE (telecom) — placeholder
    # EFKA (social security) — placeholder
}


# ============================================================================
# LIFE STAGE SCALE FACTORS
# ============================================================================

LIFE_STAGE_CONFIG = {
    'EARLY_CAREER':  {'age_range': (18, 29), 'target_months': 3,  'scale_factor': 33.33},
    'ESTABLISHING':  {'age_range': (30, 44), 'target_months': 6,  'scale_factor': 16.67},
    'CONSOLIDATING': {'age_range': (45, 59), 'target_months': 9,  'scale_factor': 11.11},
    'PRESERVING':    {'age_range': (60, 99), 'target_months': 12, 'scale_factor': 8.33},
}

# ============================================================================
# ADAPTIVE WEIGHT CONFIGURATIONS
# ============================================================================

WEIGHT_CONFIGS = {
    'STABLE_SALARIED':  {'buffer': 0.45, 'stability': 0.30, 'momentum': 0.25},
    'VARIABLE_INCOME':  {'buffer': 0.50, 'stability': 0.20, 'momentum': 0.30},
    'HIGH_VOLATILITY':  {'buffer': 0.55, 'stability': 0.15, 'momentum': 0.30},
}

# Adaptive modes when data is incomplete
DATA_MODE_WEIGHTS = {
    'full_data':     {'buffer': 0.45, 'stability': 0.30, 'momentum': 0.25},
    'no_debt':       {'buffer': 0.55, 'stability': 0.45, 'momentum': 0.00},
    'short_history': {'buffer': 0.60, 'stability': 0.15, 'momentum': 0.25},
    'new_user':      {'buffer': 0.70, 'stability': 0.15, 'momentum': 0.15},
}


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class FRIResult:
    """Complete FRI calculation result with full audit trail."""
    total_score: float
    buffer: float
    stability: float
    momentum: float
    weights: dict
    data_mode: str
    income_segment: str
    confidence: float
    calculation_date: datetime

    # Audit: what went into each component
    buffer_detail: dict = field(default_factory=dict)
    stability_detail: dict = field(default_factory=dict)
    momentum_detail: dict = field(default_factory=dict)
    data_quality: dict = field(default_factory=dict)
    coaching_signals: list = field(default_factory=list)

    @property
    def interpretation(self) -> str:
        if self.total_score >= 80:
            return "Thriving — Excellent financial resilience"
        elif self.total_score >= 60:
            return "Stable — Good financial health"
        elif self.total_score >= 40:
            return "Vulnerable — Needs attention"
        elif self.total_score >= 20:
            return "Fragile — Requires support"
        return "Crisis — Urgent intervention needed"

    def to_dict(self) -> dict:
        return {
            'fri_score': round(self.total_score, 2),
            'components': {
                'buffer':    {'score': round(self.buffer, 2),    'weight': self.weights['buffer']},
                'stability': {'score': round(self.stability, 2), 'weight': self.weights['stability']},
                'momentum':  {'score': round(self.momentum, 2),  'weight': self.weights['momentum']},
            },
            'interpretation': self.interpretation,
            'data_mode': self.data_mode,
            'income_segment': self.income_segment,
            'confidence': round(self.confidence, 3),
            'detail': {
                'buffer': self.buffer_detail,
                'stability': self.stability_detail,
                'momentum': self.momentum_detail,
            },
            'coaching_signals': self.coaching_signals,
            'data_quality': self.data_quality,
            'calculation_date': self.calculation_date.isoformat(),
        }


# ============================================================================
# TRANSACTION CLASSIFIER
# ============================================================================

class TransactionClassifier:
    """
    Classifies raw Snappi transactions into FRI roles.
    
    Two-pass approach:
      1. Rule-based: FRI_CATEGORY_MAP lookup on (TransactionType, TransactionSubSubType)
      2. MCC enrichment: If Paymentology data available, refine UNCLASSIFIED → essential/discretionary
    """

    def __init__(self, essential_ratio_fallback: float = 0.65):
        """
        Args:
            essential_ratio_fallback: When MCC data unavailable, assume this fraction 
                of unclassified spending is essential. 0.65 is conservative for Greece 
                (Eurostat HICP weighting: ~62% essential for Greek households).
        """
        self.essential_ratio_fallback = essential_ratio_fallback

    def classify(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add FRI classification columns to transaction DataFrame.
        
        Adds columns: fri_role, fri_essential, fri_needs_enrichment, fri_amount
        fri_amount is always positive: absolute value of the net flow for that transaction.
        """
        df = df.copy()

        # Compute net amount per transaction (positive = inflow, negative = outflow)
        # CreditAmountLC: positive for credits, can be negative for cancellations
        # DebitAmountLC: positive for debits, can be negative for reversals
        df['fri_net_amount'] = df['CreditAmountLC'].fillna(0) - df['DebitAmountLC'].fillna(0)
        df['fri_abs_amount'] = df['fri_net_amount'].abs()

        # Pass 1: Map lookup
        fri_roles = []
        fri_essential = []
        fri_needs_enrichment = []

        for _, row in df.iterrows():
            key = (row.get('TransactionType'), row.get('TransactionSubSubType'))
            mapping = FRI_CATEGORY_MAP.get(key)

            if mapping is None:
                # Fallback: try to infer from TransactionType alone
                mapping = self._fallback_classify(row)

            fri_roles.append(mapping['fri_role'])
            fri_essential.append(mapping['essential'])
            fri_needs_enrichment.append(mapping['needs_enrichment'])

        df['fri_role'] = fri_roles
        df['fri_essential'] = fri_essential
        df['fri_needs_enrichment'] = fri_needs_enrichment

        # Pass 2: MCC enrichment (if mcc_code column exists and has data)
        if 'mcc_code' in df.columns:
            df = self._enrich_with_mcc(df)

        return df

    def _fallback_classify(self, row) -> dict:
        """
        Fallback for unmapped (TransactionType, SubSubType) combinations.
        Uses TransactionType alone or TransactionDescription.
        """
        tx_type = row.get('TransactionType', '')
        tx_desc = row.get('TransactionDescription', '')

        # TransactionType-level fallbacks
        type_fallbacks = {
            'Receive Credit Transfer':         {'fri_role': 'STABILITY_INCOME', 'essential': True, 'needs_enrichment': True},
            'Receive Credit Transfer Instant':  {'fri_role': 'STABILITY_INCOME', 'essential': True, 'needs_enrichment': True},
            'Receive Credit Transfer Iris':     {'fri_role': 'STABILITY_INCOME', 'essential': True, 'needs_enrichment': True},
            'Withdrawal Transaction':           {'fri_role': 'BUFFER_SPENDING_UNCLASSIFIED', 'essential': True, 'needs_enrichment': True},
            'Deposit Transaction':              {'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': True},
            'Pay Debt':                         {'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False},
            'Cancellation- Second Step':        {'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False},
            'Full Reversal':                    {'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False},
        }

        if tx_type in type_fallbacks:
            return type_fallbacks[tx_type]

        # TransactionDescription-level fallbacks
        desc_fallbacks = {
            'Commission':                 {'fri_role': 'FEE_BANK', 'essential': True, 'needs_enrichment': False},
            'Tax':                        {'fri_role': 'TAX_LEVY', 'essential': True, 'needs_enrichment': False},
            'Levy':                       {'fri_role': 'TAX_LEVY', 'essential': True, 'needs_enrichment': False},
            'Credit Interests':           {'fri_role': 'REWARD_CASHBACK', 'essential': False, 'needs_enrichment': False},
            'Debit Interests':            {'fri_role': 'MOMENTUM_DEBT_COST', 'essential': True, 'needs_enrichment': False},
            'Full Reversal':              {'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False},
            'Cancellation':               {'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': False},
            'Savings Account Deposit':    {'fri_role': 'INTERNAL_TRANSFER', 'essential': False, 'needs_enrichment': False},
            'Savings Account Withrawal':  {'fri_role': 'INTERNAL_TRANSFER', 'essential': False, 'needs_enrichment': False},
        }

        if tx_desc in desc_fallbacks:
            return desc_fallbacks[tx_desc]

        logger.warning(f"Unmapped transaction: type={tx_type}, subsub={row.get('TransactionSubSubType')}, desc={tx_desc}")
        return {'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': True}

    def _enrich_with_mcc(self, df: pd.DataFrame) -> pd.DataFrame:
        """Refine UNCLASSIFIED spending using MCC codes from Paymentology."""
        mask = (df['fri_role'] == 'BUFFER_SPENDING_UNCLASSIFIED') & df['mcc_code'].notna()

        for idx in df[mask].index:
            mcc = str(df.at[idx, 'mcc_code']).strip()

            if mcc in ESSENTIAL_MCC_RANGES:
                df.at[idx, 'fri_role'] = 'BUFFER_ESSENTIAL'
                df.at[idx, 'fri_essential'] = True
                df.at[idx, 'fri_needs_enrichment'] = False
            elif mcc in DISCRETIONARY_MCC_RANGES:
                df.at[idx, 'fri_role'] = 'BUFFER_DISCRETIONARY'
                df.at[idx, 'fri_essential'] = False
                df.at[idx, 'fri_needs_enrichment'] = False
            # else: remains UNCLASSIFIED (ambiguous MCC)

        return df


# ============================================================================
# FRI CALCULATOR
# ============================================================================

class FRICalculator:
    """
    Calculate Financial Resilience Index from classified Snappi transactions.
    
    Processes a per-customer transaction DataFrame (already classified by
    TransactionClassifier) and computes Buffer, Stability, Momentum.
    
    The calculator handles four data availability modes:
      - full_data:     ≥6 months history, debt products present
      - no_debt:       ≥6 months history, no BNPL/Flex usage
      - short_history: 2-5 months history
      - new_user:      <2 months history
    """

    def __init__(self, essential_ratio_fallback: float = 0.65):
        self.classifier = TransactionClassifier(essential_ratio_fallback)
        self.essential_ratio_fallback = essential_ratio_fallback

    def calculate(
        self,
        transactions: pd.DataFrame,
        current_balance: float,
        savings_balance: float = 0.0,
        age: Optional[int] = None,
        calculation_date: Optional[datetime] = None,
    ) -> FRIResult:
        """
        Main entry point: compute FRI from raw Snappi transactions.
        
        Args:
            transactions: DataFrame with Snappi schema + transaction_date column.
                Required columns: transaction_date, TransactionType, 
                TransactionSubSubType, CreditAmountLC, DebitAmountLC.
                Optional: mcc_code, merchant_name, beneficiary_iban, balance_after.
            current_balance: Current account balance (EUR).
            savings_balance: Savings account balance (EUR).
            age: Customer age (for life stage scale factor). None = use default.
            calculation_date: Date of calculation. None = now.
        
        Returns:
            FRIResult with full audit trail.
        """
        calc_date = calculation_date or datetime.now()

        # Step 1: Classify all transactions
        classified = self.classifier.classify(transactions)

        # Step 2: Determine data mode
        data_mode, months_available = self._determine_data_mode(classified, calc_date)

        # Step 3: Compute components
        buffer, buffer_detail = self._calculate_buffer(
            classified, current_balance, savings_balance, age, calc_date
        )
        stability, stability_detail = self._calculate_stability(
            classified, calc_date
        )
        momentum, momentum_detail = self._calculate_momentum(
            classified, buffer_detail, calc_date
        )

        # Step 4: Select weights (adaptive)
        income_segment = self._determine_income_segment(stability)
        weights = self._select_weights(data_mode, income_segment)

        # Step 5: Compute total FRI
        total = (
            weights['buffer']    * buffer +
            weights['stability'] * stability +
            weights['momentum']  * momentum
        )
        total = np.clip(total, 0, 100)

        # Step 6: Assess data quality / confidence
        data_quality = self._assess_data_quality(classified, months_available, calc_date)
        confidence = data_quality['overall_confidence']

        # Step 7: Detect coaching signals
        coaching_signals = self._detect_coaching_signals(
            classified, buffer, stability, momentum, momentum_detail, calc_date
        )

        return FRIResult(
            total_score=total,
            buffer=buffer,
            stability=stability,
            momentum=momentum,
            weights=weights,
            data_mode=data_mode,
            income_segment=income_segment,
            confidence=confidence,
            calculation_date=calc_date,
            buffer_detail=buffer_detail,
            stability_detail=stability_detail,
            momentum_detail=momentum_detail,
            data_quality=data_quality,
            coaching_signals=coaching_signals,
        )

    # ────────────────────────────────────────────────────────────────────
    # BUFFER: B_i,t = min(100, (A_i,t / E^essential_i,t) × scale_factor)
    # ────────────────────────────────────────────────────────────────────

    def _calculate_buffer(
        self, df: pd.DataFrame, current_balance: float,
        savings_balance: float, age: Optional[int], calc_date: datetime,
    ) -> tuple[float, dict]:
        """
        Buffer = min(100, liquid_assets / avg_monthly_essential × scale_factor)
        
        liquid_assets = current_balance + savings_balance
        avg_monthly_essential = 3-month rolling average of essential outflows
        scale_factor = life-stage-dependent (default 16.67 for 30-44)
        """
        liquid_assets = current_balance + savings_balance
        scale_factor = self._get_scale_factor(age)

        # Calculate essential spending over last 3 months
        three_months_ago = calc_date - timedelta(days=90)
        recent = df[df['transaction_date'] >= three_months_ago].copy()

        # Identified essential spending (Direct Debit, fees, tax, debt repayment)
        essential_mask = recent['fri_role'].isin(ESSENTIAL_SPENDING_ROLES)
        identified_essential = recent.loc[essential_mask & (recent['fri_net_amount'] < 0), 'fri_net_amount'].sum()
        identified_essential = abs(identified_essential)

        # Unclassified spending — apply essential ratio fallback
        unclassified_mask = recent['fri_role'].isin(UNCLASSIFIED_SPENDING_ROLES)
        total_unclassified = recent.loc[unclassified_mask & (recent['fri_net_amount'] < 0), 'fri_net_amount'].sum()
        total_unclassified = abs(total_unclassified)

        # How much of the unclassified is enriched (has MCC)?
        enriched_essential_mask = (
            (recent['fri_role'] == 'BUFFER_ESSENTIAL') &
            (~recent['fri_needs_enrichment'])
        )
        mcc_enriched_essential = recent.loc[
            enriched_essential_mask & (recent['fri_net_amount'] < 0), 'fri_net_amount'
        ].sum()
        mcc_enriched_essential = abs(mcc_enriched_essential)

        # Estimated essential from unclassified (statistical fallback)
        estimated_essential_from_unclassified = total_unclassified * self.essential_ratio_fallback

        # Total essential = identified + enriched MCC + estimated unclassified
        total_essential_3m = (
            identified_essential + mcc_enriched_essential + estimated_essential_from_unclassified
        )

        # Monthly average (protect against division by zero and partial months)
        months_in_window = max(1.0, min(3.0, (calc_date - three_months_ago).days / 30.44))
        avg_monthly_essential = total_essential_3m / months_in_window

        # Compute Buffer
        if avg_monthly_essential <= 0:
            buffer = 100.0  # No spending detected — max buffer (will be flagged in quality)
        else:
            buffer = min(100.0, (liquid_assets / avg_monthly_essential) * scale_factor)

        buffer = max(0.0, buffer)

        detail = {
            'liquid_assets': round(liquid_assets, 2),
            'current_balance': round(current_balance, 2),
            'savings_balance': round(savings_balance, 2),
            'scale_factor': scale_factor,
            'life_stage': self._get_life_stage(age),
            'avg_monthly_essential': round(avg_monthly_essential, 2),
            'identified_essential_3m': round(identified_essential, 2),
            'mcc_enriched_essential_3m': round(mcc_enriched_essential, 2),
            'unclassified_spending_3m': round(total_unclassified, 2),
            'estimated_essential_from_unclassified': round(estimated_essential_from_unclassified, 2),
            'essential_ratio_used': self.essential_ratio_fallback,
            'buffer_months': round(liquid_assets / avg_monthly_essential, 2) if avg_monthly_essential > 0 else None,
        }

        return buffer, detail

    # ────────────────────────────────────────────────────────────────────
    # STABILITY: S_i,t = 100 × (1 − CV_income), CV = min(1, σ/μ)
    # ────────────────────────────────────────────────────────────────────

    def _calculate_stability(
        self, df: pd.DataFrame, calc_date: datetime,
    ) -> tuple[float, dict]:
        """
        Stability uses coefficient of variation of monthly income over 6 months.
        Income = STABILITY_INCOME + STABILITY_BENEFIT roles (inflows only).
        """
        six_months_ago = calc_date - timedelta(days=180)
        income_df = df[
            (df['fri_role'].isin(INCOME_ROLES)) &
            (df['transaction_date'] >= six_months_ago) &
            (df['fri_net_amount'] > 0)  # only actual inflows
        ].copy()

        if income_df.empty:
            return 50.0, {
                'status': 'no_income_detected',
                'monthly_income': [],
                'mean': 0, 'std': 0, 'cv': None,
                'months_with_income': 0,
            }

        # Group by month
        income_df['month'] = income_df['transaction_date'].dt.to_period('M')
        monthly_income = income_df.groupby('month')['fri_net_amount'].sum()

        # Fill missing months with 0 (critical for CV — missing month = no income)
        all_months = pd.period_range(
            start=six_months_ago, end=calc_date, freq='M'
        )
        monthly_income = monthly_income.reindex(all_months, fill_value=0.0)

        # Need at least 2 months for meaningful CV
        income_values = monthly_income.values.astype(float)
        months_with_income = np.sum(income_values > 0)

        if len(income_values) < 2:
            return 50.0, {
                'status': 'insufficient_history',
                'monthly_income': income_values.tolist(),
                'mean': float(np.mean(income_values)),
                'std': 0, 'cv': None,
                'months_with_income': int(months_with_income),
            }

        mean_income = float(np.mean(income_values))
        std_income = float(np.std(income_values, ddof=1))  # sample std

        if mean_income <= 0:
            return 0.0, {
                'status': 'zero_mean_income',
                'monthly_income': income_values.tolist(),
                'mean': 0, 'std': 0, 'cv': None,
                'months_with_income': int(months_with_income),
            }

        cv = min(1.0, std_income / mean_income)
        stability = 100.0 * (1.0 - cv)
        stability = max(0.0, min(100.0, stability))

        detail = {
            'status': 'computed',
            'monthly_income': [round(v, 2) for v in income_values.tolist()],
            'mean': round(mean_income, 2),
            'std': round(std_income, 2),
            'cv': round(cv, 4),
            'months_with_income': int(months_with_income),
            'months_analyzed': len(income_values),
        }

        return stability, detail

    # ────────────────────────────────────────────────────────────────────
    # MOMENTUM: M_i,t = 50 + 50 × tanh((ΔB + ΔD) / 2)
    #   where ΔB = net financial flow rate (NFR trajectory)
    #         ΔD = debt stock change (negative = improvement)
    # ────────────────────────────────────────────────────────────────────

    def _calculate_momentum(
        self, df: pd.DataFrame, buffer_detail: dict, calc_date: datetime,
    ) -> tuple[float, dict]:
        """
        Momentum uses the hybrid NFR + debt trajectory formula.
        
        ΔB: Change in net savings rate over 3 months (proxy for Buffer trajectory)
        ΔD: Change in outstanding debt stock over 3 months (sign-inverted)
        """
        three_months_ago = calc_date - timedelta(days=90)
        six_months_ago = calc_date - timedelta(days=180)

        # ── ΔB: Net Financial Flow Rate trajectory ──
        # Compare NFR in recent 3 months vs prior 3 months
        recent = df[(df['transaction_date'] >= three_months_ago)]
        prior = df[
            (df['transaction_date'] >= six_months_ago) &
            (df['transaction_date'] < three_months_ago)
        ]

        # NFR = (total income - total spending) per month
        # Exclude internal transfers and system operations
        nfr_roles = (
            INCOME_ROLES | ESSENTIAL_SPENDING_ROLES | UNCLASSIFIED_SPENDING_ROLES |
            {'BUFFER_ESSENTIAL', 'BUFFER_DISCRETIONARY', 'FEE_BANK', 'TAX_LEVY',
             'REWARD_CASHBACK', 'MOMENTUM_DEBT_COST'}
        )

        def calc_monthly_nfr(subset: pd.DataFrame) -> float:
            relevant = subset[subset['fri_role'].isin(nfr_roles)]
            if relevant.empty:
                return 0.0
            total_flow = relevant['fri_net_amount'].sum()
            months = max(1.0, len(relevant['transaction_date'].dt.to_period('M').unique()))
            return total_flow / months

        nfr_recent = calc_monthly_nfr(recent)
        nfr_prior = calc_monthly_nfr(prior)

        # Normalize ΔB to a manageable scale
        # Use mean income as normalizer to make it proportional
        mean_income = buffer_detail.get('avg_monthly_essential', 1.0)
        if mean_income <= 0:
            mean_income = 1.0

        delta_b = (nfr_recent - nfr_prior) / mean_income if mean_income > 0 else 0.0

        # ── ΔD: Debt stock change ──
        # Debt created (inflow BNPL/Flex disbursements) vs debt repaid (outflow payments)

        def calc_debt_stock_change(subset: pd.DataFrame) -> float:
            """Net debt change: positive = debt increased, negative = debt decreased."""
            new_debt = subset.loc[
                subset['fri_role'].isin(DEBT_INCREASE_ROLES) & (subset['fri_net_amount'] > 0),
                'fri_net_amount'
            ].sum()
            repaid = subset.loc[
                subset['fri_role'].isin(DEBT_DECREASE_ROLES) & (subset['fri_net_amount'] < 0),
                'fri_net_amount'
            ].sum()
            # repaid is negative (outflow), so net = new_debt + repaid
            # positive net = debt grew, negative = debt shrank
            return new_debt + repaid

        debt_change_recent = calc_debt_stock_change(recent)
        debt_change_prior = calc_debt_stock_change(prior)

        # ΔD: improvement in debt trajectory (negative change = good)
        # Invert sign so that debt reduction → positive ΔD
        delta_d = -(debt_change_recent - debt_change_prior) / mean_income if mean_income > 0 else 0.0

        # ── Combine and apply tanh normalization ──
        combined = (delta_b + delta_d) / 2.0
        momentum = 50.0 + 50.0 * np.tanh(combined)
        momentum = max(0.0, min(100.0, momentum))

        # Debt cost burden (for coaching, not in formula)
        debt_costs = df.loc[
            (df['fri_role'].isin(DEBT_COST_ROLES)) &
            (df['transaction_date'] >= three_months_ago),
            'fri_net_amount'
        ].sum()

        detail = {
            'nfr_recent': round(nfr_recent, 2),
            'nfr_prior': round(nfr_prior, 2),
            'delta_b_normalized': round(delta_b, 4),
            'debt_change_recent': round(debt_change_recent, 2),
            'debt_change_prior': round(debt_change_prior, 2),
            'delta_d_normalized': round(delta_d, 4),
            'combined_signal': round(combined, 4),
            'debt_costs_3m': round(abs(debt_costs), 2),
            'has_active_debt': bool(
                (df['fri_role'].isin(DEBT_INCREASE_ROLES | DEBT_DECREASE_ROLES)).any()
            ),
        }

        return momentum, detail

    # ────────────────────────────────────────────────────────────────────
    # WEIGHT SELECTION & DATA MODE DETERMINATION
    # ────────────────────────────────────────────────────────────────────

    def _determine_data_mode(
        self, df: pd.DataFrame, calc_date: datetime
    ) -> tuple[str, int]:
        """Determine data availability mode and months of history."""
        if df.empty or 'transaction_date' not in df.columns:
            return 'new_user', 0

        earliest = df['transaction_date'].min()
        months_available = max(1, int((calc_date - earliest).days / 30.44))

        has_debt = df['fri_role'].isin(DEBT_INCREASE_ROLES | DEBT_DECREASE_ROLES).any()

        if months_available < 2:
            return 'new_user', months_available
        elif months_available < 6:
            return 'short_history', months_available
        elif not has_debt:
            return 'no_debt', months_available
        else:
            return 'full_data', months_available

    def _determine_income_segment(self, stability: float) -> str:
        """Segment by income volatility using Stability score."""
        if stability >= 85:
            return 'STABLE_SALARIED'
        elif stability >= 60:
            return 'VARIABLE_INCOME'
        return 'HIGH_VOLATILITY'

    def _select_weights(self, data_mode: str, income_segment: str) -> dict:
        """
        Select component weights.
        
        Data mode takes precedence: if we don't have enough data for a component,
        we redistribute its weight rather than compute a garbage estimate.
        Then within full_data mode, income segment adjusts weights.
        """
        if data_mode != 'full_data':
            return DATA_MODE_WEIGHTS[data_mode]
        return WEIGHT_CONFIGS[income_segment]

    # ────────────────────────────────────────────────────────────────────
    # LIFE STAGE & SCALE FACTOR
    # ────────────────────────────────────────────────────────────────────

    def _get_life_stage(self, age: Optional[int]) -> str:
        if age is None:
            return 'ESTABLISHING'  # default
        for stage, config in LIFE_STAGE_CONFIG.items():
            if config['age_range'][0] <= age <= config['age_range'][1]:
                return stage
        return 'ESTABLISHING'

    def _get_scale_factor(self, age: Optional[int]) -> float:
        stage = self._get_life_stage(age)
        return LIFE_STAGE_CONFIG[stage]['scale_factor']

    # ────────────────────────────────────────────────────────────────────
    # DATA QUALITY & CONFIDENCE
    # ────────────────────────────────────────────────────────────────────

    def _assess_data_quality(
        self, df: pd.DataFrame, months_available: int, calc_date: datetime,
    ) -> dict:
        """
        Confidence score based on data completeness and quality.
        Ranges [0, 1]. Below 0.6 = FRI marked "provisional".
        """
        scores = {}

        # Transaction completeness: ≥80% of months with ≥5 transactions
        if months_available > 0:
            df_dated = df[df['transaction_date'].notna()]
            monthly_counts = df_dated.groupby(
                df_dated['transaction_date'].dt.to_period('M')
            ).size()
            months_with_5plus = (monthly_counts >= 5).sum()
            scores['tx_completeness'] = min(1.0, months_with_5plus / max(1, months_available))
        else:
            scores['tx_completeness'] = 0.0

        # Income detection: can we identify income?
        income_count = (df['fri_role'].isin(INCOME_ROLES)).sum()
        scores['income_detection'] = min(1.0, income_count / max(1, months_available))

        # Categorization rate: % of spending that ISN'T unclassified
        spending_mask = df['fri_role'].str.startswith('BUFFER_')
        if spending_mask.any():
            classified = (df.loc[spending_mask, 'fri_role'] != 'BUFFER_SPENDING_UNCLASSIFIED').sum()
            scores['categorization_rate'] = classified / spending_mask.sum()
        else:
            scores['categorization_rate'] = 0.0

        # History depth
        scores['history_depth'] = min(1.0, months_available / 6.0)

        # Overall: weighted average
        overall = (
            0.30 * scores['tx_completeness'] +
            0.25 * scores['income_detection'] +
            0.25 * scores['categorization_rate'] +
            0.20 * scores['history_depth']
        )

        return {
            'overall_confidence': round(overall, 3),
            'is_provisional': overall < 0.6,
            'detail': {k: round(v, 3) for k, v in scores.items()},
            'months_available': months_available,
        }

    # ────────────────────────────────────────────────────────────────────
    # COACHING SIGNALS (behavioral triggers for Fiona)
    # ────────────────────────────────────────────────────────────────────

    def _detect_coaching_signals(
        self, df: pd.DataFrame,
        buffer: float, stability: float, momentum: float,
        momentum_detail: dict, calc_date: datetime,
    ) -> list[dict]:
        """
        Detect behavioral patterns that should trigger Fiona coaching responses.
        Empathy-first: these are observations, not judgments.
        """
        signals = []
        three_months_ago = calc_date - timedelta(days=90)
        recent = df[df['transaction_date'] >= three_months_ago]

        # ── DISTRESS: Snooze fee usage ──
        snooze_count = (
            recent['TransactionSubSubType'] == 'COMMISSION RECEIVING SNOOZE'
        ).sum()
        if snooze_count > 0:
            signals.append({
                'type': 'DISTRESS',
                'signal': 'bnpl_payment_delay',
                'severity': 'HIGH' if snooze_count > 1 else 'MEDIUM',
                'message': f'Used BNPL payment delay {snooze_count} time(s) in 3 months',
                'coaching_approach': 'empathy_first',
            })

        # ── DISTRESS: Debit interest charged ──
        debit_interest = recent[
            recent['fri_role'] == 'MOMENTUM_DEBT_COST'
        ]['fri_net_amount'].sum()
        if abs(debit_interest) > 0:
            signals.append({
                'type': 'DISTRESS',
                'signal': 'debt_cost_burden',
                'severity': 'HIGH' if abs(debit_interest) > 100 else 'MEDIUM',
                'message': f'Debt costs of €{abs(debit_interest):.2f} in 3 months',
                'coaching_approach': 'empathy_first',
            })

        # ── WARNING: Declining momentum ──
        if momentum < 40 and momentum_detail.get('combined_signal', 0) < -0.1:
            signals.append({
                'type': 'WARNING',
                'signal': 'declining_trajectory',
                'severity': 'HIGH',
                'message': 'Financial trajectory is declining',
                'coaching_approach': 'gentle_awareness',
            })

        # ── WARNING: Low buffer ──
        if buffer < 30:
            signals.append({
                'type': 'WARNING',
                'signal': 'low_buffer',
                'severity': 'HIGH' if buffer < 15 else 'MEDIUM',
                'message': f'Emergency buffer covers less than {'1 month' if buffer < 15 else '2 months'} of expenses',
                'coaching_approach': 'empathy_first',
            })

        # ── WARNING: FRI below critical threshold ──
        fri_approx = 0.45 * buffer + 0.30 * stability + 0.25 * momentum
        if fri_approx < 30:
            signals.append({
                'type': 'CRITICAL',
                'signal': 'fri_below_threshold',
                'severity': 'CRITICAL',
                'message': 'Overall financial resilience is critically low',
                'coaching_approach': 'supportive_action',
            })

        # ── POSITIVE: Active debt reduction ──
        if momentum_detail.get('delta_d_normalized', 0) > 0.05:
            signals.append({
                'type': 'POSITIVE',
                'signal': 'active_debt_reduction',
                'severity': 'LOW',
                'message': 'Debt trajectory is improving — making progress',
                'coaching_approach': 'reinforce_positive',
            })

        # ── POSITIVE: High ATM usage (coaching opportunity, not distress) ──
        atm_spending = recent.loc[
            recent['TransactionSubSubType'] == 'ΑΝΑΛΗΨΗ ΑΠΟ ATM',
            'fri_net_amount'
        ].sum()
        total_spending = recent.loc[
            recent['fri_role'].str.startswith('BUFFER_'),
            'fri_net_amount'
        ].sum()
        if total_spending < 0 and abs(atm_spending) / abs(total_spending) > 0.20:
            signals.append({
                'type': 'INSIGHT',
                'signal': 'high_cash_usage',
                'severity': 'LOW',
                'message': f'Cash withdrawals represent >{abs(atm_spending)/abs(total_spending)*100:.0f}% of spending',
                'coaching_approach': 'gentle_awareness',
            })

        return signals

    # ────────────────────────────────────────────────────────────────────
    # TIME-SERIES: Monthly FRI history
    # ────────────────────────────────────────────────────────────────────

    def calculate_monthly_history(
        self, transactions: pd.DataFrame,
        balance_history: dict[str, float],
        savings_history: dict[str, float] = None,
        age: Optional[int] = None,
        n_months: int = 12,
    ) -> list[dict]:
        """
        Calculate FRI for each of the last n_months.
        
        Args:
            transactions: Full transaction history.
            balance_history: Dict of {YYYY-MM: end_of_month_balance}.
            savings_history: Dict of {YYYY-MM: end_of_month_savings}. Optional.
            age: Customer age.
            n_months: Number of months to compute.
        
        Returns:
            List of monthly FRI results (oldest first).
        """
        if savings_history is None:
            savings_history = {}

        results = []
        now = datetime.now()

        for i in range(n_months - 1, -1, -1):
            calc_date = now - timedelta(days=i * 30)
            month_key = calc_date.strftime('%Y-%m')

            # Use balance for that month, or latest available
            balance = balance_history.get(month_key, list(balance_history.values())[-1] if balance_history else 0)
            savings = savings_history.get(month_key, 0)

            # Filter transactions up to calc_date
            tx_subset = transactions[transactions['transaction_date'] <= calc_date]

            if tx_subset.empty:
                continue

            try:
                fri = self.calculate(
                    tx_subset,
                    current_balance=balance,
                    savings_balance=savings,
                    age=age,
                    calculation_date=calc_date,
                )
                results.append({
                    'month': month_key,
                    'total': round(fri.total_score, 2),
                    'buffer': round(fri.buffer, 2),
                    'stability': round(fri.stability, 2),
                    'momentum': round(fri.momentum, 2),
                    'confidence': round(fri.confidence, 3),
                    'data_mode': fri.data_mode,
                })
            except Exception as e:
                logger.error(f"FRI calculation failed for {month_key}: {e}")
                continue

        return results
