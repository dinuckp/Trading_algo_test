"""
Weekly Analysis Module for Trade Data

Analyzes trading performance on a weekly basis to identify patterns,
optimal trading periods, and performance consistency.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any
import matplotlib.pyplot as plt
import seaborn as sns
from logger import logger


class WeeklyAnalyzer:
    """
    Analyze trades on a weekly basis
    """

    def __init__(self, trades_df: pd.DataFrame, equity_curve_df: pd.DataFrame):
        """
        Initialize weekly analyzer

        Args:
            trades_df: DataFrame with trade data (must have 'timestamp' and 'pnl' columns)
            equity_curve_df: DataFrame with equity curve (must have 'timestamp' and 'equity' columns)
        """
        self.trades_df = trades_df.copy()
        self.equity_curve_df = equity_curve_df.copy()

        # Ensure timestamp is datetime
        if 'timestamp' in self.trades_df.columns:
            self.trades_df['timestamp'] = pd.to_datetime(self.trades_df['timestamp'])

        if 'timestamp' in self.equity_curve_df.columns:
            self.equity_curve_df['timestamp'] = pd.to_datetime(self.equity_curve_df['timestamp'])

        # Add week identifiers
        if 'timestamp' in self.trades_df.columns:
            self.trades_df['week'] = self.trades_df['timestamp'].dt.to_period('W')
            self.trades_df['week_start'] = self.trades_df['week'].apply(lambda x: x.start_time)
            self.trades_df['day_of_week'] = self.trades_df['timestamp'].dt.day_name()
            self.trades_df['hour'] = self.trades_df['timestamp'].dt.hour

        if 'timestamp' in self.equity_curve_df.columns:
            self.equity_curve_df['week'] = self.equity_curve_df['timestamp'].dt.to_period('W')

    def calculate_weekly_metrics(self) -> pd.DataFrame:
        """
        Calculate comprehensive weekly metrics

        Returns:
            DataFrame with weekly performance metrics
        """
        if 'week' not in self.trades_df.columns:
            logger.warning("No week column in trades data")
            return pd.DataFrame()

        weekly_stats = []

        for week, week_trades in self.trades_df.groupby('week'):
            week_start = week.start_time
            week_end = week.end_time

            # Basic metrics
            total_trades = len(week_trades)
            total_pnl = week_trades['pnl'].sum()
            winning_trades = len(week_trades[week_trades['pnl'] > 0])
            losing_trades = len(week_trades[week_trades['pnl'] < 0])
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

            # PnL metrics
            avg_pnl = week_trades['pnl'].mean()
            max_win = week_trades['pnl'].max()
            max_loss = week_trades['pnl'].min()

            # Advanced metrics
            avg_win = week_trades[week_trades['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
            avg_loss = week_trades[week_trades['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0

            gross_profit = week_trades[week_trades['pnl'] > 0]['pnl'].sum()
            gross_loss = abs(week_trades[week_trades['pnl'] < 0]['pnl'].sum())
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

            # Get equity at start and end of week
            week_equity = self.equity_curve_df[
                (self.equity_curve_df['timestamp'] >= week_start) &
                (self.equity_curve_df['timestamp'] <= week_end)
            ]

            if len(week_equity) > 1:
                equity_start = week_equity['equity'].iloc[0]
                equity_end = week_equity['equity'].iloc[-1]
                equity_return = ((equity_end - equity_start) / equity_start * 100) if equity_start > 0 else 0

                # Drawdown during the week
                cummax = week_equity['equity'].cummax()
                drawdown = (week_equity['equity'] - cummax) / cummax
                max_drawdown = drawdown.min() * 100
            else:
                equity_return = 0
                max_drawdown = 0

            weekly_stats.append({
                'week_start': week_start,
                'week_end': week_end,
                'week_number': week_start.isocalendar()[1],
                'total_trades': total_trades,
                'total_pnl': total_pnl,
                'avg_pnl': avg_pnl,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'max_win': max_win,
                'max_loss': max_loss,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'gross_profit': gross_profit,
                'gross_loss': gross_loss,
                'profit_factor': profit_factor,
                'equity_return': equity_return,
                'max_drawdown': max_drawdown
            })

        return pd.DataFrame(weekly_stats)

    def get_best_worst_weeks(self, weekly_metrics: pd.DataFrame, n: int = 3) -> Dict[str, pd.DataFrame]:
        """
        Get best and worst performing weeks

        Args:
            weekly_metrics: DataFrame with weekly metrics
            n: Number of weeks to return

        Returns:
            Dictionary with 'best' and 'worst' weeks
        """
        best_weeks = weekly_metrics.nlargest(n, 'total_pnl')
        worst_weeks = weekly_metrics.nsmallest(n, 'total_pnl')

        return {
            'best': best_weeks,
            'worst': worst_weeks
        }

    def analyze_day_of_week(self) -> pd.DataFrame:
        """
        Analyze performance by day of week

        Returns:
            DataFrame with day-of-week statistics
        """
        if 'day_of_week' not in self.trades_df.columns:
            return pd.DataFrame()

        day_stats = self.trades_df.groupby('day_of_week').agg({
            'pnl': ['count', 'sum', 'mean', 'std'],
        }).round(2)

        day_stats.columns = ['total_trades', 'total_pnl', 'avg_pnl', 'std_pnl']

        # Calculate win rate per day
        day_win_rate = self.trades_df.groupby('day_of_week').apply(
            lambda x: (x['pnl'] > 0).sum() / len(x) * 100 if len(x) > 0 else 0
        )

        day_stats['win_rate'] = day_win_rate

        # Order by day of week
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_stats = day_stats.reindex([d for d in day_order if d in day_stats.index])

        return day_stats

    def analyze_intraday_patterns(self) -> pd.DataFrame:
        """
        Analyze intraday trading patterns by hour

        Returns:
            DataFrame with hourly statistics
        """
        if 'hour' not in self.trades_df.columns:
            return pd.DataFrame()

        hour_stats = self.trades_df.groupby('hour').agg({
            'pnl': ['count', 'sum', 'mean'],
        }).round(2)

        hour_stats.columns = ['total_trades', 'total_pnl', 'avg_pnl']

        # Calculate win rate per hour
        hour_win_rate = self.trades_df.groupby('hour').apply(
            lambda x: (x['pnl'] > 0).sum() / len(x) * 100 if len(x) > 0 else 0
        )

        hour_stats['win_rate'] = hour_win_rate

        return hour_stats.sort_index()

    def plot_weekly_analysis(self, weekly_metrics: pd.DataFrame, save_path: str = None):
        """
        Create comprehensive weekly analysis visualizations

        Args:
            weekly_metrics: DataFrame with weekly metrics
            save_path: Optional path to save the plot
        """
        fig = plt.figure(figsize=(20, 12))
        gs = fig.add_gridspec(4, 3, hspace=0.3, wspace=0.3)

        # 1. Weekly P&L Bar Chart
        ax1 = fig.add_subplot(gs[0, :])
        colors = ['green' if x > 0 else 'red' for x in weekly_metrics['total_pnl']]
        ax1.bar(range(len(weekly_metrics)), weekly_metrics['total_pnl'], color=colors, alpha=0.7)
        ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax1.set_title('Weekly P&L', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Week Number')
        ax1.set_ylabel('P&L (₹)')
        ax1.set_xticks(range(len(weekly_metrics)))
        ax1.set_xticklabels([f"W{w}" for w in weekly_metrics['week_number']], rotation=45)
        ax1.grid(True, alpha=0.3)

        # Add value labels on bars
        for i, (idx, row) in enumerate(weekly_metrics.iterrows()):
            ax1.text(i, row['total_pnl'], f"₹{row['total_pnl']:,.0f}",
                    ha='center', va='bottom' if row['total_pnl'] > 0 else 'top',
                    fontsize=8)

        # 2. Weekly Trade Count
        ax2 = fig.add_subplot(gs[1, 0])
        ax2.bar(range(len(weekly_metrics)), weekly_metrics['total_trades'], color='steelblue', alpha=0.7)
        ax2.set_title('Trades per Week', fontsize=12, fontweight='bold')
        ax2.set_xlabel('Week Number')
        ax2.set_ylabel('Number of Trades')
        ax2.set_xticks(range(len(weekly_metrics)))
        ax2.set_xticklabels([f"W{w}" for w in weekly_metrics['week_number']], rotation=45)
        ax2.grid(True, alpha=0.3)

        # 3. Weekly Win Rate
        ax3 = fig.add_subplot(gs[1, 1])
        ax3.plot(range(len(weekly_metrics)), weekly_metrics['win_rate'], marker='o', linewidth=2, color='green')
        ax3.axhline(y=50, color='red', linestyle='--', label='50% Win Rate', alpha=0.5)
        ax3.set_title('Weekly Win Rate', fontsize=12, fontweight='bold')
        ax3.set_xlabel('Week Number')
        ax3.set_ylabel('Win Rate (%)')
        ax3.set_ylim(0, 105)
        ax3.set_xticks(range(len(weekly_metrics)))
        ax3.set_xticklabels([f"W{w}" for w in weekly_metrics['week_number']], rotation=45)
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # 4. Weekly Equity Return
        ax4 = fig.add_subplot(gs[1, 2])
        colors = ['green' if x > 0 else 'red' for x in weekly_metrics['equity_return']]
        ax4.bar(range(len(weekly_metrics)), weekly_metrics['equity_return'], color=colors, alpha=0.7)
        ax4.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax4.set_title('Weekly Equity Return', fontsize=12, fontweight='bold')
        ax4.set_xlabel('Week Number')
        ax4.set_ylabel('Return (%)')
        ax4.set_xticks(range(len(weekly_metrics)))
        ax4.set_xticklabels([f"W{w}" for w in weekly_metrics['week_number']], rotation=45)
        ax4.grid(True, alpha=0.3)

        # 5. Day of Week Analysis
        ax5 = fig.add_subplot(gs[2, :2])
        day_stats = self.analyze_day_of_week()
        if not day_stats.empty:
            day_stats['total_pnl'].plot(kind='bar', ax=ax5, color='steelblue', alpha=0.7)
            ax5.set_title('P&L by Day of Week', fontsize=12, fontweight='bold')
            ax5.set_xlabel('Day of Week')
            ax5.set_ylabel('Total P&L (₹)')
            ax5.tick_params(axis='x', rotation=45)
            ax5.grid(True, alpha=0.3)

        # 6. Intraday Pattern (by hour)
        ax6 = fig.add_subplot(gs[2, 2])
        hour_stats = self.analyze_intraday_patterns()
        if not hour_stats.empty:
            hour_stats['avg_pnl'].plot(kind='bar', ax=ax6, color='orange', alpha=0.7)
            ax6.set_title('Average P&L by Hour', fontsize=12, fontweight='bold')
            ax6.set_xlabel('Hour of Day')
            ax6.set_ylabel('Avg P&L (₹)')
            ax6.tick_params(axis='x', rotation=0)
            ax6.grid(True, alpha=0.3)

        # 7. Profit Factor by Week
        ax7 = fig.add_subplot(gs[3, 0])
        ax7.plot(range(len(weekly_metrics)), weekly_metrics['profit_factor'], marker='s', linewidth=2, color='purple')
        ax7.axhline(y=1, color='red', linestyle='--', label='Break-even', alpha=0.5)
        ax7.set_title('Weekly Profit Factor', fontsize=12, fontweight='bold')
        ax7.set_xlabel('Week Number')
        ax7.set_ylabel('Profit Factor')
        ax7.set_xticks(range(len(weekly_metrics)))
        ax7.set_xticklabels([f"W{w}" for w in weekly_metrics['week_number']], rotation=45)
        ax7.legend()
        ax7.grid(True, alpha=0.3)

        # 8. Average Win vs Loss by Week
        ax8 = fig.add_subplot(gs[3, 1])
        x = np.arange(len(weekly_metrics))
        width = 0.35
        ax8.bar(x - width/2, weekly_metrics['avg_win'], width, label='Avg Win', color='green', alpha=0.7)
        ax8.bar(x + width/2, weekly_metrics['avg_loss'], width, label='Avg Loss', color='red', alpha=0.7)
        ax8.set_title('Avg Win vs Loss by Week', fontsize=12, fontweight='bold')
        ax8.set_xlabel('Week Number')
        ax8.set_ylabel('P&L (₹)')
        ax8.set_xticks(x)
        ax8.set_xticklabels([f"W{w}" for w in weekly_metrics['week_number']], rotation=45)
        ax8.legend()
        ax8.grid(True, alpha=0.3)

        # 9. Weekly Drawdown
        ax9 = fig.add_subplot(gs[3, 2])
        ax9.fill_between(range(len(weekly_metrics)), weekly_metrics['max_drawdown'], 0, color='red', alpha=0.3)
        ax9.plot(range(len(weekly_metrics)), weekly_metrics['max_drawdown'], color='darkred', linewidth=2)
        ax9.set_title('Weekly Max Drawdown', fontsize=12, fontweight='bold')
        ax9.set_xlabel('Week Number')
        ax9.set_ylabel('Drawdown (%)')
        ax9.set_xticks(range(len(weekly_metrics)))
        ax9.set_xticklabels([f"W{w}" for w in weekly_metrics['week_number']], rotation=45)
        ax9.grid(True, alpha=0.3)

        plt.suptitle('Comprehensive Weekly Analysis', fontsize=16, fontweight='bold', y=0.995)

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Weekly analysis plot saved to {save_path}")

        plt.tight_layout()
        plt.show()

    def generate_weekly_report(self, save_path: str = None) -> str:
        """
        Generate comprehensive weekly analysis report

        Args:
            save_path: Optional path to save the report

        Returns:
            Report as string
        """
        weekly_metrics = self.calculate_weekly_metrics()

        if weekly_metrics.empty:
            return "No weekly data available for analysis"

        best_worst = self.get_best_worst_weeks(weekly_metrics, n=3)
        day_stats = self.analyze_day_of_week()

        report = []
        report.append("="*80)
        report.append("WEEKLY TRADING ANALYSIS REPORT")
        report.append("="*80)

        # Overall Summary
        report.append("\nOVERALL SUMMARY")
        report.append("-"*80)
        report.append(f"Total Weeks Analyzed: {len(weekly_metrics)}")
        report.append(f"Total Trades: {weekly_metrics['total_trades'].sum():,}")
        report.append(f"Total P&L: ₹{weekly_metrics['total_pnl'].sum():,.2f}")
        report.append(f"Average Weekly P&L: ₹{weekly_metrics['total_pnl'].mean():,.2f}")
        report.append(f"Average Weekly Trades: {weekly_metrics['total_trades'].mean():.0f}")
        report.append(f"Average Win Rate: {weekly_metrics['win_rate'].mean():.2f}%")

        # Best Performing Weeks
        report.append("\nTOP 3 BEST PERFORMING WEEKS")
        report.append("-"*80)
        for idx, row in best_worst['best'].iterrows():
            report.append(f"\nWeek {row['week_number']} ({row['week_start'].strftime('%Y-%m-%d')} to {row['week_end'].strftime('%Y-%m-%d')})")
            report.append(f"  Total P&L: ₹{row['total_pnl']:,.2f}")
            report.append(f"  Trades: {row['total_trades']:,} | Win Rate: {row['win_rate']:.2f}%")
            report.append(f"  Equity Return: {row['equity_return']:.2f}%")
            report.append(f"  Profit Factor: {row['profit_factor']:.2f}")

        # Worst Performing Weeks
        report.append("\nTOP 3 WORST PERFORMING WEEKS")
        report.append("-"*80)
        for idx, row in best_worst['worst'].iterrows():
            report.append(f"\nWeek {row['week_number']} ({row['week_start'].strftime('%Y-%m-%d')} to {row['week_end'].strftime('%Y-%m-%d')})")
            report.append(f"  Total P&L: ₹{row['total_pnl']:,.2f}")
            report.append(f"  Trades: {row['total_trades']:,} | Win Rate: {row['win_rate']:.2f}%")
            report.append(f"  Equity Return: {row['equity_return']:.2f}%")
            report.append(f"  Max Drawdown: {row['max_drawdown']:.2f}%")

        # Weekly Breakdown Table
        report.append("\nWEEKLY PERFORMANCE BREAKDOWN")
        report.append("-"*80)
        report.append(f"{'Week':<6} {'Dates':<24} {'Trades':<8} {'P&L':<15} {'Win%':<8} {'Return%':<10}")
        report.append("-"*80)
        for idx, row in weekly_metrics.iterrows():
            dates = f"{row['week_start'].strftime('%m/%d')} - {row['week_end'].strftime('%m/%d')}"
            report.append(
                f"W{row['week_number']:<5} {dates:<24} {row['total_trades']:<8} "
                f"₹{row['total_pnl']:>12,.0f} {row['win_rate']:>6.1f}% {row['equity_return']:>8.2f}%"
            )

        # Day of Week Analysis
        if not day_stats.empty:
            report.append("\nDAY OF WEEK ANALYSIS")
            report.append("-"*80)
            report.append(f"{'Day':<12} {'Trades':<10} {'Total P&L':<15} {'Avg P&L':<15} {'Win Rate':<10}")
            report.append("-"*80)
            for day, row in day_stats.iterrows():
                report.append(
                    f"{day:<12} {row['total_trades']:<10.0f} ₹{row['total_pnl']:>12,.0f} "
                    f"₹{row['avg_pnl']:>12,.0f} {row['win_rate']:>8.1f}%"
                )

        report.append("\n" + "="*80)

        report_text = "\n".join(report)

        if save_path:
            with open(save_path, 'w') as f:
                f.write(report_text)
            logger.info(f"Weekly report saved to {save_path}")

        return report_text
