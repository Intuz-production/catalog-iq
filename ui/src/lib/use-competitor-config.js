/**
 * CatalogIQ — Hook to load competitor monitoring config from the backend.
 */

import { useState, useEffect, useCallback } from "react";
import { fetchCompetitorConfig } from "../api/client";

/**
 * Load and cache competitor config (region, marketplaces, exchange rate).
 */
export function useCompetitorConfig() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchCompetitorConfig({ force: true });
      setConfig(data);
      return data;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchCompetitorConfig();
        if (!cancelled) {
          setConfig(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, []);

  return { config, loading, error, reload };
}
