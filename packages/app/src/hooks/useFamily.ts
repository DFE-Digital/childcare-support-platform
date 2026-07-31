import { useContext } from "react";
import { FamilyContext } from "@/context/familyContextValue";
import type { FamilyContextValue } from "@/context/FamilyContext";

export function useFamily(): FamilyContextValue {
  const ctx = useContext(FamilyContext);
  if (!ctx) throw new Error("useFamily must be used within a FamilyProvider");
  return ctx;
}
