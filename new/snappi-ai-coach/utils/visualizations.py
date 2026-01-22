import plotly.graph_objects as go
import plotly.express as px

# Dark theme template
DARK_TEMPLATE = {
    'layout': {
        'paper_bgcolor': '#1e1e2e',
        'plot_bgcolor': '#1e1e2e',
        'font': {'color': '#ffffff'},
        'xaxis': {'gridcolor': '#2a2a3e', 'color': '#ffffff'},
        'yaxis': {'gridcolor': '#2a2a3e', 'color': '#ffffff'}
    }
}

def create_fri_gauge(score):
    """Create FRI gauge chart with dark theme"""
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "FRI Score", 'font': {'color': '#ffffff'}},
        delta={'reference': 50},
        number={'font': {'color': '#ffffff'}},
        gauge={
            'axis': {'range': [None, 100], 'tickcolor': '#ffffff'},
            'bar': {'color': "#667eea"},
            'steps': [
                {'range': [0, 20], 'color': "#f5576c"},
                {'range': [20, 40], 'color': "#fcb69f"},
                {'range': [40, 60], 'color': "#ffd93d"},
                {'range': [60, 80], 'color': "#6bcf7f"},
                {'range': [80, 100], 'color': "#4caf50"}
            ],
            'threshold': {
                'line': {'color': "white", 'width': 4},
                'thickness': 0.75,
                'value': 90
            }
        }
    ))
    
    fig.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor='#1e1e2e',
        plot_bgcolor='#1e1e2e',
        font={'color': '#ffffff'}
    )
    
    return fig

def create_component_radar(components):
    """Create radar chart for FRI components with dark theme"""
    
    categories = [c['name'] for c in components]
    values = [c['score'] for c in components]
    values.append(values[0])  # Close the loop
    categories.append(categories[0])
    
    fig = go.Figure(data=go.Scatterpolar(
        r=values,
        theta=categories,
        fill='toself',
        line=dict(color='#667eea', width=2),
        fillcolor='rgba(102, 126, 234, 0.3)'
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                gridcolor='#2a2a3e',
                tickfont={'color': '#ffffff'}
            ),
            angularaxis=dict(
                gridcolor='#2a2a3e',
                tickfont={'color': '#ffffff'}
            ),
            bgcolor='#1e1e2e'
        ),
        showlegend=False,
        title="FRI Component Analysis",
        title_font={'color': '#ffffff'},
        height=400,
        paper_bgcolor='#1e1e2e',
        plot_bgcolor='#1e1e2e',
        font={'color': '#ffffff'}
    )
    
    return fig

def create_timeline_chart(monthly_fri):
    """Create FRI timeline chart with dark theme"""
    
    months = [m['month'] for m in monthly_fri]
    totals = [m['total'] for m in monthly_fri]
    
    fig = go.Figure()
    
    # Add main FRI line
    fig.add_trace(go.Scatter(
        x=months,
        y=totals,
        mode='lines+markers',
        name='FRI Score',
        line=dict(color='#667eea', width=3),
        marker=dict(size=8, color='#667eea')
    ))
    
    # Add reference lines with labels
    fig.add_hline(
        y=80, 
        line_dash="dash", 
        line_color="#4caf50",
        annotation_text="Thriving",
        annotation_font_color="#ffffff"
    )
    fig.add_hline(
        y=60, 
        line_dash="dash", 
        line_color="#2196f3",
        annotation_text="Stable",
        annotation_font_color="#ffffff"
    )
    fig.add_hline(
        y=40, 
        line_dash="dash", 
        line_color="#ff9800",
        annotation_text="Vulnerable",
        annotation_font_color="#ffffff"
    )
    
    fig.update_layout(
        title="Financial Resilience Trajectory (12 Months)",
        title_font={'color': '#ffffff'},
        xaxis_title="Month",
        yaxis_title="FRI Score",
        height=400,
        hovermode='x unified',
        paper_bgcolor='#1e1e2e',
        plot_bgcolor='#1e1e2e',
        font={'color': '#ffffff'},
        xaxis=dict(
            gridcolor='#2a2a3e',
            tickfont={'color': '#ffffff'}
        ),
        yaxis=dict(
            gridcolor='#2a2a3e',
            tickfont={'color': '#ffffff'}
        )
    )
    
    return fig