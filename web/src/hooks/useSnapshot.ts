// Base del panel: portado de src/coordinator/web/panel.html

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getContext,
  postCitizenReport,
  postDecision,
  postPreload,
  postReports,
  postReset,
  postReview,
  type CitizenReportBody,
  type CoordinatorSnapshot,
  type DecisionBody,
} from "../lib/api";

const CORRECT_DEFAULT_COMMENT = "Ajuste solicitado por el coordinador";

export function useSnapshot() {
  const [snapshot, setSnapshot] = useState<CoordinatorSnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const preloadAttempted = useRef(false);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const ctx = await getContext();
      setSnapshot(ctx);
      return ctx;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      throw err;
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const ctx = await refresh();
        if (
          !preloadAttempted.current &&
          ctx.state == null &&
          ctx.clusters.length === 0
        ) {
          preloadAttempted.current = true;
          setBusy(true);
          try {
            const loaded = await postPreload();
            setSnapshot(loaded);
          } catch (preloadErr) {
            const message =
              preloadErr instanceof Error
                ? preloadErr.message
                : String(preloadErr);
            setError(message);
          } finally {
            setBusy(false);
          }
        }
      } catch {
        /* refresh already stored error */
      }
    })();
  }, [refresh]);

  const preload = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const ctx = await postPreload();
      setSnapshot(ctx);
      return ctx;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      throw err;
    } finally {
      setBusy(false);
    }
  }, []);

  const reset = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const ctx = await postReset();
      setSnapshot(ctx);
      return ctx;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      throw err;
    } finally {
      setBusy(false);
    }
  }, []);

  const loadReports = useCallback(async (texts: string[]) => {
    setBusy(true);
    setError(null);
    try {
      const ctx = await postReports(texts);
      setSnapshot(ctx);
      return ctx;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      throw err;
    } finally {
      setBusy(false);
    }
  }, []);

  const review = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const ctx = await postReview();
      setSnapshot(ctx);
      return ctx;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      throw err;
    } finally {
      setBusy(false);
    }
  }, []);

  const decide = useCallback(
    async (
      action: DecisionBody["action"],
      actor: string,
      comment?: string,
    ) => {
      if (!snapshot?.plan?.plan_id) {
        throw new Error("No hay un plan cargado.");
      }
      let finalComment = comment ?? "";
      if (action === "CORRECT" && !finalComment.trim()) {
        finalComment = CORRECT_DEFAULT_COMMENT;
      }
      setBusy(true);
      setError(null);
      try {
        const ctx = await postDecision({
          plan_id: snapshot.plan.plan_id,
          action,
          actor: actor.trim() || "coordinador",
          comment: finalComment,
        });
        setSnapshot(ctx);
        return ctx;
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setError(message);
        throw err;
      } finally {
        setBusy(false);
      }
    },
    [snapshot],
  );

  const submitCitizen = useCallback(async (body: CitizenReportBody) => {
    setBusy(true);
    setError(null);
    try {
      const ctx = await postCitizenReport(body);
      setSnapshot(ctx);
      return ctx;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      throw err;
    } finally {
      setBusy(false);
    }
  }, []);

  return {
    snapshot,
    busy,
    error,
    refresh,
    preload,
    reset,
    loadReports,
    review,
    decide,
    submitCitizen,
  };
}
