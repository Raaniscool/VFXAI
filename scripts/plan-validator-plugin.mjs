import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import Ajv from "ajv";
import standaloneCode from "ajv/dist/standalone/index.js";
import ucs2length from "ajv/dist/runtime/ucs2length.js";

// The same schema/rules as Node tests, compiled at bundle time so the sandboxed
// desktop renderer does not need eval/new Function or a weakened script CSP.
export function planValidatorPlugin() {
  const target = fileURLToPath(
    new URL("../src/plan-validator.js", import.meta.url),
  );
  return {
    name: "vfxai-static-plan-validator",
    enforce: "pre",
    transform(_source, id) {
      if (
        id.split("?")[0].replaceAll("\\", "/") !== target.replaceAll("\\", "/")
      )
        return;
      const schema = JSON.parse(
        readFileSync(
          new URL("../schemas/plan-v1.schema.json", import.meta.url),
          "utf8",
        ),
      );
      const ajv = new Ajv({
        allErrors: true,
        strict: false,
        strictNumbers: true,
        code: { source: true, esm: true },
      });
      const lengthFunction = ucs2length.default ?? ucs2length;
      const code = standaloneCode(ajv, ajv.compile(schema)).replaceAll(
        'require("ajv/dist/runtime/ucs2length").default',
        `(${lengthFunction.toString()})`,
      );
      if (/\brequire\(/.test(code))
        throw new Error(
          "Add an explicit standalone helper for the updated plan schema.",
        );
      return { code, map: null };
    },
  };
}
