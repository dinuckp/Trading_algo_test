import { Greeks } from '../types';
import { logger } from '../utils/logger';

/**
 * Black-Scholes Option Pricing and Greeks Calculator
 *
 * Calculates option Greeks using Black-Scholes model:
 * - Delta: Rate of change of option price with respect to underlying price
 * - Gamma: Rate of change of delta with respect to underlying price
 * - Theta: Rate of change of option price with respect to time
 * - Vega: Rate of change of option price with respect to volatility
 * - Rho: Rate of change of option price with respect to interest rate
 */

const SQRT_2PI = Math.sqrt(2 * Math.PI);

/**
 * Standard normal probability density function
 */
function normalPDF(x: number): number {
  return Math.exp(-0.5 * x * x) / SQRT_2PI;
}

/**
 * Cumulative distribution function for standard normal distribution
 * Using approximation by Abramowitz and Stegun
 */
function normalCDF(x: number): number {
  const t = 1 / (1 + 0.2316419 * Math.abs(x));
  const d = 0.3989423 * Math.exp((-x * x) / 2);
  const prob =
    d *
    t *
    (0.3193815 +
      t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));

  return x > 0 ? 1 - prob : prob;
}

/**
 * Calculate d1 for Black-Scholes formula
 */
function calculateD1(
  spotPrice: number,
  strikePrice: number,
  timeToExpiry: number,
  volatility: number,
  riskFreeRate: number
): number {
  const numerator =
    Math.log(spotPrice / strikePrice) +
    (riskFreeRate + (volatility * volatility) / 2) * timeToExpiry;
  const denominator = volatility * Math.sqrt(timeToExpiry);

  return numerator / denominator;
}

/**
 * Calculate d2 for Black-Scholes formula
 */
function calculateD2(
  d1: number,
  volatility: number,
  timeToExpiry: number
): number {
  return d1 - volatility * Math.sqrt(timeToExpiry);
}

/**
 * Calculate option price using Black-Scholes model
 */
export function calculateOptionPrice(
  spotPrice: number,
  strikePrice: number,
  timeToExpiry: number,
  volatility: number,
  riskFreeRate: number,
  optionType: 'CE' | 'PE'
): number {
  if (timeToExpiry <= 0) {
    // At expiration, option value is intrinsic value
    if (optionType === 'CE') {
      return Math.max(0, spotPrice - strikePrice);
    } else {
      return Math.max(0, strikePrice - spotPrice);
    }
  }

  const d1 = calculateD1(spotPrice, strikePrice, timeToExpiry, volatility, riskFreeRate);
  const d2 = calculateD2(d1, volatility, timeToExpiry);

  if (optionType === 'CE') {
    // Call option
    return (
      spotPrice * normalCDF(d1) -
      strikePrice * Math.exp(-riskFreeRate * timeToExpiry) * normalCDF(d2)
    );
  } else {
    // Put option
    return (
      strikePrice * Math.exp(-riskFreeRate * timeToExpiry) * normalCDF(-d2) -
      spotPrice * normalCDF(-d1)
    );
  }
}

/**
 * Calculate all Greeks for an option
 */
export function calculateGreeks(
  spotPrice: number,
  strikePrice: number,
  timeToExpiry: number,
  volatility: number,
  riskFreeRate: number,
  optionType: 'CE' | 'PE'
): Greeks {
  // Validate inputs
  if (spotPrice <= 0 || strikePrice <= 0) {
    throw new Error('Spot price and strike price must be positive');
  }

  if (volatility <= 0) {
    throw new Error('Volatility must be positive');
  }

  if (timeToExpiry < 0) {
    throw new Error('Time to expiry cannot be negative');
  }

  // Handle expired options
  if (timeToExpiry === 0) {
    return {
      delta: 0,
      gamma: 0,
      theta: 0,
      vega: 0,
      rho: 0,
    };
  }

  const d1 = calculateD1(spotPrice, strikePrice, timeToExpiry, volatility, riskFreeRate);
  const d2 = calculateD2(d1, volatility, timeToExpiry);
  const sqrtT = Math.sqrt(timeToExpiry);
  const pdf_d1 = normalPDF(d1);
  const cdf_d1 = normalCDF(d1);
  const cdf_d2 = normalCDF(d2);

  // Delta
  let delta: number;
  if (optionType === 'CE') {
    delta = cdf_d1;
  } else {
    delta = cdf_d1 - 1; // or -normalCDF(-d1)
  }

  // Gamma (same for calls and puts)
  const gamma = pdf_d1 / (spotPrice * volatility * sqrtT);

  // Vega (same for calls and puts)
  // Vega is typically expressed per 1% change in volatility
  const vega = (spotPrice * pdf_d1 * sqrtT) / 100;

  // Theta
  let theta: number;
  const term1 = -(spotPrice * pdf_d1 * volatility) / (2 * sqrtT);

  if (optionType === 'CE') {
    const term2 = riskFreeRate * strikePrice * Math.exp(-riskFreeRate * timeToExpiry) * cdf_d2;
    theta = (term1 - term2) / 365; // Per day
  } else {
    const term2 =
      riskFreeRate * strikePrice * Math.exp(-riskFreeRate * timeToExpiry) * normalCDF(-d2);
    theta = (term1 + term2) / 365; // Per day
  }

  // Rho (per 1% change in interest rate)
  let rho: number;
  if (optionType === 'CE') {
    rho = (strikePrice * timeToExpiry * Math.exp(-riskFreeRate * timeToExpiry) * cdf_d2) / 100;
  } else {
    rho =
      (-strikePrice * timeToExpiry * Math.exp(-riskFreeRate * timeToExpiry) * normalCDF(-d2)) /
      100;
  }

  return {
    delta,
    gamma,
    theta,
    vega,
    rho,
  };
}

/**
 * Calculate implied volatility using Newton-Raphson method
 * Returns the volatility that makes the Black-Scholes price equal to market price
 */
export function calculateImpliedVolatility(
  marketPrice: number,
  spotPrice: number,
  strikePrice: number,
  timeToExpiry: number,
  riskFreeRate: number,
  optionType: 'CE' | 'PE',
  maxIterations: number = 100,
  tolerance: number = 0.0001
): number | null {
  // Initial guess using Brenner-Subrahmanyam approximation
  let sigma = Math.sqrt((2 * Math.PI) / timeToExpiry) * (marketPrice / spotPrice);

  // Bounds for volatility search
  const MIN_VOL = 0.01; // 1%
  const MAX_VOL = 5.0; // 500%

  for (let i = 0; i < maxIterations; i++) {
    try {
      const price = calculateOptionPrice(
        spotPrice,
        strikePrice,
        timeToExpiry,
        sigma,
        riskFreeRate,
        optionType
      );

      const diff = price - marketPrice;

      // Check convergence
      if (Math.abs(diff) < tolerance) {
        return sigma;
      }

      // Calculate vega for Newton-Raphson
      const vega =
        (spotPrice *
          normalPDF(
            calculateD1(spotPrice, strikePrice, timeToExpiry, sigma, riskFreeRate)
          ) *
          Math.sqrt(timeToExpiry)) /
        100;

      if (vega < 1e-10) {
        logger.warn('Vega too small, IV calculation failed');
        return null;
      }

      // Newton-Raphson update
      sigma = sigma - diff / (vega * 100);

      // Keep sigma within bounds
      sigma = Math.max(MIN_VOL, Math.min(MAX_VOL, sigma));
    } catch (error) {
      logger.error('Error calculating implied volatility', { error });
      return null;
    }
  }

  logger.warn('Implied volatility calculation did not converge', {
    marketPrice,
    spotPrice,
    strikePrice,
    iterations: maxIterations,
  });

  return null;
}

/**
 * Calculate time to expiry in years
 */
export function calculateTimeToExpiry(expiryDate: Date): number {
  const now = new Date();
  const diffMs = expiryDate.getTime() - now.getTime();
  const diffDays = diffMs / (1000 * 60 * 60 * 24);

  // Convert to years (using 365 days)
  return Math.max(0, diffDays / 365);
}

/**
 * Utility to format Greeks for display
 */
export function formatGreeks(greeks: Greeks): string {
  return `Delta: ${greeks.delta.toFixed(4)}, Gamma: ${greeks.gamma.toFixed(6)}, Vega: ${greeks.vega.toFixed(4)}, Theta: ${greeks.theta.toFixed(4)}, Rho: ${greeks.rho.toFixed(4)}`;
}

export default {
  calculateGreeks,
  calculateOptionPrice,
  calculateImpliedVolatility,
  calculateTimeToExpiry,
  formatGreeks,
};
