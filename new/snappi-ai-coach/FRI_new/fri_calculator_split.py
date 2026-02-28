"""
Financial Resilience Index (FRI) Calculator — Snappi Production Engine
======================================================================
Processes raw Snappi core banking transactions through the FRI Category Map
to compute Buffer (45%), Stability (30%), and Momentum (25%) components.

This module contains ONLY calculation logic, weights, and scale factors.
Transaction classification rules live in fri_category_map.py.

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
    internal_metrics: Dict[str, Any]

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
        calc_date = calculation_date or datetime.now()

        classified = self.classifier.classify(transactions)
        data_mode, months_available = self._determine_data_mode(classified, calc_date)

        Buffer, buffer_detail = self._calculate_buffer(
            classified, current_balance, savings_balance, age, calc_date
        )
        stability, stability_detail = self._calculate_stability(classified, calc_date)
        momentum, momentum_detail = self._calculate_momentum(
            classified, buffer_detail, calc_date
        )

        income_segment = self._determine_income_segment(stability)
        weights = self._select_weights(data_mode, income_segment)

        total = np.clip(
            weights['buffer'] * Buffer +
            weights['stability'] * stability +
            weights['momentum'] * momentum,
            0, 100,
        )

        internal_metrics = {
            'raw_buffer': buffer_detail,
            'raw_stability': stability_detail,
            'raw_momentum': momentum_detail
        }
        data_quality = self._assess_data_quality(classified, months_available, calc_date)
        coaching_signals = self._detect_coaching_signals(
            classified, Buffer, stability, momentum, momentum_detail, calc_date
        )

        return FRIResult(
            total_score=total,
            buffer=Buffer,
            stability=stability,
            momentum=momentum,
            weights=weights,
            data_mode=data_mode,
            income_segment=income_segment,
            confidence=data_quality['overall_confidence'],
            calculation_date=calc_date,
            internal_metrics=internal_metrics,
            buffer_detail=buffer_detail,
            stability_detail=stability_detail,
            momentum_detail=momentum_detail,
            data_quality=data_quality,
            coaching_signals=coaching_signals,
        )

    # ────────────────────────────────────────────────────────────────────
    # BUFFER: B_i,t = min(100, (A_i,t / E^{essential}_i,t) × scale_factor)
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
            Buffer = 100.0
        else:
            Buffer = min(100.0, (liquid_assets / avg_monthly_essential) * scale_factor)
        Buffer = max(0.0, Buffer)

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
        return Buffer, detail

    # ────────────────────────────────────────────────────────────────────
    # STABILITY: S_i,t = 100 × (1 − CV_income), CV = min(1, σ/μ)
    # ────────────────────────────────────────────────────────────────────

    def _calculate_stability(
        self, df: pd.DataFrame, calc_date: datetime,
    ) -> tuple[float, dict]:
        six_months_ago = calc_date - timedelta(days=180)  # 6-months
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

    # ────────────────────────────────────────────────────────────────────
    # MOMENTUM: M_i,t = 50 + 50 × tanh((ΔB + ΔD) / 2)
    # ────────────────────────────────────────────────────────────────────

    def _calculate_momentum(
        self, df: pd.DataFrame, buffer_detail: dict, calc_date: datetime,
    ) -> tuple[float, dict]:
        three_months_ago = calc_date - timedelta(days=90)  # 3-months
        six_months_ago = calc_date - timedelta(days=180)  # 6-months

        recent = df[df['transaction_date'] >= three_months_ago]
        prior = df[
            (df['transaction_date'] >= six_months_ago) &
            (df['transaction_date'] < three_months_ago)
        ]

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

        normalizer = max(1.0, buffer_detail.get('avg_monthly_essential', 1.0))
        delta_b = (nfr_recent - nfr_prior) / normalizer

        def calc_debt_stock_change(subset: pd.DataFrame) -> float:
            new_debt = subset.loc[
                subset['fri_role'].isin(DEBT_INCREASE_ROLES) & (subset['fri_net_amount'] > 0),
                'fri_net_amount'
            ].sum()
            repaid = subset.loc[
                subset['fri_role'].isin(DEBT_DECREASE_ROLES) & (subset['fri_net_amount'] < 0),
                'fri_net_amount'
            ].sum()
            return new_debt + repaid

        debt_recent = calc_debt_stock_change(recent)
        debt_prior = calc_debt_stock_change(prior)
        delta_d = -(debt_recent - debt_prior) / normalizer

        combined = (delta_b + delta_d) / 2.0
        momentum = max(0.0, min(100.0, 50.0 + 50.0 * np.tanh(combined)))

        debt_costs = abs(df.loc[
            (df['fri_role'].isin(DEBT_COST_ROLES)) &
            (df['transaction_date'] >= three_months_ago),
            'fri_net_amount'
        ].sum())

        return momentum, {
            'nfr_recent': round(nfr_recent, 2),
            'nfr_prior': round(nfr_prior, 2),
            'delta_b_normalized': round(delta_b, 4),
            'debt_change_recent': round(debt_recent, 2),
            'debt_change_prior': round(debt_prior, 2),
            'delta_d_normalized': round(delta_d, 4),
            'combined_signal': round(combined, 4),
            'debt_costs_3m': round(debt_costs, 2),
            'has_active_debt': bool(
                df['fri_role'].isin(DEBT_INCREASE_ROLES | DEBT_DECREASE_ROLES).any()
            ),
        }

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
    # COACHING SIGNALS
    # ────────────────────────────────────────────────────────────────────

    def _detect_coaching_signals(
        self, df: pd.DataFrame,
        Buffer: float, stability: float, momentum: float,
        momentum_detail: dict, calc_date: datetime,
    ) -> list[dict]:
        signals = []
        three_months_ago = calc_date - timedelta(days=90)  # 3 months
        recent = df[df['transaction_date'] >= three_months_ago]

        # Snooze fee = payment delay distress
        snooze_count = (
            recent['TransactionSubSubType'] == 'COMMISSION RECEIVING SNOOZE'
        ).sum()
        if snooze_count > 0:
            signals.append({
                'type': 'DISTRESS', 'signal': 'bnpl_payment_delay',
                'severity': 'HIGH' if snooze_count > 1 else 'MEDIUM',
                'message': f'Used BNPL payment delay {snooze_count} time(s) in 3 months',
                'coaching_approach': 'empathy_first',
            })

        # Debt cost burden
        debt_costs = abs(recent[recent['fri_role'].isin(DEBT_COST_ROLES)]['fri_net_amount'].sum())
        if debt_costs > 0:
            signals.append({
                'type': 'DISTRESS', 'signal': 'debt_cost_burden',
                'severity': 'HIGH' if debt_costs > 100 else 'MEDIUM',
                'message': f'Debt costs of €{debt_costs:.2f} in 3 months',
                'coaching_approach': 'empathy_first',
            })

        # Declining trajectory
        if momentum < 40 and momentum_detail.get('combined_signal', 0) < -0.1:
            signals.append({
                'type': 'WARNING', 'signal': 'declining_trajectory',
                'severity': 'HIGH',
                'message': 'Financial trajectory is declining',
                'coaching_approach': 'gentle_awareness',
            })

        # Low buffer
        if Buffer < 30:
            severity = 'HIGH' if Buffer < 15 else 'MEDIUM'
            months_label = '1 month' if Buffer < 15 else '2 months'
            signals.append({
                'type': 'WARNING', 'signal': 'low_buffer',
                'severity': severity,
                'message': f'Emergency buffer covers less than {months_label} of expenses',
                'coaching_approach': 'empathy_first',
            })

        # Critical FRI
        fri_approx = 0.45 * Buffer + 0.30 * stability + 0.25 * momentum
        if fri_approx < 30:
            signals.append({
                'type': 'CRITICAL', 'signal': 'fri_below_threshold',
                'severity': 'CRITICAL',
                'message': 'Overall financial resilience is critically low',
                'coaching_approach': 'supportive_action',
            })

        # Positive: active debt reduction
        if momentum_detail.get('delta_d_normalized', 0) > 0.05:
            signals.append({
                'type': 'POSITIVE', 'signal': 'active_debt_reduction',
                'severity': 'LOW',
                'message': 'Debt trajectory is improving — making progress',
                'coaching_approach': 'reinforce_positive',
            })

        # High cash usage
        atm_spending = abs(recent.loc[
            recent['TransactionSubSubType'] == 'ΑΝΑΛΗΨΗ ΑΠΟ ATM', 'fri_net_amount'
        ].sum())
        total_spending = abs(recent.loc[
            recent['fri_role'].str.startswith('BUFFER_'), 'fri_net_amount'
        ].sum())
        if total_spending > 0 and atm_spending / total_spending > 0.20:
            signals.append({
                'type': 'INSIGHT', 'signal': 'high_cash_usage',
                'severity': 'LOW',
                'message': f'Cash withdrawals represent >{atm_spending/total_spending*100:.0f}% of spending',
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
            internal_metrics=internal_metrics,
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
