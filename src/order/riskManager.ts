import { config } from '../config';
import { logger } from '../utils/logger';
import {
  OrderIntent,
  Position,
  RiskCheckResult,
  Greeks,
} from '../types';

/**
 * RiskManager - Pre-trade risk checks
 * Enforces:
 * - Maximum total exposure
 * - Maximum risk per trade
 * - Position sizing limits
 * - Greeks-based exposure limits (delta, vega)
 * - Margin requirements
 */

export interface RiskManagerConfig {
  maxTotalExposure: number;
  maxRiskPerTrade: number;
  maxPositionSize: number;
  maxVegaExposure: number;
  maxDeltaExposure: number;
  marginBufferPercent: number;
}

export class RiskManager {
  private config: RiskManagerConfig;
  private currentExposure: number = 0;
  private currentVegaExposure: number = 0;
  private currentDeltaExposure: number = 0;
  private positions: Map<string, Position> = new Map();

  constructor(customConfig?: Partial<RiskManagerConfig>) {
    this.config = {
      maxTotalExposure: customConfig?.maxTotalExposure || config.risk.maxTotalExposure,
      maxRiskPerTrade: customConfig?.maxRiskPerTrade || config.risk.maxRiskPerTrade,
      maxPositionSize: customConfig?.maxPositionSize || config.risk.maxPositionSize,
      maxVegaExposure: customConfig?.maxVegaExposure || config.risk.maxVegaExposure,
      maxDeltaExposure: customConfig?.maxDeltaExposure || config.risk.maxDeltaExposure,
      marginBufferPercent:
        customConfig?.marginBufferPercent || config.risk.marginBufferPercent,
    };

    logger.info('RiskManager initialized', { config: this.config });
  }

  /**
   * Check if an order passes all risk checks
   */
  checkOrder(
    orderIntent: OrderIntent,
    currentPrice: number,
    greeks?: Greeks,
    availableMargin?: number
  ): RiskCheckResult {
    const checks: RiskCheckResult['checks'] = {
      totalExposure: { passed: true, current: 0, limit: 0 },
      tradeRisk: { passed: true, current: 0, limit: 0 },
      positionSize: { passed: true, current: 0, limit: 0 },
    };

    // Calculate order value
    const orderValue = orderIntent.quantity * currentPrice;

    // Check 1: Total exposure
    const newExposure = this.currentExposure + orderValue;
    checks.totalExposure = {
      passed: newExposure <= this.config.maxTotalExposure,
      current: newExposure,
      limit: this.config.maxTotalExposure,
    };

    if (!checks.totalExposure.passed) {
      logger.warn('Risk check failed: Total exposure exceeded', {
        current: newExposure,
        limit: this.config.maxTotalExposure,
      });

      return {
        allowed: false,
        reason: 'Total exposure limit exceeded',
        checks,
      };
    }

    // Check 2: Trade risk
    checks.tradeRisk = {
      passed: orderValue <= this.config.maxRiskPerTrade,
      current: orderValue,
      limit: this.config.maxRiskPerTrade,
    };

    if (!checks.tradeRisk.passed) {
      logger.warn('Risk check failed: Trade risk exceeded', {
        current: orderValue,
        limit: this.config.maxRiskPerTrade,
      });

      return {
        allowed: false,
        reason: 'Trade risk limit exceeded',
        checks,
      };
    }

    // Check 3: Position size
    checks.positionSize = {
      passed: orderIntent.quantity <= this.config.maxPositionSize,
      current: orderIntent.quantity,
      limit: this.config.maxPositionSize,
    };

    if (!checks.positionSize.passed) {
      logger.warn('Risk check failed: Position size exceeded', {
        current: orderIntent.quantity,
        limit: this.config.maxPositionSize,
      });

      return {
        allowed: false,
        reason: 'Position size limit exceeded',
        checks,
      };
    }

    // Check 4: Greeks-based exposure (if greeks provided)
    if (greeks) {
      // Vega exposure
      const vegaChange = Math.abs(greeks.vega * orderIntent.quantity);
      const newVegaExposure = this.currentVegaExposure + vegaChange;

      checks.vegaExposure = {
        passed: newVegaExposure <= this.config.maxVegaExposure,
        current: newVegaExposure,
        limit: this.config.maxVegaExposure,
      };

      if (!checks.vegaExposure.passed) {
        logger.warn('Risk check failed: Vega exposure exceeded', {
          current: newVegaExposure,
          limit: this.config.maxVegaExposure,
        });

        return {
          allowed: false,
          reason: 'Vega exposure limit exceeded',
          checks,
        };
      }

      // Delta exposure
      const deltaChange =
        greeks.delta *
        orderIntent.quantity *
        (orderIntent.transactionType === 'BUY' ? 1 : -1);
      const newDeltaExposure = Math.abs(this.currentDeltaExposure + deltaChange);

      checks.deltaExposure = {
        passed: newDeltaExposure <= this.config.maxDeltaExposure,
        current: newDeltaExposure,
        limit: this.config.maxDeltaExposure,
      };

      if (!checks.deltaExposure.passed) {
        logger.warn('Risk check failed: Delta exposure exceeded', {
          current: newDeltaExposure,
          limit: this.config.maxDeltaExposure,
        });

        return {
          allowed: false,
          reason: 'Delta exposure limit exceeded',
          checks,
        };
      }
    }

    // Check 5: Margin availability (if margin data provided)
    if (availableMargin !== undefined) {
      const requiredMargin = orderValue * (this.config.marginBufferPercent / 100);

      checks.marginAvailable = {
        passed: availableMargin >= requiredMargin,
        current: availableMargin,
        required: requiredMargin,
      };

      if (!checks.marginAvailable.passed) {
        logger.warn('Risk check failed: Insufficient margin', {
          available: availableMargin,
          required: requiredMargin,
        });

        return {
          allowed: false,
          reason: 'Insufficient margin available',
          checks,
        };
      }
    }

    logger.info('Risk check passed', {
      symbol: orderIntent.symbol,
      orderValue,
    });

    return {
      allowed: true,
      checks,
    };
  }

  /**
   * Calculate position size based on risk parameters
   */
  calculatePositionSize(
    price: number,
    riskAmount: number,
    stopLoss: number
  ): number {
    // Position size = Risk Amount / (Entry Price - Stop Loss)
    const riskPerUnit = Math.abs(price - stopLoss);

    if (riskPerUnit === 0) {
      logger.warn('Cannot calculate position size: Stop loss equals entry price');
      return 0;
    }

    const calculatedSize = Math.floor(riskAmount / riskPerUnit);

    // Apply position size limit
    const finalSize = Math.min(calculatedSize, this.config.maxPositionSize);

    logger.info('Position size calculated', {
      price,
      stopLoss,
      riskAmount,
      calculatedSize,
      finalSize,
    });

    return finalSize;
  }

  /**
   * Update current exposure after order execution
   */
  updateExposure(
    symbol: string,
    quantity: number,
    price: number,
    transactionType: 'BUY' | 'SELL',
    greeks?: Greeks
  ): void {
    const exposure = quantity * price;

    if (transactionType === 'BUY') {
      this.currentExposure += exposure;
    } else {
      this.currentExposure = Math.max(0, this.currentExposure - exposure);
    }

    // Update greeks exposure
    if (greeks) {
      const vegaChange = Math.abs(greeks.vega * quantity);
      const deltaChange =
        greeks.delta * quantity * (transactionType === 'BUY' ? 1 : -1);

      if (transactionType === 'BUY') {
        this.currentVegaExposure += vegaChange;
        this.currentDeltaExposure += deltaChange;
      } else {
        this.currentVegaExposure = Math.max(0, this.currentVegaExposure - vegaChange);
        this.currentDeltaExposure -= deltaChange;
      }
    }

    logger.info('Exposure updated', {
      symbol,
      currentExposure: this.currentExposure,
      currentVegaExposure: this.currentVegaExposure,
      currentDeltaExposure: this.currentDeltaExposure,
    });
  }

  /**
   * Update positions from broker
   */
  updatePositions(positions: Position[]): void {
    this.positions.clear();
    this.currentExposure = 0;

    for (const position of positions) {
      this.positions.set(position.tradingSymbol, position);
      this.currentExposure += Math.abs(position.value);
    }

    logger.info('Positions updated', {
      count: positions.length,
      totalExposure: this.currentExposure,
    });
  }

  /**
   * Get current risk metrics
   */
  getRiskMetrics(): {
    currentExposure: number;
    maxExposure: number;
    utilizationPercent: number;
    currentVegaExposure: number;
    currentDeltaExposure: number;
    positionCount: number;
  } {
    return {
      currentExposure: this.currentExposure,
      maxExposure: this.config.maxTotalExposure,
      utilizationPercent: (this.currentExposure / this.config.maxTotalExposure) * 100,
      currentVegaExposure: this.currentVegaExposure,
      currentDeltaExposure: this.currentDeltaExposure,
      positionCount: this.positions.size,
    };
  }

  /**
   * Reset risk state (useful for testing)
   */
  reset(): void {
    this.currentExposure = 0;
    this.currentVegaExposure = 0;
    this.currentDeltaExposure = 0;
    this.positions.clear();
    logger.info('RiskManager reset');
  }
}

export default RiskManager;
