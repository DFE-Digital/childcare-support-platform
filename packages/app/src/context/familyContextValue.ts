import { createContext } from "react";
import type { FamilyContextValue } from "./FamilyContext";

export const FamilyContext = createContext<FamilyContextValue | null>(null);
