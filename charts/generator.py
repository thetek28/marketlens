"""Chart generator for product analysis visualization."""

import os
import sys
from typing import Dict, List, Optional

try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

if getattr(sys, 'frozen', False):
    _CHART_BASE = os.path.dirname(os.path.dirname(sys.executable))
else:
    _CHART_BASE = os.path.join(os.path.dirname(__file__), "..")


class ChartGenerator:
    """Generates interactive charts for product analysis."""

    def __init__(self, output_dir: Optional[str] = None):
        if output_dir is None:
            try:
                from utils.paths import CHARTS_DIR
                output_dir = CHARTS_DIR
            except ImportError:
                output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "charts")
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_all(self, ideas: List[Dict], hidden_gems: Optional[List[Dict]] = None) -> Dict[str, str]:
        """Generate all charts and return file paths."""
        if not HAS_PLOTLY:
            return {}

        charts = {}

        charts["price_distribution"] = self.price_distribution(ideas)
        charts["rating_distribution"] = self.rating_distribution(ideas)
        charts["competition_analysis"] = self.competition_analysis(ideas)
        charts["priority_breakdown"] = self.priority_breakdown(ideas)
        charts["profit_margin"] = self.profit_margin_chart(ideas)
        charts["roi_analysis"] = self.roi_analysis(ideas)

        if hidden_gems:
            charts["hidden_gems"] = self.hidden_gems_chart(hidden_gems)

        return charts

    def price_distribution(self, ideas: List[Dict]) -> str:
        """Generate price distribution histogram."""
        prices = [i.get("amazon_price", 0) or i.get("price", 0) for i in ideas if i.get("amazon_price") or i.get("price")]

        fig = go.Figure(data=[go.Histogram(
            x=prices,
            nbinsx=20,
            marker_color='#2F5496',
            opacity=0.75,
        )])

        fig.update_layout(
            title="Product Price Distribution",
            xaxis_title="Price (£)",
            yaxis_title="Count",
            template="plotly_white",
            height=400,
        )

        return self._save_chart(fig, "price_distribution")

    def rating_distribution(self, ideas: List[Dict]) -> str:
        """Generate rating distribution bar chart."""
        ratings: dict[str, float] = {}
        for idea in ideas:
            rating = idea.get("rating", 0)
            if rating > 0:
                bucket = f"{int(rating)}-{int(rating)+1}"
                ratings[bucket] = ratings.get(bucket, 0) + 1

        fig = go.Figure(data=[go.Bar(
            x=list(ratings.keys()),
            y=list(ratings.values()),
            marker_color='#548235',
        )])

        fig.update_layout(
            title="Rating Distribution",
            xaxis_title="Rating",
            yaxis_title="Count",
            template="plotly_white",
            height=400,
        )

        return self._save_chart(fig, "rating_distribution")

    def competition_analysis(self, ideas: List[Dict]) -> str:
        """Generate competition vs margin scatter plot."""
        reviews = [i.get("review_count", 0) for i in ideas]
        margins = [i.get("estimated_margin_pct", 0) for i in ideas]
        names = [i.get("name", "")[:30] for i in ideas]
        scores = [i.get("score", 0) for i in ideas]

        fig = go.Figure(data=[go.Scatter(
            x=reviews,
            y=margins,
            mode='markers',
            text=names,
            hovertemplate="%{text}<br>Reviews: %{x}<br>Margin: %{y}%",
            marker=dict(
                size=[s * 30 for s in scores],
                color=margins,
                colorscale='RdYlGn',
                showscale=True,
                colorbar=dict(title="Margin %"),
            ),
        )])

        fig.update_layout(
            title="Competition vs Margin Analysis",
            xaxis_title="Number of Reviews (Competition)",
            yaxis_title="Margin (%)",
            template="plotly_white",
            height=400,
        )

        return self._save_chart(fig, "competition_analysis")

    def priority_breakdown(self, ideas: List[Dict]) -> str:
        """Generate priority tier pie chart."""
        tiers = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "MINIMAL": 0}
        for idea in ideas:
            priority = idea.get("priority", {})
            tier = priority.get("tier", "MINIMAL")
            tiers[tier] = tiers.get(tier, 0) + 1

        colors = {
            "CRITICAL": "#FF0000",
            "HIGH": "#FFA500",
            "MEDIUM": "#FFFF00",
            "LOW": "#0000FF",
            "MINIMAL": "#808080",
        }

        fig = go.Figure(data=[go.Pie(
            labels=list(tiers.keys()),
            values=list(tiers.values()),
            marker_colors=[colors.get(k, "#999") for k in tiers],
            hole=0.3,
        )])

        fig.update_layout(
            title="Priority Breakdown",
            template="plotly_white",
            height=400,
        )

        return self._save_chart(fig, "priority_breakdown")

    def profit_margin_chart(self, ideas: List[Dict]) -> str:
        """Generate profit margin bar chart."""
        sorted_ideas = sorted(ideas, key=lambda x: x.get("estimated_margin_pct", 0), reverse=True)[:20]
        names = [i.get("name", "")[:25] for i in sorted_ideas]
        margins = [i.get("estimated_margin_pct", 0) for i in sorted_ideas]

        fig = go.Figure(data=[go.Bar(
            x=margins,
            y=names,
            orientation='h',
            marker_color='#BF8F00',
        )])

        fig.update_layout(
            title="Top 20 Products by Margin",
            xaxis_title="Margin (%)",
            yaxis=dict(autorange="reversed"),
            template="plotly_white",
            height=500,
        )

        return self._save_chart(fig, "profit_margin")

    def roi_analysis(self, ideas: List[Dict]) -> str:
        """Generate ROI analysis chart."""
        names = [i.get("name", "")[:25] for i in ideas[:15]]
        scores = [i.get("score", 0) * 100 for i in ideas[:15]]
        margins = [i.get("estimated_margin_pct", 0) for i in ideas[:15]]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='Score',
            x=names,
            y=scores,
            marker_color='#2F5496',
        ))
        fig.add_trace(go.Bar(
            name='Margin %',
            x=names,
            y=margins,
            marker_color='#548235',
        ))

        fig.update_layout(
            title="Score vs Margin Comparison",
            barmode='group',
            template="plotly_white",
            height=400,
            xaxis_tickangle=-45,
        )

        return self._save_chart(fig, "roi_analysis")

    def hidden_gems_chart(self, gems: List[Dict]) -> str:
        """Generate hidden gems scatter chart."""
        scores = [g.get("potential_score", 0) for g in gems]
        reviews = [g.get("review_count", 0) for g in gems]
        names = [g.get("name", "")[:30] for g in gems]
        prices = [g.get("amazon_price", 0) for g in gems]

        fig = go.Figure(data=[go.Scatter(
            x=reviews,
            y=scores,
            mode='markers+text',
            text=names,
            textposition="top center",
            hovertemplate="%{text}<br>Reviews: %{x}<br>Potential: %{y}<br>Price: £%{customdata:.2f}",
            customdata=prices,
            marker=dict(
                size=[p / 5 + 5 for p in prices],
                color=scores,
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title="Potential"),
            ),
        )])

        fig.update_layout(
            title="Hidden Gems Analysis",
            xaxis_title="Competition (Reviews)",
            yaxis_title="Potential Score",
            template="plotly_white",
            height=400,
        )

        return self._save_chart(fig, "hidden_gems")

    def supplier_comparison(self, supplier_data: List[Dict]) -> str:
        """Generate supplier comparison chart."""
        names = [s.get("supplier_name", "")[:20] for s in supplier_data]
        costs = [s.get("unit_cost", 0) for s in supplier_data]
        profits = [s.get("profit_per_unit", 0) for s in supplier_data]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='Unit Cost',
            x=names,
            y=costs,
            marker_color='#C00000',
        ))
        fig.add_trace(go.Bar(
            name='Profit/Unit',
            x=names,
            y=profits,
            marker_color='#00B050',
        ))

        fig.update_layout(
            title="Supplier Cost vs Profit Comparison",
            barmode='group',
            template="plotly_white",
            height=400,
        )

        return self._save_chart(fig, "supplier_comparison")

    def profit_projection(self, projections: List[Dict]) -> str:
        """Generate profit projection line chart."""
        months = [p["month"] for p in projections]
        cumulative = [p["cumulative_profit"] for p in projections]
        monthly = [p["profit"] for p in projections]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=months,
            y=cumulative,
            name='Cumulative Profit',
            line=dict(color='#2F5496', width=3),
        ))
        fig.add_trace(go.Bar(
            x=months,
            y=monthly,
            name='Monthly Profit',
            marker_color='#548235',
            opacity=0.6,
        ))

        fig.update_layout(
            title="Profit Projection (12 Months)",
            xaxis_title="Month",
            yaxis_title="Profit (£)",
            template="plotly_white",
            height=400,
        )

        return self._save_chart(fig, "profit_projection")

    def create_dashboard(self, ideas: List[Dict], hidden_gems: Optional[List[Dict]] = None) -> str:
        """Create a combined dashboard HTML file."""
        if not HAS_PLOTLY:
            return ""

        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=(
                "Price Distribution", "Rating Distribution",
                "Competition vs Margin", "Priority Breakdown",
                "Top Products by Margin", "Score vs Margin"
            ),
            specs=[
                [{"type": "histogram"}, {"type": "bar"}],
                [{"type": "scatter"}, {"type": "pie"}],
                [{"type": "bar", "rowspan": 1}, {"type": "bar"}],
            ],
        )

        prices = [i.get("amazon_price", 0) or i.get("price", 0) for i in ideas if i.get("amazon_price") or i.get("price")]
        if prices:
            fig.add_trace(
                go.Histogram(x=prices, nbinsx=15, marker_color='#2F5496'),
                row=1, col=1
            )

        ratings: dict[str, float] = {}
        for idea in ideas:
            r = idea.get("rating", 0)
            if r > 0:
                bucket = f"{int(r)}-{int(r)+1}"
                ratings[bucket] = ratings.get(bucket, 0) + 1
        if ratings:
            fig.add_trace(
                go.Bar(x=list(ratings.keys()), y=list(ratings.values()), marker_color='#548235'),
                row=1, col=2
            )

        reviews = [i.get("review_count", 0) for i in ideas]
        margins = [i.get("estimated_margin_pct", 0) for i in ideas]
        if reviews and margins:
            fig.add_trace(
                go.Scatter(x=reviews, y=margins, mode='markers',
                          marker=dict(size=8, color=margins, colorscale='RdYlGn')),
                row=2, col=1
            )

        tiers: dict[str, int] = {}
        for idea in ideas:
            tier = idea.get("priority", {}).get("tier", "MINIMAL")
            tiers[tier] = tiers.get(tier, 0) + 1
        if tiers:
            fig.add_trace(
                go.Pie(labels=list(tiers.keys()), values=list(tiers.values()), hole=0.3),
                row=2, col=2
            )

        sorted_ideas = sorted(ideas, key=lambda x: x.get("estimated_margin_pct", 0), reverse=True)[:10]
        if sorted_ideas:
            fig.add_trace(
                go.Bar(
                    x=[i.get("estimated_margin_pct", 0) for i in sorted_ideas],
                    y=[i.get("name", "")[:20] for i in sorted_ideas],
                    orientation='h',
                    marker_color='#BF8F00',
                ),
                row=3, col=1
            )

        if sorted_ideas:
            fig.add_trace(
                go.Bar(
                    name='Score',
                    x=[i.get("name", "")[:15] for i in sorted_ideas],
                    y=[i.get("score", 0) * 100 for i in sorted_ideas],
                    marker_color='#2F5496',
                ),
                row=3, col=2
            )

        fig.update_layout(
            height=900,
            title_text="Amazon Product Analysis Dashboard",
            showlegend=False,
            template="plotly_white",
        )

        filepath = os.path.join(self.output_dir, "dashboard.html")
        fig.write_html(filepath)
        return filepath

    def _save_chart(self, fig, name: str) -> str:
        """Save chart as HTML and return filepath."""
        html_path = os.path.join(self.output_dir, f"{name}.html")
        fig.write_html(html_path)

        try:
            png_path = os.path.join(self.output_dir, f"{name}.png")
            fig.write_image(png_path, width=1200, height=600)
        except Exception:
            pass

        return html_path
