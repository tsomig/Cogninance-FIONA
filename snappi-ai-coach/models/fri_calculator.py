import numpy as np
from datetime import datetime, timedelta

class FRICalculator:
    """Calculate Financial Resilience Index from transaction data"""
    
    def __init__(self, weights=(0.45, 0.30, 0.25)):
        self.w_buffer, self.w_stability, self.w_momentum = weights
    
    def calculate_fri(self, transactions):
        """Calculate current FRI from transaction history"""
        
        # Calculate components
        buffer = self._calculate_buffer(transactions)
        stability = self._calculate_stability(transactions)
        momentum = self._calculate_momentum(transactions)
        
        # Total FRI
        total = (self.w_buffer * buffer + 
                self.w_stability * stability + 
                self.w_momentum * momentum)
        
        return {
            'total_score': total,
            'components': [
                {'name': 'Buffer', 'score': buffer, 'weight': self.w_buffer},
                {'name': 'Stability', 'score': stability, 'weight': self.w_stability},
                {'name': 'Momentum', 'score': momentum, 'weight': self.w_momentum}
            ],
            'interpretation': self._interpret_score(total),
            'assets': transactions['current_assets'],
            'buffer': buffer
        }
    
    def _calculate_buffer(self, transactions):
        """Buffer = min(100, (Assets / Essential_Expenses) * 16.67)"""
        assets = transactions['current_assets']
        essential_expenses = transactions['avg_monthly_essential']
        
        if essential_expenses == 0:
            return 100
        
        buffer = min(100, (assets / essential_expenses) * 16.67)
        return buffer
    
    def _calculate_stability(self, transactions):
        """Stability = 100 * (1 - CV_income)"""
        income_history = transactions['monthly_income'][-6:]  # Last 6 months
        
        if len(income_history) < 2:
            return 50  # Default for insufficient data
        
        mean_income = np.mean(income_history)
        std_income = np.std(income_history)
        
        if mean_income == 0:
            return 0
        
        cv = min(1.0, std_income / mean_income)
        stability = 100 * (1 - cv)
        
        return stability
    
    def _calculate_momentum(self, transactions):
        """Momentum = 50 + 50 * tanh((ΔBuffer + ΔDebt) / 2)"""
        
        # Get buffer change (last 3 months)
        if len(transactions['monthly_buffer']) >= 3:
            recent_buffer = transactions['monthly_buffer'][-3:]
            delta_buffer = (recent_buffer[-1] - recent_buffer[0]) / 3
        else:
            delta_buffer = 0
        
        # Get debt change (negative = improvement)
        if len(transactions['monthly_debt']) >= 3:
            recent_debt = transactions['monthly_debt'][-3:]
            delta_debt = -(recent_debt[-1] - recent_debt[0]) / 3
        else:
            delta_debt = 0
        
        combined = (delta_buffer + delta_debt) / 2
        momentum = 50 + 50 * np.tanh(combined / 10)  # Scale factor for realistic range
        
        return momentum
    
    def _interpret_score(self, score):
        """Interpret FRI score"""
        if score >= 80:
            return "Thriving - Excellent financial resilience"
        elif score >= 60:
            return "Stable - Good financial health"
        elif score >= 40:
            return "Vulnerable - Needs attention"
        elif score >= 20:
            return "Fragile - Requires support"
        else:
            return "Crisis - Urgent intervention needed"
    
    def calculate_monthly_fri(self, transactions):
        """Calculate FRI for each of the last 12 months"""
        monthly_scores = []
        
        for i in range(12):
            month_data = self._get_month_data(transactions, i)
            fri = self.calculate_fri(month_data)
            
            monthly_scores.append({
                'month': f"Month {i+1}",
                'total': fri['total_score'],
                'buffer': fri['components'][0]['score'],
                'stability': fri['components'][1]['score'],
                'momentum': fri['components'][2]['score'],
                'assets': month_data['current_assets']
            })
        
        return monthly_scores
    
    def _get_month_data(self, transactions, month_index):
        """Extract data for specific month"""
        # This is simplified - in production, you'd filter actual transaction dates
        return {
            'current_assets': transactions['current_assets'] * (0.8 + 0.4 * np.random.random()),
            'avg_monthly_essential': transactions['avg_monthly_essential'],
            'monthly_income': transactions['monthly_income'][max(0, month_index-5):month_index+1],
            'monthly_buffer': transactions['monthly_buffer'][:month_index+1],
            'monthly_debt': transactions['monthly_debt'][:month_index+1]
        }