export interface Caveat {
  code: string;
  params?: Record<string, string>;
}

export interface SchemeEntitlement {
  schemeId: string;
  eligible: boolean;
  reasons: string[];
  caveats: Caveat[];
  descriptionParams?: Record<string, string>;
}

export interface ChildEntitlement {
  childId: number;
  childName: string;
  schemes: SchemeEntitlement[];
}

export interface EntitlementResult {
  children: ChildEntitlement[];
}
