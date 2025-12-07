import { RiskManager } from '../src/order/riskManager';
import { OrderIntent, Greeks } from '../src/types';

describe('RiskManager', () => {
  let riskManager: RiskManager;

  const mockOrderIntent: OrderIntent = {
    symbol: 'NIFTY24DEC20000CE',
    instrumentToken: 12345,
    exchange: 'NFO',
    transactionType: 'BUY',
    quantity: 25,
    orderType: 'MARKET',
    product: 'NRML',
    variety: 'regular',
  };

  const mockGreeks: Greeks = {
    delta: 0.5,
    gamma: 0.002,
    theta: -15,
    vega: 120,
    rho: 8,
  };

  beforeEach(() => {
    riskManager = new RiskManager({
      maxTotalExposure: 100000,
      maxRiskPerTrade: 10000,
      maxPositionSize: 50,
      maxVegaExposure: 5000,
      maxDeltaExposure: 100,
      marginBufferPercent: 20,
    });
  });

  afterEach(() => {
    riskManager.reset();
  });

  describe('Total exposure check', () => {
    it('should allow order within exposure limit', () => {
      const result = riskManager.checkOrder(mockOrderIntent, 100, mockGreeks);

      expect(result.allowed).toBe(true);
      expect(result.checks.totalExposure.passed).toBe(true);
    });

    it('should block order exceeding exposure limit', () => {
      const result = riskManager.checkOrder(mockOrderIntent, 5000, mockGreeks);

      expect(result.allowed).toBe(false);
      expect(result.reason).toContain('Total exposure');
      expect(result.checks.totalExposure.passed).toBe(false);
    });

    it('should track cumulative exposure', () => {
      // First order
      riskManager.checkOrder(mockOrderIntent, 100);
      riskManager.updateExposure('TEST1', 25, 100, 'BUY');

      // Second order should consider existing exposure
      const result = riskManager.checkOrder(mockOrderIntent, 3500);

      expect(result.checks.totalExposure.current).toBeGreaterThan(2500);
    });
  });

  describe('Trade risk check', () => {
    it('should allow order within trade risk limit', () => {
      const result = riskManager.checkOrder(mockOrderIntent, 200, mockGreeks);

      expect(result.allowed).toBe(true);
      expect(result.checks.tradeRisk.passed).toBe(true);
    });

    it('should block order exceeding trade risk limit', () => {
      const result = riskManager.checkOrder(mockOrderIntent, 500, mockGreeks);

      expect(result.allowed).toBe(false);
      expect(result.reason).toContain('Trade risk');
      expect(result.checks.tradeRisk.passed).toBe(false);
    });
  });

  describe('Position size check', () => {
    it('should allow order within position size limit', () => {
      const result = riskManager.checkOrder(mockOrderIntent, 100, mockGreeks);

      expect(result.allowed).toBe(true);
      expect(result.checks.positionSize.passed).toBe(true);
    });

    it('should block order exceeding position size limit', () => {
      const largeOrder = { ...mockOrderIntent, quantity: 100 };
      const result = riskManager.checkOrder(largeOrder, 100, mockGreeks);

      expect(result.allowed).toBe(false);
      expect(result.reason).toContain('Position size');
      expect(result.checks.positionSize.passed).toBe(false);
    });
  });

  describe('Vega exposure check', () => {
    it('should allow order within vega limit', () => {
      const result = riskManager.checkOrder(mockOrderIntent, 100, mockGreeks);

      expect(result.allowed).toBe(true);
      expect(result.checks.vegaExposure?.passed).toBe(true);
    });

    it('should block order exceeding vega limit', () => {
      const highVegaGreeks = { ...mockGreeks, vega: 250 };
      const result = riskManager.checkOrder(
        mockOrderIntent,
        100,
        highVegaGreeks
      );

      expect(result.allowed).toBe(false);
      expect(result.reason).toContain('Vega exposure');
      expect(result.checks.vegaExposure?.passed).toBe(false);
    });
  });

  describe('Delta exposure check', () => {
    it('should allow order within delta limit', () => {
      const result = riskManager.checkOrder(mockOrderIntent, 100, mockGreeks);

      expect(result.allowed).toBe(true);
      expect(result.checks.deltaExposure?.passed).toBe(true);
    });

    it('should block order exceeding delta limit', () => {
      const highDeltaGreeks = { ...mockGreeks, delta: 5 };
      const result = riskManager.checkOrder(
        mockOrderIntent,
        100,
        highDeltaGreeks
      );

      expect(result.allowed).toBe(false);
      expect(result.reason).toContain('Delta exposure');
      expect(result.checks.deltaExposure?.passed).toBe(false);
    });
  });

  describe('Margin check', () => {
    it('should allow order with sufficient margin', () => {
      const availableMargin = 10000;
      const result = riskManager.checkOrder(
        mockOrderIntent,
        100,
        mockGreeks,
        availableMargin
      );

      expect(result.allowed).toBe(true);
      expect(result.checks.marginAvailable?.passed).toBe(true);
    });

    it('should block order with insufficient margin', () => {
      const availableMargin = 100;
      const result = riskManager.checkOrder(
        mockOrderIntent,
        100,
        mockGreeks,
        availableMargin
      );

      expect(result.allowed).toBe(false);
      expect(result.reason).toContain('Insufficient margin');
      expect(result.checks.marginAvailable?.passed).toBe(false);
    });
  });

  describe('calculatePositionSize', () => {
    it('should calculate position size based on risk', () => {
      const size = riskManager.calculatePositionSize(100, 1000, 90);

      expect(size).toBeGreaterThan(0);
      expect(size).toBeLessThanOrEqual(50); // Max position size
    });

    it('should return 0 for invalid stop loss', () => {
      const size = riskManager.calculatePositionSize(100, 1000, 100);

      expect(size).toBe(0);
    });

    it('should respect max position size', () => {
      const size = riskManager.calculatePositionSize(100, 100000, 50);

      expect(size).toBeLessThanOrEqual(50);
    });
  });

  describe('updateExposure', () => {
    it('should update exposure after buy', () => {
      riskManager.updateExposure('TEST', 25, 100, 'BUY', mockGreeks);

      const metrics = riskManager.getRiskMetrics();

      expect(metrics.currentExposure).toBe(2500);
    });

    it('should update exposure after sell', () => {
      riskManager.updateExposure('TEST', 25, 100, 'BUY', mockGreeks);
      riskManager.updateExposure('TEST', 25, 100, 'SELL', mockGreeks);

      const metrics = riskManager.getRiskMetrics();

      expect(metrics.currentExposure).toBe(0);
    });

    it('should update greeks exposure', () => {
      riskManager.updateExposure('TEST', 25, 100, 'BUY', mockGreeks);

      const metrics = riskManager.getRiskMetrics();

      expect(metrics.currentVegaExposure).toBeGreaterThan(0);
      expect(metrics.currentDeltaExposure).toBeGreaterThan(0);
    });
  });

  describe('getRiskMetrics', () => {
    it('should return current risk metrics', () => {
      const metrics = riskManager.getRiskMetrics();

      expect(metrics).toHaveProperty('currentExposure');
      expect(metrics).toHaveProperty('maxExposure');
      expect(metrics).toHaveProperty('utilizationPercent');
      expect(metrics).toHaveProperty('currentVegaExposure');
      expect(metrics).toHaveProperty('currentDeltaExposure');
      expect(metrics).toHaveProperty('positionCount');

      expect(metrics.maxExposure).toBe(100000);
      expect(metrics.utilizationPercent).toBe(0);
    });
  });

  describe('reset', () => {
    it('should reset all exposure', () => {
      riskManager.updateExposure('TEST', 25, 100, 'BUY', mockGreeks);
      riskManager.reset();

      const metrics = riskManager.getRiskMetrics();

      expect(metrics.currentExposure).toBe(0);
      expect(metrics.currentVegaExposure).toBe(0);
      expect(metrics.currentDeltaExposure).toBe(0);
      expect(metrics.positionCount).toBe(0);
    });
  });
});
