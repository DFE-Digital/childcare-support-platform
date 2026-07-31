-- Add CMA (Childminder Agency) inspection fields
ALTER TABLE "published"."providers" ADD COLUMN "cma_agency" TEXT;
ALTER TABLE "published"."providers" ADD COLUMN "cma_qa_grading" TEXT;
ALTER TABLE "published"."providers" ADD COLUMN "cma_inspection_date" DATE;
