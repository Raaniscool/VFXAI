import Ajv from "ajv";
import schema from "../schemas/plan-v1.schema.json" with { type: "json" };

// Node/test entry. Vite substitutes an equivalent standalone validator generated
// from this schema at build time; the browser bundle requires no runtime compiler.
export default new Ajv({
  allErrors: true,
  strict: false,
  strictNumbers: true,
}).compile(schema);
