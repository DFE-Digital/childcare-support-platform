export type RoundingMode = "precise" | "nearest10";

function round2(x: number): number {
  return Math.round(x * 100) / 100;
}

function roundNearest10(x: number): number {
  return Math.round(x / 10) * 10;
}

export function getRoundFn(mode: RoundingMode): (x: number) => number {
  return mode === "nearest10" ? roundNearest10 : round2;
}
