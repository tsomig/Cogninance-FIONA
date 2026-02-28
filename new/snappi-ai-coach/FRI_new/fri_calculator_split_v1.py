"""
Financial Resilience Index (FRI) Calculator — Snappi Production Engine
======================================================================
Processes raw Snappi core banking transactions through the FRI Category Map
to compute Buffer (45%), Stability (30%), and Momentum (25%) components.

This module contains ONLY calculation logic, weights, and scale factors.
Transaction classification rules live in fri_category_map.py.

Momentum: Hybrid NFR + Debt Trajectory formula
    M_{i,t} = 50 + 50 · tanh(k · (α · ΔNFR + (1−α) · ΔD))
    NFR_{i,t} = (I − E^ess − E^disc − D^service) / I

Author: George Tsomidis, PhD — Cogninance, Feb 2026
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import logging

from fri_category_map import (
    FRI_CATEGORY_MAP,
    TRANSACTION_TYPE_FALLBACK,
    TRANSACTION_DESC_FALLBACK,
    ESSENTIAL_MCC_CODES,
    DISCRETIONARY_MCC_CODES,
    INCOME_ROLES,
    ESSENTIAL_SPENDING_ROLES,
    UNCLASSIFIED_SPENDING_ROLES,
    EXCLUDED_ROLES,
    DEBT_INCREASE_ROLES,
    DEBT_DECREASE_ROLES,
    DEBT_COST_ROLES,
)

logger = logging.getLogger(__name__)


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
      2. MCC enrichment: If Paymentology data available, refine UNCLASSIFIED spending
    """

    def __init__(self, essential_ratio_fallback: float = 0.65):
        self.essential_ratio_fallback = essential_ratio_fallback

    def classify(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['fri_net_amount'] = df['CreditAmountLC'].fillna(0) - df['DebitAmountLC'].fillna(0)
        df['fri_abs_amount'] = df['fri_net_amount'].abs()

        fri_roles, fri_essential, fri_needs_enrichment = [], [], []

        for _, row in df.iterrows():
            key = (row.get('TransactionType'), row.get('TransactionSubSubType'))
            mapping = FRI_CATEGORY_MAP.get(key) or self._fallback_classify(row)

            fri_roles.append(mapping['fri_role'])
            fri_essential.append(mapping['essential'])
            fri_needs_enrichment.append(mapping['needs_enrichment'])

        df['fri_role'] = fri_roles
        df['fri_essential'] = fri_essential
        df['fri_needs_enrichment'] = fri_needs_enrichment

        if 'mcc_code' in df.columns:
            df = self._enrich_with_mcc(df)

        return df

    def _fallback_classify(self, row) -> dict:
        tx_type = row.get('TransactionType', '')
        tx_desc = row.get('TransactionDescription', '')

        if tx_type in TRANSACTION_TYPE_FALLBACK:
            return TRANSACTION_TYPE_FALLBACK[tx_type]
        if tx_desc in TRANSACTION_DESC_FALLBACK:
            return TRANSACTION_DESC_FALLBACK[tx_desc]

        logger.warning(
            f"Unmapped transaction: type={tx_type}, "
            f"subsub={row.get('TransactionSubSubType')}, desc={tx_desc}"
        )
        return {'fri_role': 'SYSTEM_OPERATION', 'essential': False, 'needs_enrichment': True}

    def _enrich_with_mcc(self, df: pd.DataFrame) -> pd.DataFrame:
        mask = (df['fri_role'] == 'BUFFER_SPENDING_UNCLASSIFIED') & df['mcc_code'].notna()
        for idx in df[mask].index:
            mcc = str(df.at[idx, 'mcc_code']).strip()
            if mcc in ESSENTIAL_MCC_CODES:
                df.at[idx, 'fri_role'] = 'BUFFER_ESSENTIAL'
                df.at[idx, 'fri_essential'] = True
                df.at[idx, 'fri_needs_enrichment'] = False
            elif mcc in DISCRETIONARY_MCC_CODES:
                df.at[idx, 'fri_role'] = 'BUFFER_DISCRETIONARY'
                df.at[idx, 'fri_essential'] = False
                df.at[idx, 'fri_needs_enrichment'] = False
        return df


# ============================================================================
# FRI CALCULATOR
# ============================================================================

class FRICalculator:
    """
    Calculate Financial Resilience Index from classified Snappi transactions.

    Handles four data availability modes:
      - full_data:     >=6 months history, debt products present
      - no_debt:       >=6 months history, no BNPL/Flex usage
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
        calc_date = calculation_date or datetime.now()

        classified = self.classifier.classify(transactions)
        data_mode, months_available = self._determine_data_mode(classified, calc_date)

        buffer, buffer_detail = self._calculate_buffer(
            classified, current_balance, savings_balance, age, calc_date
        )
        stability, stability_detail = self._calculate_stability(classified, calc_date)
        momentum, momentum_detail = self._calculate_momentum(
            classified, buffer_detail, calc_date
        )

        income_segment = self._determine_income_segment(stability)
        weights = self._select_weights(data_mode, income_segment)

        total = np.clip(
            weights['buffer'] * buffer +
            weights['stability'] * stability +
            weights['momentum'] * momentum,
            0, 100,
        )

        data_quality = self._assess_data_quality(classified, months_available, calc_date)
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
            confidence=data_quality['overall_confidence'],
            calculation_date=calc_date,
            buffer_detail=buffer_detail,
            stability_detail=stability_detail,
            momentum_detail=momentum_detail,
            data_quality=data_quality,
            coaching_signals=coaching_signals,
        )

    # ────────────────────────────────────────────────────────────────────
    # BUFFER: B_i,t = min(100, (A_i,t / E^{essential}_i,t) x scale_factor)
    # ────────────────────────────────────────────────────────────────────

    def _calculate_buffer(
        self, df: pd.DataFrame, current_balance: float,
        savings_balance: float, age: Optional[int], calc_date: datetime,
    ) -> tuple[float, dict]:
        liquid_assets = current_balance + savings_balance
        scale_factor = self._get_scale_factor(age)

        three_months_ago = calc_date - timedelta(days=90)
        recent = df[df['transaction_date'] >= three_months_ago].copy()

        # Layer 1: Identified essential (direct debit, fees, tax, debt repayment)
        essential_mask = recent['fri_role'].isin(ESSENTIAL_SPENDING_ROLES)
        identified_essential = abs(
            recent.loc[essential_mask & (recent['fri_net_amount'] < 0), 'fri_net_amount'].sum()
        )

        # Layer 2: MCC-enriched essential (from Paymentology)
        mcc_mask = (recent['fri_role'] == 'BUFFER_ESSENTIAL') & (~recent['fri_needs_enrichment'])
        mcc_enriched_essential = abs(
            recent.loc[mcc_mask & (recent['fri_net_amount'] < 0), 'fri_net_amount'].sum()
        )

        # Layer 3: Statistical fallback for unclassified spending
        unclassified_mask = recent['fri_role'].isin(UNCLASSIFIED_SPENDING_ROLES)
        total_unclassified = abs(
            recent.loc[unclassified_mask & (recent['fri_net_amount'] < 0), 'fri_net_amount'].sum()
        )
        estimated_essential = total_unclassified * self.essential_ratio_fallback

        total_essential_3m = identified_essential + mcc_enriched_essential + estimated_essential
        months_in_window = max(1.0, min(3.0, (calc_date - three_months_ago).days / 30.44))
        avg_monthly_essential = total_essential_3m / months_in_window

        if avg_monthly_essential <= 0:
            buffer = 100.0
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
            'estimated_essential_from_unclassified': round(estimated_essential, 2),
            'essential_ratio_used': self.essential_ratio_fallback,
            'buffer_months': round(liquid_assets / avg_monthly_essential, 2) if avg_monthly_essential > 0 else None,
        }
        return buffer, detail

    # ────────────────────────────────────────────────────────────────────
    # STABILITY: S_i,t = 100 x (1 - CV_income), CV = min(1, sigma/mu)
    # ────────────────────────────────────────────────────────────────────

    def _calculate_stability(
        self, df: pd.DataFrame, calc_date: datetime,
    ) -> tuple[float, dict]:
        six_months_ago = calc_date - timedelta(days=180)
        income_df = df[
            (df['fri_role'].isin(INCOME_ROLES)) &
            (df['transaction_date'] >= six_months_ago) &
            (df['fri_net_amount'] > 0)
        ].copy()

        if income_df.empty:
            return 50.0, {
                'status': 'no_income_detected',
                'monthly_income': [], 'mean': 0, 'std': 0, 'cv': None,
                'months_with_income': 0,
            }

        income_df['month'] = income_df['transaction_date'].dt.to_period('M')
        monthly_income = income_df.groupby('month')['fri_net_amount'].sum()
        all_months = pd.period_range(start=six_months_ago, end=calc_date, freq='M')
        monthly_income = monthly_income.reindex(all_months, fill_value=0.0)

        income_values = monthly_income.values.astype(float)
        months_with_income = int(np.sum(income_values > 0))

        if len(income_values) < 2:
            return 50.0, {
                'status': 'insufficient_history',
                'monthly_income': income_values.tolist(),
                'mean': float(np.mean(income_values)),
                'std': 0, 'cv': None,
                'months_with_income': months_with_income,
            }

        mean_income = float(np.mean(income_values))
        std_income = float(np.std(income_values, ddof=1))

        if mean_income <= 0:
            return 0.0, {
                'status': 'zero_mean_income',
                'monthly_income': income_values.tolist(),
                'mean': 0, 'std': 0, 'cv': None,
                'months_with_income': months_with_income,
            }

        cv = min(1.0, std_income / mean_income)
        stability = max(0.0, min(100.0, 100.0 * (1.0 - cv)))

        return stability, {
            'status': 'computed',
            'monthly_income': [round(v, 2) for v in income_values],
            'mean': round(mean_income, 2),
            'std': round(std_income, 2),
            'cv': round(cv, 4),
            'months_with_income': months_with_income,
            'months_analyzed': len(income_values),
        }

    # ──────────────────────────────────────────────────────────────────────
    # MOMENTUM (Hybrid NFR + Debt Trajectory)
    # ──────────────────────────────────────────────────────────────────────
    #
    #   NFR_{i,t} = (I - E^ess - E^disc - D^service) / I
    #
    #   M_{i,t} = 50 + 50 * tanh(k * (alpha * dNFR + (1-alpha) * dD))
    #
    #   where dNFR = (NFR_recent - NFR_prior) / 3   (quarterly slope)
    #         dD   = -(debt_stock_recent - debt_stock_prior) / I_avg
    #         k    = sensitivity parameter (calibrate to empirical dist.)
    #         alpha = NFR vs debt trajectory mix
    # ──────────────────────────────────────────────────────────────────────

    def _calculate_momentum(
        self, df: pd.DataFrame, buffer_detail: dict, calc_date: datetime,
        alpha: float = 0.6, k: float = 2.0,
    ) -> tuple[float, dict]:
        """
        Hybrid Momentum: NFR trajectory + debt stock trajectory.

        Informational independence from Buffer: normalizes by income (I),
        not by essential spending. Each FRI component now measures a
        genuinely different dimension.

        Args:
            df: Classified transaction DataFrame.
            buffer_detail: Buffer audit dict (not used in formula -- kept
                for interface compatibility and coaching signal access).
            calc_date: Calculation reference date.
            alpha: Weight on NFR trajectory vs debt trajectory.
                   alpha in [0.5, 0.7] recommended; default 0.6.
            k: Sensitivity parameter controlling tanh saturation.
                   Higher k -> faster saturation. Default 2.0.
        """
        three_months_ago = calc_date - timedelta(days=90)
        six_months_ago = calc_date - timedelta(days=180)

        # -- Partition into recent (t) and prior (t-1) windows --
        recent = df[df['transaction_date'] >= three_months_ago]
        prior = df[
            (df['transaction_date'] >= six_months_ago)
            & (df['transaction_date'] < three_months_ago)
        ]

        # ────────────────────────────────────────────────────────
        # NFR computation for a window
        # ────────────────────────────────────────────────────────

        def calc_nfr(subset: pd.DataFrame) -> tuple[float, dict]:
            """
            Compute NFR = (I - E_ess - E_disc - D_service) / I
            for a 3-month window. Returns (nfr_value, components_dict).
            """
            empty_components = {
                'income': 0.0, 'essential': 0.0, 'discretionary': 0.0,
                'debt_service': 0.0, 'debt_repayment': 0.0, 'debt_cost': 0.0,
                'unclassified_total': 0.0,
                'unclassified_essential_est': 0.0,
                'unclassified_discretionary_est': 0.0,
            }
            if subset.empty:
                return 0.0, empty_components

            # Income: positive inflows from income roles
            income = subset.loc[
                subset['fri_role'].isin(INCOME_ROLES) & (subset['fri_net_amount'] > 0),
                'fri_net_amount'
            ].sum()

            # Essential spending (identified)
            essential_identified = abs(subset.loc[
                subset['fri_role'].isin({'BUFFER_ESSENTIAL', 'FEE_BANK', 'TAX_LEVY'})
                & (subset['fri_net_amount'] < 0),
                'fri_net_amount'
            ].sum())

            # Discretionary spending (identified)
            discretionary_identified = abs(subset.loc[
                (subset['fri_role'] == 'BUFFER_DISCRETIONARY')
                & (subset['fri_net_amount'] < 0),
                'fri_net_amount'
            ].sum())

            # Unclassified -> split by essential_ratio_fallback
            unclassified = abs(subset.loc[
                subset['fri_role'].isin(UNCLASSIFIED_SPENDING_ROLES)
                & (subset['fri_net_amount'] < 0),
                'fri_net_amount'
            ].sum())
            essential_from_unclassified = unclassified * self.essential_ratio_fallback
            discretionary_from_unclassified = unclassified * (1.0 - self.essential_ratio_fallback)

            total_essential = essential_identified + essential_from_unclassified
            total_discretionary = discretionary_identified + discretionary_from_unclassified

            # Debt service: repayments + costs (interest, fees, snooze)
            debt_repayment = abs(subset.loc[
                subset['fri_role'].isin(DEBT_DECREASE_ROLES)
                & (subset['fri_net_amount'] < 0),
                'fri_net_amount'
            ].sum())
            debt_cost = abs(subset.loc[
                subset['fri_role'].isin(DEBT_COST_ROLES)
                & (subset['fri_net_amount'] < 0),
                'fri_net_amount'
            ].sum())
            debt_service = debt_repayment + debt_cost

            # NFR
            if income <= 0:
                nfr = 0.0
            else:
                nfr = (income - total_essential - total_discretionary - debt_service) / income

            components = {
                'income': round(income, 2),
                'essential': round(total_essential, 2),
                'discretionary': round(total_discretionary, 2),
                'debt_service': round(debt_service, 2),
                'debt_repayment': round(debt_repayment, 2),
                'debt_cost': round(debt_cost, 2),
                'unclassified_total': round(unclassified, 2),
                'unclassified_essential_est': round(essential_from_unclassified, 2),
                'unclassified_discretionary_est': round(discretionary_from_unclassified, 2),
            }
            return nfr, components

        # ────────────────────────────────────────────────────────
        # Monthly NFR series (like Stability's monthly_income)
        # ────────────────────────────────────────────────────────

        def calc_monthly_nfr_series(subset: pd.DataFrame) -> list[dict]:
            """
            Per-month NFR breakdown over a window.
            Returns list of {month, nfr, income, essential, discretionary, ...}.
            """
            if subset.empty:
                return []

            months_in_window = subset['transaction_date'].dt.to_period('M').unique()
            monthly = []
            for month_period in sorted(months_in_window):
                month_mask = subset['transaction_date'].dt.to_period('M') == month_period
                month_data = subset[month_mask]
                nfr_val, parts = calc_nfr(month_data)
                monthly.append({
                    'month': str(month_period),
                    'nfr': round(nfr_val, 4),
                    **parts,
                })
            return monthly

        # ────────────────────────────────────────────────────────
        # Window-level NFR
        # ────────────────────────────────────────────────────────

        nfr_recent, nfr_recent_parts = calc_nfr(recent)
        nfr_prior, nfr_prior_parts = calc_nfr(prior)

        # Monthly series for full audit trail and LLM context
        monthly_nfr_recent = calc_monthly_nfr_series(recent)
        monthly_nfr_prior = calc_monthly_nfr_series(prior)

        # dNFR: quarterly slope of net financial rate
        delta_nfr = (nfr_recent - nfr_prior) / 3.0

        # ────────────────────────────────────────────────────────
        # dD: Debt stock trajectory
        # ────────────────────────────────────────────────────────

        def calc_net_debt_change(subset: pd.DataFrame) -> tuple[float, dict]:
            """
            Net debt change: positive = debt grew, negative = debt shrank.
            Returns (net_change, {new_debt, repaid, repaid_outflows, refund_inflows}).

            BNPL refund fix: captures both regular repayment outflows
            (fri_net_amount < 0) AND refund inflows (fri_net_amount > 0)
            in DEBT_DECREASE_ROLES. BNPL refunds use dual-entry accounting:
              - INFLOW:  MOMENTUM_DEBT_REPAY, fri_net_amount > 0 (credit)
              - OUTFLOW: SYSTEM_OPERATION, fri_net_amount < 0 (excluded)
            Without this fix, returned BNPL products show zero debt reduction.
            """
            new_debt = subset.loc[
                subset['fri_role'].isin(DEBT_INCREASE_ROLES) & (subset['fri_net_amount'] > 0),
                'fri_net_amount'
            ].sum()

            # Regular installment payments (negative outflows)
            repaid_outflows = abs(subset.loc[
                subset['fri_role'].isin(DEBT_DECREASE_ROLES) & (subset['fri_net_amount'] < 0),
                'fri_net_amount'
            ].sum())

            # BNPL refund inflows (positive credits with DEBT_DECREASE role)
            refund_inflows = subset.loc[
                subset['fri_role'].isin(DEBT_DECREASE_ROLES) & (subset['fri_net_amount'] > 0),
                'fri_net_amount'
            ].sum()

            total_repaid = repaid_outflows + refund_inflows
            return new_debt - total_repaid, {
                'new_debt': round(new_debt, 2),
                'repaid': round(total_repaid, 2),
                'repaid_outflows': round(repaid_outflows, 2),
                'refund_inflows': round(refund_inflows, 2),
            }

        debt_change_recent, debt_parts_recent = calc_net_debt_change(recent)
        debt_change_prior, debt_parts_prior = calc_net_debt_change(prior)

        # Normalize by average income (NOT essential spending -> no Buffer leak)
        avg_income = (nfr_recent_parts['income'] + nfr_prior_parts['income']) / 2.0
        if avg_income <= 0:
            avg_income = max(nfr_recent_parts['income'], nfr_prior_parts['income'], 1.0)

        # dD: sign-inverted so debt reduction -> positive signal
        delta_d = -(debt_change_recent - debt_change_prior) / avg_income

        # ────────────────────────────────────────────────────────
        # Hybrid: M = 50 + 50*tanh(k*(alpha*dNFR + (1-alpha)*dD))
        # ────────────────────────────────────────────────────────

        combined_raw = alpha * delta_nfr + (1.0 - alpha) * delta_d
        combined_scaled = k * combined_raw
        momentum = 50.0 + 50.0 * np.tanh(combined_scaled)
        momentum = float(np.clip(momentum, 0.0, 100.0))

        # ────────────────────────────────────────────────────────
        # Spending composition ratios (for LLM coaching context)
        # ────────────────────────────────────────────────────────

        def spending_ratios(parts: dict) -> dict:
            """What % of income goes to each category."""
            inc = parts['income']
            if inc <= 0:
                return {
                    'essential_pct': None, 'discretionary_pct': None,
                    'debt_service_pct': None, 'savings_rate_pct': None,
                }
            ess_pct = round(parts['essential'] / inc * 100, 1)
            disc_pct = round(parts['discretionary'] / inc * 100, 1)
            debt_pct = round(parts['debt_service'] / inc * 100, 1)
            savings_pct = round(
                max(0, (1.0 - (parts['essential'] + parts['discretionary'] + parts['debt_service']) / inc)) * 100, 1
            )
            return {
                'essential_pct': ess_pct,
                'discretionary_pct': disc_pct,
                'debt_service_pct': debt_pct,
                'savings_rate_pct': savings_pct,
            }

        ratios_recent = spending_ratios(nfr_recent_parts)
        ratios_prior = spending_ratios(nfr_prior_parts)

        # ────────────────────────────────────────────────────────
        # Trajectory interpretation (LLM consumes directly)
        # ────────────────────────────────────────────────────────

        def interpret_nfr_trend(d_nfr: float) -> str:
            if d_nfr > 0.02:
                return 'improving'
            elif d_nfr < -0.02:
                return 'declining'
            return 'stable'

        def interpret_debt_trend(d_d: float) -> str:
            if d_d > 0.02:
                return 'reducing'
            elif d_d < -0.02:
                return 'increasing'
            return 'stable'

        def interpret_momentum(score: float) -> str:
            if score >= 70:
                return 'strong_positive'
            elif score >= 55:
                return 'mild_positive'
            elif score >= 45:
                return 'neutral'
            elif score >= 30:
                return 'mild_negative'
            return 'strong_negative'

        # ────────────────────────────────────────────────────────
        # Debt context (coaching signals, not in formula)
        # ────────────────────────────────────────────────────────

        debt_costs_3m = abs(df.loc[
            df['fri_role'].isin(DEBT_COST_ROLES)
            & (df['transaction_date'] >= three_months_ago),
            'fri_net_amount'
        ].sum())

        has_active_debt = bool(
            df['fri_role'].isin(DEBT_INCREASE_ROLES | DEBT_DECREASE_ROLES).any()
        )

        bnpl_count_recent = int(recent[
            recent['fri_role'].isin(DEBT_INCREASE_ROLES)
        ].shape[0])

        snooze_count_recent = int(recent[
            recent['TransactionSubSubType'] == 'COMMISSION RECEIVING SNOOZE'
        ].shape[0]) if 'TransactionSubSubType' in recent.columns else 0

        # ────────────────────────────────────────────────────────
        # Full detail dict -- 28 keys matching Buffer/Stability granularity
        # ────────────────────────────────────────────────────────

        detail = {
            # Status (mirrors Stability's 'status' field)
            'status': 'computed' if avg_income > 1.0 else 'insufficient_income',

            # Formula parameters
            'alpha': alpha,
            'k': k,

            # NFR: window-level aggregates
            'nfr_recent': round(nfr_recent, 4),
            'nfr_prior': round(nfr_prior, 4),
            'delta_nfr': round(delta_nfr, 6),

            # NFR: full decomposition per window
            'nfr_recent_components': nfr_recent_parts,
            'nfr_prior_components': nfr_prior_parts,

            # NFR: monthly series (like Stability's monthly_income)
            'monthly_nfr_recent': monthly_nfr_recent,
            'monthly_nfr_prior': monthly_nfr_prior,

            # Spending composition (% of income)
            'spending_ratios_recent': ratios_recent,
            'spending_ratios_prior': ratios_prior,

            # Debt trajectory
            'debt_change_recent': round(debt_change_recent, 2),
            'debt_change_prior': round(debt_change_prior, 2),
            'debt_parts_recent': debt_parts_recent,
            'debt_parts_prior': debt_parts_prior,
            'delta_d_normalized': round(delta_d, 6),

            # Combination signals
            'combined_raw': round(combined_raw, 6),
            'combined_scaled': round(combined_scaled, 4),
            'avg_income_normalizer': round(avg_income, 2),

            # Interpretive fields (LLM consumes these directly)
            'nfr_trend': interpret_nfr_trend(delta_nfr),
            'debt_trend': interpret_debt_trend(delta_d),
            'momentum_interpretation': interpret_momentum(momentum),

            # Debt context (coaching)
            'has_active_debt': has_active_debt,
            'debt_costs_3m': round(debt_costs_3m, 2),
            'bnpl_new_products_recent': bnpl_count_recent,
            'snooze_usage_recent': snooze_count_recent,

            # Essential ratio used for unclassified split
            'essential_ratio_used': self.essential_ratio_fallback,
        }

        return momentum, detail

    # ────────────────────────────────────────────────────────────────────
    # WEIGHT SELECTION & DATA MODE
    # ────────────────────────────────────────────────────────────────────

    def _determine_data_mode(self, df: pd.DataFrame, calc_date: datetime) -> tuple[str, int]:
        if df.empty or 'transaction_date' not in df.columns:
            return 'new_user', 0
        earliest = df['transaction_date'].min()
        months = max(1, int((calc_date - earliest).days / 30.44))
        has_debt = df['fri_role'].isin(DEBT_INCREASE_ROLES | DEBT_DECREASE_ROLES).any()
        if months < 2:
            return 'new_user', months
        elif months < 6:
            return 'short_history', months
        elif not has_debt:
            return 'no_debt', months
        return 'full_data', months

    def _determine_income_segment(self, stability: float) -> str:
        if stability >= 85:
            return 'STABLE_SALARIED'
        elif stability >= 60:
            return 'VARIABLE_INCOME'
        return 'HIGH_VOLATILITY'

    def _select_weights(self, data_mode: str, income_segment: str) -> dict:
        if data_mode != 'full_data':
            return DATA_MODE_WEIGHTS[data_mode]
        return WEIGHT_CONFIGS[income_segment]

    # ────────────────────────────────────────────────────────────────────
    # LIFE STAGE
    # ────────────────────────────────────────────────────────────────────

    def _get_life_stage(self, age: Optional[int]) -> str:
        if age is None:
            return 'ESTABLISHING'
        for stage, cfg in LIFE_STAGE_CONFIG.items():
            if cfg['age_range'][0] <= age <= cfg['age_range'][1]:
                return stage
        return 'ESTABLISHING'

    def _get_scale_factor(self, age: Optional[int]) -> float:
        return LIFE_STAGE_CONFIG[self._get_life_stage(age)]['scale_factor']

    # ────────────────────────────────────────────────────────────────────
    # DATA QUALITY & CONFIDENCE
    # ────────────────────────────────────────────────────────────────────

    def _assess_data_quality(
        self, df: pd.DataFrame, months_available: int, calc_date: datetime,
    ) -> dict:
        scores = {}

        if months_available > 0:
            df_dated = df[df['transaction_date'].notna()]
            monthly_counts = df_dated.groupby(
                df_dated['transaction_date'].dt.to_period('M')
            ).size()
            months_with_5plus = (monthly_counts >= 5).sum()
            scores['tx_completeness'] = min(1.0, months_with_5plus / max(1, months_available))
        else:
            scores['tx_completeness'] = 0.0

        scores['income_detection'] = min(
            1.0, df['fri_role'].isin(INCOME_ROLES).sum() / max(1, months_available)
        )

        spending_mask = df['fri_role'].str.startswith('BUFFER_')
        if spending_mask.any():
            classified = (df.loc[spending_mask, 'fri_role'] != 'BUFFER_SPENDING_UNCLASSIFIED').sum()
            scores['categorization_rate'] = classified / spending_mask.sum()
        else:
            scores['categorization_rate'] = 0.0

        scores['history_depth'] = min(1.0, months_available / 6.0)

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
    # COACHING SIGNALS (17 signals, NFR-aware)
    # ────────────────────────────────────────────────────────────────────

    def _detect_coaching_signals(
        self, df: pd.DataFrame,
        buffer: float, stability: float, momentum: float,
        momentum_detail: dict, calc_date: datetime,
    ) -> list[dict]:
        """
        Detect behavioral patterns that should trigger Fiona coaching responses.
        Empathy-first: these are observations, not judgments.

        Uses the rich momentum_detail from the hybrid NFR formula to produce
        granular, actionable coaching signals.
        """
        signals = []
        three_months_ago = calc_date - timedelta(days=90)
        recent = df[df['transaction_date'] >= three_months_ago]

        # -- DISTRESS: Snooze fee usage (BNPL payment delay) --
        snooze_count = momentum_detail.get('snooze_usage_recent', 0)
        if snooze_count == 0 and 'TransactionSubSubType' in recent.columns:
            snooze_count = int((
                recent['TransactionSubSubType'] == 'COMMISSION RECEIVING SNOOZE'
            ).sum())
        if snooze_count > 0:
            signals.append({
                'type': 'DISTRESS',
                'signal': 'bnpl_payment_delay',
                'severity': 'HIGH' if snooze_count > 1 else 'MEDIUM',
                'message': f'Used BNPL payment delay {snooze_count} time(s) in 3 months',
                'coaching_approach': 'empathy_first',
            })

        # -- DISTRESS: Debt cost burden --
        debt_costs = momentum_detail.get('debt_costs_3m', 0)
        if debt_costs > 0:
            avg_income = momentum_detail.get('avg_income_normalizer', 1.0)
            debt_cost_pct = (debt_costs / avg_income * 100) if avg_income > 0 else 0
            signals.append({
                'type': 'DISTRESS',
                'signal': 'debt_cost_burden',
                'severity': 'HIGH' if debt_costs > 100 or debt_cost_pct > 5 else 'MEDIUM',
                'message': f'Debt costs of \u20ac{debt_costs:.2f} in 3 months ({debt_cost_pct:.1f}% of income)',
                'coaching_approach': 'empathy_first',
            })

        # -- DISTRESS: New BNPL products while already carrying debt --
        bnpl_new = momentum_detail.get('bnpl_new_products_recent', 0)
        has_active_debt = momentum_detail.get('has_active_debt', False)
        if bnpl_new > 1 and has_active_debt:
            signals.append({
                'type': 'DISTRESS',
                'signal': 'multiple_new_bnpl',
                'severity': 'HIGH' if bnpl_new > 3 else 'MEDIUM',
                'message': f'Opened {bnpl_new} new BNPL/Flex products in 3 months',
                'coaching_approach': 'empathy_first',
            })

        # -- WARNING: Declining NFR trajectory --
        nfr_trend = momentum_detail.get('nfr_trend', 'stable')
        if nfr_trend == 'declining':
            ratios = momentum_detail.get('spending_ratios_recent', {})
            savings_pct = ratios.get('savings_rate_pct')
            severity = 'HIGH' if (savings_pct is not None and savings_pct < 5) else 'MEDIUM'
            msg = 'Financial behavior trajectory is declining'
            if savings_pct is not None:
                msg += f' \u2014 current savings rate {savings_pct}% of income'
            signals.append({
                'type': 'WARNING',
                'signal': 'declining_nfr_trajectory',
                'severity': severity,
                'message': msg,
                'coaching_approach': 'gentle_awareness',
            })

        # -- WARNING: Declining momentum score --
        momentum_interp = momentum_detail.get('momentum_interpretation', 'neutral')
        if momentum < 40 and momentum_interp in ('mild_negative', 'strong_negative'):
            signals.append({
                'type': 'WARNING',
                'signal': 'declining_trajectory',
                'severity': 'HIGH' if momentum_interp == 'strong_negative' else 'MEDIUM',
                'message': 'Overall financial trajectory is declining',
                'coaching_approach': 'gentle_awareness',
            })

        # -- WARNING: Increasing debt trajectory --
        debt_trend = momentum_detail.get('debt_trend', 'stable')
        if debt_trend == 'increasing':
            debt_parts = momentum_detail.get('debt_parts_recent', {})
            new_debt = debt_parts.get('new_debt', 0)
            repaid = debt_parts.get('repaid', 0)
            signals.append({
                'type': 'WARNING',
                'signal': 'increasing_debt',
                'severity': 'HIGH' if new_debt > repaid * 2 else 'MEDIUM',
                'message': f'Debt is growing \u2014 \u20ac{new_debt:.0f} new vs \u20ac{repaid:.0f} repaid in 3 months',
                'coaching_approach': 'gentle_awareness',
            })

        # -- WARNING: Low buffer --
        if buffer < 30:
            signals.append({
                'type': 'WARNING',
                'signal': 'low_buffer',
                'severity': 'HIGH' if buffer < 15 else 'MEDIUM',
                'message': f"Emergency buffer covers less than {'1 month' if buffer < 15 else '2 months'} of expenses",
                'coaching_approach': 'empathy_first',
            })

        # -- WARNING: High essential spending ratio --
        ratios_recent = momentum_detail.get('spending_ratios_recent', {})
        essential_pct = ratios_recent.get('essential_pct')
        if essential_pct is not None and essential_pct > 85:
            signals.append({
                'type': 'WARNING',
                'signal': 'essential_spending_squeeze',
                'severity': 'HIGH' if essential_pct > 95 else 'MEDIUM',
                'message': f'{essential_pct}% of income goes to essential expenses \u2014 very little flexibility',
                'coaching_approach': 'empathy_first',
            })

        # -- CRITICAL: FRI below critical threshold --
        fri_approx = 0.45 * buffer + 0.30 * stability + 0.25 * momentum
        if fri_approx < 30:
            signals.append({
                'type': 'CRITICAL',
                'signal': 'fri_below_threshold',
                'severity': 'CRITICAL',
                'message': 'Overall financial resilience is critically low',
                'coaching_approach': 'supportive_action',
            })

        # -- POSITIVE: Active debt reduction --
        if debt_trend == 'reducing':
            debt_parts = momentum_detail.get('debt_parts_recent', {})
            repaid = debt_parts.get('repaid', 0)
            signals.append({
                'type': 'POSITIVE',
                'signal': 'active_debt_reduction',
                'severity': 'LOW',
                'message': f'Debt trajectory is improving \u2014 \u20ac{repaid:.0f} repaid in 3 months',
                'coaching_approach': 'reinforce_positive',
            })

        # -- POSITIVE: Improving NFR trajectory --
        if nfr_trend == 'improving':
            nfr_recent = momentum_detail.get('nfr_recent', 0)
            nfr_prior = momentum_detail.get('nfr_prior', 0)
            signals.append({
                'type': 'POSITIVE',
                'signal': 'improving_savings_behavior',
                'severity': 'LOW',
                'message': f'Savings behavior is improving (NFR {nfr_prior:.1%} \u2192 {nfr_recent:.1%})',
                'coaching_approach': 'reinforce_positive',
            })

        # -- POSITIVE: Strong momentum --
        if momentum_interp == 'strong_positive':
            signals.append({
                'type': 'POSITIVE',
                'signal': 'strong_momentum',
                'severity': 'LOW',
                'message': 'Financial trajectory is strongly positive \u2014 great progress',
                'coaching_approach': 'reinforce_positive',
            })

        # -- INSIGHT: Discretionary spending shift --
        ratios_prior = momentum_detail.get('spending_ratios_prior', {})
        disc_recent = ratios_recent.get('discretionary_pct')
        disc_prior = ratios_prior.get('discretionary_pct')
        if disc_recent is not None and disc_prior is not None:
            disc_shift = disc_recent - disc_prior
            if abs(disc_shift) > 5:
                direction = 'increased' if disc_shift > 0 else 'decreased'
                signals.append({
                    'type': 'INSIGHT',
                    'signal': 'discretionary_spending_shift',
                    'severity': 'LOW',
                    'message': f'Discretionary spending {direction} by {abs(disc_shift):.1f}pp ({disc_prior:.1f}% \u2192 {disc_recent:.1f}%)',
                    'coaching_approach': 'gentle_awareness',
                })

        # -- INSIGHT: High cash usage (ATM) --
        atm_spending = recent.loc[
            recent['TransactionSubSubType'] == '\u0391\u039d\u0386\u039b\u0397\u03a8\u0397 \u0391\u03a0\u039f ATM',
            'fri_net_amount'
        ].sum() if 'TransactionSubSubType' in recent.columns else 0
        total_spending = recent.loc[
            recent['fri_role'].str.startswith('BUFFER_'),
            'fri_net_amount'
        ].sum()
        if total_spending < 0 and abs(atm_spending) / abs(total_spending) > 0.20:
            signals.append({
                'type': 'INSIGHT',
                'signal': 'high_cash_usage',
                'severity': 'LOW',
                'message': f'Cash withdrawals represent {abs(atm_spending)/abs(total_spending)*100:.0f}% of spending',
                'coaching_approach': 'gentle_awareness',
            })

        # -- INSIGHT: Debt service burden relative to income --
        debt_svc_pct = ratios_recent.get('debt_service_pct')
        if debt_svc_pct is not None and debt_svc_pct > 20:
            signals.append({
                'type': 'INSIGHT',
                'signal': 'high_debt_service_ratio',
                'severity': 'MEDIUM' if debt_svc_pct > 30 else 'LOW',
                'message': f'{debt_svc_pct}% of income goes to debt service',
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
        if savings_history is None:
            savings_history = {}

        results = []
        now = datetime.now()

        for i in range(n_months - 1, -1, -1):
            calc_date = now - timedelta(days=i * 30)
            month_key = calc_date.strftime('%Y-%m')
            balance = balance_history.get(
                month_key, list(balance_history.values())[-1] if balance_history else 0
            )
            savings = savings_history.get(month_key, 0)
            tx_subset = transactions[transactions['transaction_date'] <= calc_date]

            if tx_subset.empty:
                continue

            try:
                fri = self.calculate(
                    tx_subset, current_balance=balance,
                    savings_balance=savings, age=age, calculation_date=calc_date,
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

        return results