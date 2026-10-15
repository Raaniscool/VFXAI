/** Replaceable Designer contract: design(prompt) -> {ok, plan, issues}.
 * No prompt interpretation or trained model is implemented in Milestone 1.
 */
export const designer = Object.freeze({
  id: "unavailable-milestone-1",
  planVersion: "1.0",
  async design(_prompt) {
    return {
      ok: false,
      plan: null,
      issues: [
        {
          code: "DESIGNER_UNAVAILABLE",
          path: "/",
          message: "Prompt interpretation is not implemented.",
          correction: "Load a manually authored plan 1.0.",
        },
      ],
    };
  },
});
