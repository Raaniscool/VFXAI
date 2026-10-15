import { reason } from "./organs/reasoner.js";
import { build } from "./organs/builder.js";
import { verify } from "./organs/verifier.js";

/** No automatic repair in M1: one attempt, explicit failure, no retry loop. */
export function construct(plan) {
  const reasoning = reason(plan);
  if (!reasoning.ok)
    return { ok: false, stage: "reasoner", issues: reasoning.issues };
  const built = build(plan);
  const verification = verify(plan, built);
  if (!verification.ok)
    return { ok: false, stage: "verifier", issues: verification.issues };
  return { ok: true, built, reasoning, verification };
}
