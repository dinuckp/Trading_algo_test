"""
Performance Metrics Calculator

Provides comprehensive performance analysis for backtested strategies.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any
from datetime import datetime
import json


class PerformanceMetrics:
    """
    Calculate and analyze trading performance metrics
    """

    def __init__(self, trades: List[Dict], equity_curve: List[Dict]):
        """
        Initialize with trade data and equity curve

        Args:
            trades: List of trade dictionaries
            equity_curve: List of equity snapshots over time
        """
        self.trades = trades
        self.equity_curve = equity_curve
        self.trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()
        self.equity_df = pd.DataFrame(equity_curve) if equity_curve else pd.DataFrame()

    def calculate_all_metrics(self) -> Dict[str, Any]:
        """
        Calculate all performance metrics

        Returns:
            Dictionary containing all metrics
        """
        metrics = {}

        # Basic metrics
        metrics.update(self._calculate_return_metrics())
        metrics.update(self._calculate_risk_metrics())
        metrics.update(self._calculate_trade_metrics())
        metrics.update(self._calculate_advanced_metrics())

        return metrics

    def _calculate_return_metrics(self) -> Dict[str, float]:
        """Calculate return-based metrics"""
        if self.equity_df.empty:
            return {}

        initial = self.equity_df['equity'].iloc[0]
        final = self.equity_df['equity'].iloc[-1]

        total_return = (final - initial) / initial
        total_return_pct = total_return * 100

        # Calculate CAGR if we have time data
        if 'timestamp' in self.equity_df.columns:
            days = (self.equity_df['timestamp'].iloc[-1] - self.equity_df['timestamp'].iloc[0]).days
            years = days / 365.25
            cagr = ((final / initial) ** (1 / years) - 1) if years > 0 else 0
            cagr_pct = cagr * 100
        else:
            cagr = 0
            cagr_pct = 0

        return {
            'initial_capital': initial,
            'final_capital': final,
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'cagr': cagr,
            'cagr_pct': cagr_pct,
            'absolute_profit': final - initial
        }

    def _calculate_risk_metrics(self) -> Dict[str, float]:
        """Calculate risk-based metrics"""
        if self.equity_df.empty:
            return {}

        equity = self.equity_df['equity']
        returns = equity.pct_change().dropna()

        # Maximum drawdown
        cummax = equity.cummax()
        drawdown = (equity - cummax) / cummax
        max_drawdown = drawdown.min()
        max_drawdown_pct = max_drawdown * 100

        # Volatility (annualized)
        volatility = returns.std() * np.sqrt(252)
        volatility_pct = volatility * 100

        # Sharpe Ratio (assuming 252 trading days, 0% risk-free rate)
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0

        # Sortino Ratio (downside deviation)
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std()
        sortino = (returns.mean() / downside_std) * np.sqrt(252) if downside_std > 0 else 0

        # Calmar Ratio (return / max drawdown)
        calmar = abs(returns.mean() * 252 / max_drawdown) if max_drawdown != 0 else 0

        return {
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'volatility': volatility,
            'volatility_pct': volatility_pct,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'calmar_ratio': calmar
        }

    def _calculate_trade_metrics(self) -> Dict[str, Any]:
        """Calculate trade-specific metrics"""
        if self.trades_df.empty:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'win_rate_pct': 0
            }

        total_trades = len(self.trades_df)
        winning_trades = len(self.trades_df[self.trades_df['pnl'] > 0])
        losing_trades = len(self.trades_df[self.trades_df['pnl'] < 0])

        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        avg_win = self.trades_df[self.trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = self.trades_df[self.trades_df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0

        # Profit factor
        gross_profit = self.trades_df[self.trades_df['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(self.trades_df[self.trades_df['pnl'] < 0]['pnl'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Average trade
        avg_trade = self.trades_df['pnl'].mean()

        # Max consecutive wins/losses
        pnl_sign = np.sign(self.trades_df['pnl'])
        sign_changes = pnl_sign.diff().fillna(0) != 0
        groups = sign_changes.cumsum()

        win_streaks = self.trades_df[pnl_sign > 0].groupby(groups[pnl_sign > 0]).size()
        loss_streaks = self.trades_df[pnl_sign < 0].groupby(groups[pnl_sign < 0]).size()

        max_consecutive_wins = win_streaks.max() if len(win_streaks) > 0 else 0
        max_consecutive_losses = loss_streaks.max() if len(loss_streaks) > 0 else 0

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'win_rate_pct': win_rate * 100,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_trade': avg_trade,
            'profit_factor': profit_factor,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'max_consecutive_wins': int(max_consecutive_wins),
            'max_consecutive_losses': int(max_consecutive_losses),
            'expectancy': avg_trade  # Expected profit per trade
        }

    def _calculate_advanced_metrics(self) -> Dict[str, Any]:
        """Calculate advanced performance metrics"""
        if self.equity_df.empty:
            return {}

        equity = self.equity_df['equity']
        returns = equity.pct_change().dropna()

        # Value at Risk (95% confidence)
        var_95 = returns.quantile(0.05)

        # Conditional Value at Risk (Expected Shortfall)
        cvar_95 = returns[returns <= var_95].mean()

        # Recovery Factor (Net Profit / Max Drawdown)
        cummax = equity.cummax()
        drawdown = (equity - cummax) / cummax
        max_dd = abs(drawdown.min())
        net_profit = equity.iloc[-1] - equity.iloc[0]
        recovery_factor = net_profit / (max_dd * equity.iloc[0]) if max_dd > 0 else 0

        # Ulcer Index (measure of downside volatility)
        drawdown_pct = drawdown * 100
        ulcer_index = np.sqrt((drawdown_pct ** 2).mean())

        return {
            'var_95': var_95,
            'cvar_95': cvar_95,
            'recovery_factor': recovery_factor,
            'ulcer_index': ulcer_index
        }

    def generate_report(self, filename: str = None) -> str:
        """
        Generate a comprehensive text report

        Args:
            filename: Optional filename to save report to

        Returns:
            Report as string
        """
        metrics = self.calculate_all_metrics()

        report = []
        report.append("="*80)
        report.append("PERFORMANCE METRICS REPORT")
        report.append("="*80)

        report.append("\nRETURN METRICS")
        report.append("-"*80)
        report.append(f"Initial Capital: ₹{metrics.get('initial_capital', 0):,.2f}")
        report.append(f"Final Capital: ₹{metrics.get('final_capital', 0):,.2f}")
        report.append(f"Absolute Profit: ₹{metrics.get('absolute_profit', 0):,.2f}")
        report.append(f"Total Return: {metrics.get('total_return_pct', 0):.2f}%")
        report.append(f"CAGR: {metrics.get('cagr_pct', 0):.2f}%")

        report.append("\nRISK METRICS")
        report.append("-"*80)
        report.append(f"Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2f}%")
        report.append(f"Volatility (Annual): {metrics.get('volatility_pct', 0):.2f}%")
        report.append(f"Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.3f}")
        report.append(f"Sortino Ratio: {metrics.get('sortino_ratio', 0):.3f}")
        report.append(f"Calmar Ratio: {metrics.get('calmar_ratio', 0):.3f}")
        report.append(f"VaR (95%): {metrics.get('var_95', 0):.4f}")
        report.append(f"Recovery Factor: {metrics.get('recovery_factor', 0):.2f}")

        report.append("\nTRADE METRICS")
        report.append("-"*80)
        report.append(f"Total Trades: {metrics.get('total_trades', 0)}")
        report.append(f"Winning Trades: {metrics.get('winning_trades', 0)}")
        report.append(f"Losing Trades: {metrics.get('losing_trades', 0)}")
        report.append(f"Win Rate: {metrics.get('win_rate_pct', 0):.2f}%")
        report.append(f"Average Win: ₹{metrics.get('avg_win', 0):,.2f}")
        report.append(f"Average Loss: ₹{metrics.get('avg_loss', 0):,.2f}")
        report.append(f"Average Trade: ₹{metrics.get('avg_trade', 0):,.2f}")
        report.append(f"Profit Factor: {metrics.get('profit_factor', 0):.2f}")
        report.append(f"Expectancy: ₹{metrics.get('expectancy', 0):,.2f}")
        report.append(f"Max Consecutive Wins: {metrics.get('max_consecutive_wins', 0)}")
        report.append(f"Max Consecutive Losses: {metrics.get('max_consecutive_losses', 0)}")

        report.append("\n" + "="*80)

        report_text = "\n".join(report)

        if filename:
            with open(filename, 'w') as f:
                f.write(report_text)
            print(f"Report saved to {filename}")

        return report_text

    def save_metrics_json(self, filename: str):
        """Save metrics to JSON file"""
        metrics = self.calculate_all_metrics()

        # Convert numpy types to native Python types for JSON serialization
        metrics_serializable = {}
        for k, v in metrics.items():
            if isinstance(v, (np.integer, np.floating)):
                metrics_serializable[k] = float(v)
            else:
                metrics_serializable[k] = v

        with open(filename, 'w') as f:
            json.dump(metrics_serializable, f, indent=4)

        print(f"Metrics saved to {filename}")

    def save_trades_csv(self, filename: str):
        """Save trade log to CSV"""
        if not self.trades_df.empty:
            self.trades_df.to_csv(filename, index=False)
            print(f"Trades saved to {filename}")
        else:
            print("No trades to save")

    def plot_analysis(self, save_path: str = None):
        """Generate comprehensive performance plots"""
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns

            sns.set_style("whitegrid")

            fig = plt.figure(figsize=(16, 12))

            # 1. Equity Curve
            ax1 = plt.subplot(3, 2, 1)
            if not self.equity_df.empty:
                equity = self.equity_df['equity']
                timestamps = self.equity_df.get('timestamp', range(len(equity)))
                ax1.plot(timestamps, equity, label='Portfolio Value', linewidth=2)
                ax1.axhline(y=equity.iloc[0], color='r', linestyle='--', label='Initial Capital', alpha=0.7)
                ax1.fill_between(timestamps, equity, equity.iloc[0], alpha=0.3)
                ax1.set_title('Equity Curve', fontsize=12, fontweight='bold')
                ax1.set_xlabel('Time')
                ax1.set_ylabel('Portfolio Value (₹)')
                ax1.legend()
                ax1.grid(True, alpha=0.3)

            # 2. Drawdown
            ax2 = plt.subplot(3, 2, 2)
            if not self.equity_df.empty:
                cummax = equity.cummax()
                drawdown = (equity - cummax) / cummax * 100
                ax2.fill_between(timestamps, drawdown, 0, color='red', alpha=0.3)
                ax2.plot(timestamps, drawdown, color='darkred', linewidth=1)
                ax2.set_title('Drawdown', fontsize=12, fontweight='bold')
                ax2.set_xlabel('Time')
                ax2.set_ylabel('Drawdown (%)')
                ax2.grid(True, alpha=0.3)

            # 3. Returns Distribution
            ax3 = plt.subplot(3, 2, 3)
            if not self.equity_df.empty:
                returns = equity.pct_change().dropna() * 100
                ax3.hist(returns, bins=50, alpha=0.7, edgecolor='black')
                ax3.axvline(x=returns.mean(), color='r', linestyle='--', label=f'Mean: {returns.mean():.2f}%')
                ax3.axvline(x=returns.median(), color='g', linestyle='--', label=f'Median: {returns.median():.2f}%')
                ax3.set_title('Returns Distribution', fontsize=12, fontweight='bold')
                ax3.set_xlabel('Return (%)')
                ax3.set_ylabel('Frequency')
                ax3.legend()
                ax3.grid(True, alpha=0.3)

            # 4. Trade P&L
            ax4 = plt.subplot(3, 2, 4)
            if not self.trades_df.empty:
                colors = ['green' if x > 0 else 'red' for x in self.trades_df['pnl']]
                ax4.bar(range(len(self.trades_df)), self.trades_df['pnl'], color=colors, alpha=0.7)
                ax4.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
                ax4.set_title('Trade P&L', fontsize=12, fontweight='bold')
                ax4.set_xlabel('Trade Number')
                ax4.set_ylabel('P&L (₹)')
                ax4.grid(True, alpha=0.3)

            # 5. Cumulative P&L
            ax5 = plt.subplot(3, 2, 5)
            if not self.trades_df.empty:
                cumulative_pnl = self.trades_df['pnl'].cumsum()
                ax5.plot(cumulative_pnl, linewidth=2, color='blue')
                ax5.fill_between(range(len(cumulative_pnl)), cumulative_pnl, 0, alpha=0.3)
                ax5.set_title('Cumulative P&L', fontsize=12, fontweight='bold')
                ax5.set_xlabel('Trade Number')
                ax5.set_ylabel('Cumulative P&L (₹)')
                ax5.grid(True, alpha=0.3)

            # 6. Monthly Returns Heatmap (if enough data)
            ax6 = plt.subplot(3, 2, 6)
            if not self.equity_df.empty and 'timestamp' in self.equity_df.columns:
                try:
                    equity_ts = self.equity_df.set_index('timestamp')['equity']
                    monthly_returns = equity_ts.resample('M').last().pct_change() * 100

                    if len(monthly_returns) > 1:
                        monthly_returns_pivot = monthly_returns.to_frame('return')
                        monthly_returns_pivot['year'] = monthly_returns_pivot.index.year
                        monthly_returns_pivot['month'] = monthly_returns_pivot.index.month
                        pivot = monthly_returns_pivot.pivot(index='year', columns='month', values='return')

                        sns.heatmap(pivot, annot=True, fmt='.1f', cmap='RdYlGn', center=0,
                                   cbar_kws={'label': 'Return (%)'}, ax=ax6)
                        ax6.set_title('Monthly Returns Heatmap', fontsize=12, fontweight='bold')
                        ax6.set_xlabel('Month')
                        ax6.set_ylabel('Year')
                except:
                    ax6.text(0.5, 0.5, 'Insufficient data for heatmap',
                            ha='center', va='center', transform=ax6.transAxes)

            plt.tight_layout()

            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                print(f"Analysis plots saved to {save_path}")

            plt.show()

        except ImportError as e:
            print(f"Required plotting libraries not available: {e}")
