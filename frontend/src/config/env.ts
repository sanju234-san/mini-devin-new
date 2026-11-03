/**
 * Environment configuration for the Mini-Devin frontend.
 * Reads environment variables with safe defaults for local development.
 */

export const NEXT_PUBLIC_API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const API_BASE_URL = NEXT_PUBLIC_API_URL;
