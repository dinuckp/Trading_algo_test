import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import fs from 'fs';
import { config } from '../config';
import { logger } from '../utils/logger';
import { BacktestResult, TradeSignal } from '../types';

/**
 * Python Backtrader Connector
 *
 * Bridges Node.js trading signals to Python Backtrader for backtesting
 * Supports both subprocess and HTTP modes
 */

export interface BacktraderConfig {
  pythonPath?: string;
  scriptPath?: string;
  dataFile: string;
  startDate?: string;
  endDate?: string;
  initialCash?: number;
  commission?: number;
}

export class BacktraderConnector {
  private config: BacktraderConfig;
  private process: ChildProcess | null = null;

  constructor(customConfig: BacktraderConfig) {
    this.config = {
      pythonPath: customConfig.pythonPath || config.backtest.pythonPath,
      scriptPath: customConfig.scriptPath || config.backtest.backtraderScriptPath,
      ...customConfig,
    };

    logger.info('BacktraderConnector initialized', {
      pythonPath: this.config.pythonPath,
      scriptPath: this.config.scriptPath,
      dataFile: this.config.dataFile,
    });
  }

  /**
   * Run backtest with Python Backtrader
   */
  async runBacktest(signals: TradeSignal[]): Promise<BacktestResult> {
    logger.info('Starting backtest', {
      signalCount: signals.length,
      dataFile: this.config.dataFile,
    });

    try {
      // Write signals to temporary file
      const signalsFile = path.join(
        config.backtest.dataDir,
        'temp_signals.json'
      );
      fs.writeFileSync(signalsFile, JSON.stringify(signals, null, 2));

      // Prepare command arguments
      const args = [
        this.config.scriptPath!,
        '--data',
        this.config.dataFile,
        '--signals',
        signalsFile,
      ];

      if (this.config.startDate) {
        args.push('--start-date', this.config.startDate);
      }

      if (this.config.endDate) {
        args.push('--end-date', this.config.endDate);
      }

      if (this.config.initialCash) {
        args.push('--initial-cash', this.config.initialCash.toString());
      }

      if (this.config.commission) {
        args.push('--commission', this.config.commission.toString());
      }

      logger.info('Executing Python backtest', {
        command: this.config.pythonPath,
        args,
      });

      // Run Python script
      const result = await this.executePythonScript(args);

      // Parse results
      const backtestResult = this.parseBacktestResult(result);

      // Clean up temp file
      if (fs.existsSync(signalsFile)) {
        fs.unlinkSync(signalsFile);
      }

      logger.info('Backtest completed', {
        totalTrades: backtestResult.totalTrades,
        totalPnl: backtestResult.totalPnl,
        winRate: backtestResult.winRate,
      });

      return backtestResult;
    } catch (error) {
      logger.error('Backtest failed', { error });
      throw error;
    }
  }

  /**
   * Execute Python script and return output
   */
  private executePythonScript(args: string[]): Promise<string> {
    return new Promise((resolve, reject) => {
      let stdout = '';
      let stderr = '';

      this.process = spawn(this.config.pythonPath!, args);

      this.process.stdout?.on('data', (data) => {
        stdout += data.toString();
        logger.debug('Python stdout', { data: data.toString() });
      });

      this.process.stderr?.on('data', (data) => {
        stderr += data.toString();
        logger.warn('Python stderr', { data: data.toString() });
      });

      this.process.on('close', (code) => {
        if (code === 0) {
          resolve(stdout);
        } else {
          reject(
            new Error(`Python script exited with code ${code}\n${stderr}`)
          );
        }
      });

      this.process.on('error', (error) => {
        reject(error);
      });
    });
  }

  /**
   * Parse backtest result from Python output
   * Expected format: JSON output from Backtrader
   */
  private parseBacktestResult(output: string): BacktestResult {
    try {
      // Look for JSON in output (Python script should output JSON)
      const jsonMatch = output.match(/\{[\s\S]*\}/);

      if (!jsonMatch) {
        throw new Error('No JSON found in Python output');
      }

      const result = JSON.parse(jsonMatch[0]);

      return {
        totalTrades: result.total_trades || 0,
        winningTrades: result.winning_trades || 0,
        losingTrades: result.losing_trades || 0,
        totalPnl: result.total_pnl || 0,
        maxDrawdown: result.max_drawdown || 0,
        sharpeRatio: result.sharpe_ratio || 0,
        winRate: result.win_rate || 0,
        avgWin: result.avg_win || 0,
        avgLoss: result.avg_loss || 0,
        profitFactor: result.profit_factor || 0,
        trades: (result.trades || []).map((trade: any) => ({
          entryTime: new Date(trade.entry_time),
          exitTime: new Date(trade.exit_time),
          symbol: trade.symbol,
          side: trade.side,
          entryPrice: trade.entry_price,
          exitPrice: trade.exit_price,
          quantity: trade.quantity,
          pnl: trade.pnl,
        })),
      };
    } catch (error) {
      logger.error('Failed to parse backtest result', { error, output });
      throw error;
    }
  }

  /**
   * Kill running process
   */
  kill(): void {
    if (this.process) {
      this.process.kill();
      this.process = null;
      logger.info('Python process killed');
    }
  }
}

export default BacktraderConnector;
