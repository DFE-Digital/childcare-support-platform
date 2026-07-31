export interface DevolvedNationLink {
  nation: string;
  url: string;
  label: string;
}

export interface SchemesData {
  schemes: Scheme[];
  caveatMessages: Record<string, { text: string; type: "warn" | "info" }>;
  devolvedNationLinks?: DevolvedNationLink[];
}

export interface Scheme {
  id: string;
  name: string;
  description: string;
  financialType: string;
  topUpRate?: number;
  maxGovernmentContributionPerYear?: number;
  maxGovernmentContributionPerYearDisabled?: number;
  reimbursementRate?: number;
  maxPerMonthOneChild?: number;
  maxPerMonthTwoOrMore?: number;
  defaultDescriptionParams?: Record<string, string>;
  allSchemesDescription?: string;
  links: {
    info?: string;
    apply?: string;
  };
  secondaryLinks?: Array<{ label: string; url: string }>;
  caveats: Array<{ text: string; type: "warn" | "info" }>;
  transitionDescriptions?: {
    gain?: string;
    loss?: string;
  };
}
