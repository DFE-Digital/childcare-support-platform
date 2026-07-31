export type TransitionDirection = "gain" | "loss";

export interface SchemeTransition {
  schemeId: string;
  direction: TransitionDirection;
  /** The date the eligibility change takes effect. */
  effectiveDate: Date;
  /** Human-readable date label, e.g. "September 2027". */
  effectiveDateLabel: string;
  /** Child's age in months at the effective date. */
  ageAtTransitionMonths: number;
}

export interface ChildTimeline {
  childId: number;
  childName: string;
  transitions: SchemeTransition[];
}

export interface TimelineResult {
  children: ChildTimeline[];
}
