import type { FormLocalStorageData } from "@/types/formData";

export type {
  AgeBracket,
  WorkingStatus,
  ResidencyStatus,
  CareTypeId,
  StudyLevel,
  PersonData,
  ChildcareSelection,
  ChildData,
  LocalStorageData,
} from "@bsil/calculator";

export interface Family {
  description: string;
  localStorage: FormLocalStorageData;
}

export interface FamilyMeta {
  id: string;
  filename: string;
  label: string;
  shortDescription: string;
}
