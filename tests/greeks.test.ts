import {
  calculateGreeks,
  calculateOptionPrice,
  calculateImpliedVolatility,
  calculateTimeToExpiry,
} from '../src/options/greeks';

describe('Greeks Calculator', () => {
  const spotPrice = 20000;
  const strikePrice = 20000; // ATM
  const timeToExpiry = 30 / 365; // 30 days
  const volatility = 0.15; // 15%
  const riskFreeRate = 0.065; // 6.5%

  describe('calculateOptionPrice', () => {
    it('should calculate call option price', () => {
      const price = calculateOptionPrice(
        spotPrice,
        strikePrice,
        timeToExpiry,
        volatility,
        riskFreeRate,
        'CE'
      );

      expect(price).toBeGreaterThan(0);
      expect(price).toBeLessThan(spotPrice);
    });

    it('should calculate put option price', () => {
      const price = calculateOptionPrice(
        spotPrice,
        strikePrice,
        timeToExpiry,
        volatility,
        riskFreeRate,
        'PE'
      );

      expect(price).toBeGreaterThan(0);
      expect(price).toBeLessThan(spotPrice);
    });

    it('should calculate intrinsic value for ITM call at expiry', () => {
      const price = calculateOptionPrice(
        20100,
        20000,
        0,
        volatility,
        riskFreeRate,
        'CE'
      );

      expect(price).toBe(100); // Intrinsic value
    });

    it('should calculate intrinsic value for ITM put at expiry', () => {
      const price = calculateOptionPrice(
        19900,
        20000,
        0,
        volatility,
        riskFreeRate,
        'PE'
      );

      expect(price).toBe(100); // Intrinsic value
    });

    it('should return 0 for OTM option at expiry', () => {
      const callPrice = calculateOptionPrice(
        19900,
        20000,
        0,
        volatility,
        riskFreeRate,
        'CE'
      );

      const putPrice = calculateOptionPrice(
        20100,
        20000,
        0,
        volatility,
        riskFreeRate,
        'PE'
      );

      expect(callPrice).toBe(0);
      expect(putPrice).toBe(0);
    });
  });

  describe('calculateGreeks', () => {
    it('should calculate all greeks for call option', () => {
      const greeks = calculateGreeks(
        spotPrice,
        strikePrice,
        timeToExpiry,
        volatility,
        riskFreeRate,
        'CE'
      );

      expect(greeks).toHaveProperty('delta');
      expect(greeks).toHaveProperty('gamma');
      expect(greeks).toHaveProperty('theta');
      expect(greeks).toHaveProperty('vega');
      expect(greeks).toHaveProperty('rho');

      // ATM call delta should be around 0.5
      expect(greeks.delta).toBeGreaterThan(0.3);
      expect(greeks.delta).toBeLessThan(0.7);

      // Gamma should be positive
      expect(greeks.gamma).toBeGreaterThan(0);

      // Theta should be negative for long options
      expect(greeks.theta).toBeLessThan(0);

      // Vega should be positive
      expect(greeks.vega).toBeGreaterThan(0);
    });

    it('should calculate all greeks for put option', () => {
      const greeks = calculateGreeks(
        spotPrice,
        strikePrice,
        timeToExpiry,
        volatility,
        riskFreeRate,
        'PE'
      );

      // ATM put delta should be around -0.5
      expect(greeks.delta).toBeLessThan(0);
      expect(greeks.delta).toBeGreaterThan(-0.7);

      // Gamma should be positive (same as call)
      expect(greeks.gamma).toBeGreaterThan(0);

      // Theta should be negative
      expect(greeks.theta).toBeLessThan(0);

      // Vega should be positive
      expect(greeks.vega).toBeGreaterThan(0);
    });

    it('should return zero greeks for expired option', () => {
      const greeks = calculateGreeks(
        spotPrice,
        strikePrice,
        0,
        volatility,
        riskFreeRate,
        'CE'
      );

      expect(greeks.delta).toBe(0);
      expect(greeks.gamma).toBe(0);
      expect(greeks.theta).toBe(0);
      expect(greeks.vega).toBe(0);
      expect(greeks.rho).toBe(0);
    });

    it('should throw error for invalid inputs', () => {
      expect(() =>
        calculateGreeks(0, strikePrice, timeToExpiry, volatility, riskFreeRate, 'CE')
      ).toThrow();

      expect(() =>
        calculateGreeks(spotPrice, 0, timeToExpiry, volatility, riskFreeRate, 'CE')
      ).toThrow();

      expect(() =>
        calculateGreeks(spotPrice, strikePrice, timeToExpiry, 0, riskFreeRate, 'CE')
      ).toThrow();

      expect(() =>
        calculateGreeks(spotPrice, strikePrice, -1, volatility, riskFreeRate, 'CE')
      ).toThrow();
    });

    it('should calculate higher delta for ITM call', () => {
      const itmGreeks = calculateGreeks(
        20500,
        20000,
        timeToExpiry,
        volatility,
        riskFreeRate,
        'CE'
      );

      const atmGreeks = calculateGreeks(
        20000,
        20000,
        timeToExpiry,
        volatility,
        riskFreeRate,
        'CE'
      );

      expect(itmGreeks.delta).toBeGreaterThan(atmGreeks.delta);
    });

    it('should calculate lower delta for OTM call', () => {
      const otmGreeks = calculateGreeks(
        19500,
        20000,
        timeToExpiry,
        volatility,
        riskFreeRate,
        'CE'
      );

      const atmGreeks = calculateGreeks(
        20000,
        20000,
        timeToExpiry,
        volatility,
        riskFreeRate,
        'CE'
      );

      expect(otmGreeks.delta).toBeLessThan(atmGreeks.delta);
    });
  });

  describe('calculateImpliedVolatility', () => {
    it('should calculate implied volatility for call option', () => {
      // First calculate a price with known volatility
      const theoreticalPrice = calculateOptionPrice(
        spotPrice,
        strikePrice,
        timeToExpiry,
        volatility,
        riskFreeRate,
        'CE'
      );

      // Then calculate IV
      const iv = calculateImpliedVolatility(
        theoreticalPrice,
        spotPrice,
        strikePrice,
        timeToExpiry,
        riskFreeRate,
        'CE'
      );

      expect(iv).not.toBeNull();
      if (iv !== null) {
        // Should be close to the original volatility
        expect(Math.abs(iv - volatility)).toBeLessThan(0.01);
      }
    });

    it('should calculate implied volatility for put option', () => {
      const theoreticalPrice = calculateOptionPrice(
        spotPrice,
        strikePrice,
        timeToExpiry,
        volatility,
        riskFreeRate,
        'PE'
      );

      const iv = calculateImpliedVolatility(
        theoreticalPrice,
        spotPrice,
        strikePrice,
        timeToExpiry,
        riskFreeRate,
        'PE'
      );

      expect(iv).not.toBeNull();
      if (iv !== null) {
        expect(Math.abs(iv - volatility)).toBeLessThan(0.01);
      }
    });

    it('should return null for invalid market price', () => {
      const iv = calculateImpliedVolatility(
        0,
        spotPrice,
        strikePrice,
        timeToExpiry,
        riskFreeRate,
        'CE'
      );

      // Should either return null or a very low value
      expect(iv === null || iv < 0.01).toBe(true);
    });
  });

  describe('calculateTimeToExpiry', () => {
    it('should calculate time to expiry in years', () => {
      const futureDate = new Date();
      futureDate.setDate(futureDate.getDate() + 30);

      const timeToExpiry = calculateTimeToExpiry(futureDate);

      expect(timeToExpiry).toBeGreaterThan(0);
      expect(timeToExpiry).toBeLessThan(1); // Less than a year
      expect(timeToExpiry).toBeCloseTo(30 / 365, 2);
    });

    it('should return 0 for past dates', () => {
      const pastDate = new Date();
      pastDate.setDate(pastDate.getDate() - 1);

      const timeToExpiry = calculateTimeToExpiry(pastDate);

      expect(timeToExpiry).toBe(0);
    });

    it('should return 0 for current date', () => {
      const now = new Date();

      const timeToExpiry = calculateTimeToExpiry(now);

      expect(timeToExpiry).toBeGreaterThanOrEqual(0);
      expect(timeToExpiry).toBeLessThan(1 / 365);
    });
  });

  describe('Put-Call Parity', () => {
    it('should satisfy put-call parity relationship', () => {
      const callPrice = calculateOptionPrice(
        spotPrice,
        strikePrice,
        timeToExpiry,
        volatility,
        riskFreeRate,
        'CE'
      );

      const putPrice = calculateOptionPrice(
        spotPrice,
        strikePrice,
        timeToExpiry,
        volatility,
        riskFreeRate,
        'PE'
      );

      // Put-Call Parity: C - P = S - K*e^(-r*T)
      const leftSide = callPrice - putPrice;
      const rightSide =
        spotPrice - strikePrice * Math.exp(-riskFreeRate * timeToExpiry);

      expect(Math.abs(leftSide - rightSide)).toBeLessThan(1);
    });
  });
});
