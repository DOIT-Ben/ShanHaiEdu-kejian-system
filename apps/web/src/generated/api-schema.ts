/**
 * The frontend consumes the single generated runtime contract owned by the
 * repository root. Keep this import-only bridge so feature code never creates
 * a second DTO or a hand-maintained API schema.
 */
export type {
  components,
  operations,
  paths,
} from "../../../../contracts/generated/typescript/schema";
