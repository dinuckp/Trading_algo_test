import KiteConnect from 'kiteconnect';
import fs from 'fs';
import path from 'path';
import { config } from '../config';
import { logger } from '../utils/logger';
import { KiteTokens, KiteProfile, OrderIntent, Instrument } from '../types';

/**
 * KiteClient - Wrapper for Kite Connect REST API
 * Handles authentication, token persistence, and order placement
 * NEVER logs sensitive information like API keys or tokens
 */

export class KiteClient {
  private kite: KiteConnect;
  private tokenPath: string;
  private tokens: KiteTokens | null = null;

  constructor(apiKey?: string, apiSecret?: string, tokenPath?: string) {
    const key = apiKey || config.kite.apiKey;
    const secret = apiSecret || config.kite.apiSecret;
    this.tokenPath = tokenPath || config.kite.tokenPath;

    if (!key || !secret) {
      throw new Error('Kite API key and secret are required');
    }

    this.kite = new KiteConnect({
      api_key: key,
      api_secret: secret,
    });

    logger.info('KiteClient initialized');
  }

  /**
   * Initialize session by loading saved tokens or requiring manual login
   * Returns the login URL if no valid tokens are found
   */
  async init(): Promise<{ loggedIn: boolean; loginUrl?: string }> {
    try {
      // Try to load existing tokens
      const loaded = await this.loadTokens();

      if (loaded && this.tokens) {
        // Check if token is still valid
        try {
          await this.refreshTokenIfNeeded();
          logger.info('Session initialized with existing tokens');
          return { loggedIn: true };
        } catch (error) {
          logger.warn('Existing tokens are invalid, requiring new login');
        }
      }

      // Generate login URL
      const loginUrl = this.kite.getLoginURL();
      logger.info('Login required. Use the provided login URL');
      return { loggedIn: false, loginUrl };
    } catch (error) {
      logger.error('Failed to initialize Kite client', { error });
      throw error;
    }
  }

  /**
   * Generate session using request token from login callback
   * Saves access token to disk for future use
   */
  async generateSession(requestToken: string): Promise<KiteTokens> {
    try {
      logger.info('Generating session with request token');

      const response = await this.kite.generateSession(requestToken);

      this.tokens = {
        accessToken: response.access_token,
        refreshToken: response.refresh_token,
        expiresAt: Date.now() + 24 * 60 * 60 * 1000, // 24 hours
      };

      // Set access token
      this.kite.setAccessToken(this.tokens.accessToken);

      // Save tokens to disk
      await this.saveTokens();

      logger.info('Session generated successfully');
      return this.tokens;
    } catch (error) {
      logger.error('Failed to generate session', { error });
      throw error;
    }
  }

  /**
   * Refresh access token if it's about to expire
   */
  async refreshTokenIfNeeded(): Promise<void> {
    if (!this.tokens) {
      throw new Error('No tokens available');
    }

    const now = Date.now();
    const expiresAt = this.tokens.expiresAt || 0;

    // Refresh if token expires in less than 1 hour
    if (expiresAt - now < 60 * 60 * 1000) {
      logger.info('Access token expiring soon, refreshing...');

      if (this.tokens.refreshToken) {
        try {
          const response = await this.kite.renewAccessToken(
            this.tokens.refreshToken,
            config.kite.apiSecret
          );

          this.tokens.accessToken = response.access_token;
          this.tokens.expiresAt = Date.now() + 24 * 60 * 60 * 1000;

          this.kite.setAccessToken(this.tokens.accessToken);
          await this.saveTokens();

          logger.info('Access token refreshed successfully');
        } catch (error) {
          logger.error('Failed to refresh access token', { error });
          throw error;
        }
      } else {
        logger.warn('No refresh token available');
      }
    }
  }

  /**
   * Get current access token
   */
  getAccessToken(): string | null {
    return this.tokens?.accessToken || null;
  }

  /**
   * Get user profile
   */
  async getProfile(): Promise<KiteProfile> {
    try {
      await this.refreshTokenIfNeeded();
      const profile = await this.kite.getProfile();
      logger.info('Retrieved user profile', { userId: profile.user_id });
      return profile as KiteProfile;
    } catch (error) {
      logger.error('Failed to get profile', { error });
      throw error;
    }
  }

  /**
   * Place an order
   * NOTE: This is a low-level method. Use OrderExecutor for safe order placement
   */
  async placeOrder(orderIntent: OrderIntent): Promise<{ order_id: string }> {
    try {
      await this.refreshTokenIfNeeded();

      const orderParams = {
        exchange: orderIntent.exchange,
        tradingsymbol: orderIntent.symbol,
        transaction_type: orderIntent.transactionType,
        quantity: orderIntent.quantity,
        order_type: orderIntent.orderType,
        product: orderIntent.product,
        variety: orderIntent.variety,
        price: orderIntent.price,
        trigger_price: orderIntent.triggerPrice,
        validity: orderIntent.validity || 'DAY',
        disclosed_quantity: orderIntent.disclosedQuantity,
        tag: orderIntent.tag,
      };

      logger.info('Placing order', {
        symbol: orderIntent.symbol,
        transaction: orderIntent.transactionType,
        quantity: orderIntent.quantity,
      });

      const response = await this.kite.placeOrder(orderIntent.variety, orderParams);

      logger.info('Order placed successfully', {
        orderId: response.order_id,
        symbol: orderIntent.symbol,
      });

      return response;
    } catch (error) {
      logger.error('Failed to place order', {
        error,
        symbol: orderIntent.symbol,
      });
      throw error;
    }
  }

  /**
   * Cancel an order
   */
  async cancelOrder(orderId: string, variety: OrderVariety = 'regular'): Promise<void> {
    try {
      await this.refreshTokenIfNeeded();
      await this.kite.cancelOrder(variety, orderId);
      logger.info('Order cancelled successfully', { orderId });
    } catch (error) {
      logger.error('Failed to cancel order', { error, orderId });
      throw error;
    }
  }

  /**
   * Get positions
   */
  async getPositions(): Promise<{ net: unknown[]; day: unknown[] }> {
    try {
      await this.refreshTokenIfNeeded();
      const positions = await this.kite.getPositions();
      return positions;
    } catch (error) {
      logger.error('Failed to get positions', { error });
      throw error;
    }
  }

  /**
   * Get holdings
   */
  async getHoldings(): Promise<unknown[]> {
    try {
      await this.refreshTokenIfNeeded();
      const holdings = await this.kite.getHoldings();
      return holdings;
    } catch (error) {
      logger.error('Failed to get holdings', { error });
      throw error;
    }
  }

  /**
   * Get instruments for an exchange
   */
  async getInstruments(exchange?: string): Promise<Instrument[]> {
    try {
      await this.refreshTokenIfNeeded();
      const instruments = await this.kite.getInstruments(exchange);
      return instruments as Instrument[];
    } catch (error) {
      logger.error('Failed to get instruments', { error, exchange });
      throw error;
    }
  }

  /**
   * Get margins
   */
  async getMargins(segment?: string): Promise<unknown> {
    try {
      await this.refreshTokenIfNeeded();
      const margins = segment
        ? await this.kite.getMargins(segment)
        : await this.kite.getMargins();
      return margins;
    } catch (error) {
      logger.error('Failed to get margins', { error, segment });
      throw error;
    }
  }

  /**
   * Save tokens to disk (encrypted storage would be better for production)
   */
  private async saveTokens(): Promise<void> {
    if (!this.tokens) return;

    try {
      const tokenDir = path.dirname(this.tokenPath);
      if (!fs.existsSync(tokenDir)) {
        fs.mkdirSync(tokenDir, { recursive: true });
      }

      // NOTE: In production, encrypt this file or use a secure key store
      fs.writeFileSync(this.tokenPath, JSON.stringify(this.tokens, null, 2), {
        mode: 0o600, // Only owner can read/write
      });

      logger.info('Tokens saved successfully');
    } catch (error) {
      logger.error('Failed to save tokens', { error });
      throw error;
    }
  }

  /**
   * Load tokens from disk
   */
  private async loadTokens(): Promise<boolean> {
    try {
      if (!fs.existsSync(this.tokenPath)) {
        logger.info('No saved tokens found');
        return false;
      }

      const data = fs.readFileSync(this.tokenPath, 'utf-8');
      this.tokens = JSON.parse(data) as KiteTokens;

      if (this.tokens.accessToken) {
        this.kite.setAccessToken(this.tokens.accessToken);
        logger.info('Tokens loaded successfully');
        return true;
      }

      return false;
    } catch (error) {
      logger.error('Failed to load tokens', { error });
      return false;
    }
  }

  /**
   * Clear saved tokens (logout)
   */
  async logout(): Promise<void> {
    try {
      if (fs.existsSync(this.tokenPath)) {
        fs.unlinkSync(this.tokenPath);
      }
      this.tokens = null;
      logger.info('Logged out successfully');
    } catch (error) {
      logger.error('Failed to logout', { error });
      throw error;
    }
  }
}

export default KiteClient;
