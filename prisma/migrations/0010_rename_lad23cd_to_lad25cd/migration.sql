-- Rename lad23cd column to lad25cd (LAD 2023 → LAD 2025 code vintage)
ALTER TABLE "published"."providers" RENAME COLUMN "lad23cd" TO "lad25cd";

-- Rename index to match
ALTER INDEX "published"."idx_providers_lad23cd" RENAME TO "idx_providers_lad25cd";
