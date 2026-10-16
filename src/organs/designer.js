/**
 * Thin browser boundary for the Python neural Designer. The actual model,
 * training, checkpoint loading, and decoding live in vfxai/model.py and
 * vfxai/inference.py. This adapter never invents a fallback plan.
 */
export const designer = Object.freeze({
  id: "local-python-structured-mlp",
  planVersion: "1.0",
  async design(prompt, { checkpointId, seed } = {}) {
    try {
      const response = await fetch("/api/generate", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          checkpoint_id: checkpointId,
          seed,
        }),
      });
      const result = await response.json();
      if (!response.ok) {
        return {
          ok: false,
          plan: null,
          prediction: null,
          issues: [
            {
              code: "LOCAL_DESIGNER_ERROR",
              path: "/",
              message: result.error || `Local Designer request failed (${response.status}).`,
              correction: "Check the local Python server and selected checkpoint.",
            },
          ],
        };
      }
      return {
        ok: Boolean(result.validation?.ok),
        plan: result.candidate_plan,
        prediction: result,
        issues: result.validation?.issues || [],
      };
    } catch (error) {
      return {
        ok: false,
        plan: null,
        prediction: null,
        issues: [
          {
            code: "LOCAL_API_UNAVAILABLE",
            path: "/",
            message: `Local Python Designer is unavailable: ${error.message}`,
            correction: "Start the complete app with START_VFXAI.bat; npm run dev alone does not start the model server.",
          },
        ],
      };
    }
  },
});
