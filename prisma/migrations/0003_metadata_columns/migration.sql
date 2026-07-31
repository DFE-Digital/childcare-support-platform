-- AddColumn
ALTER TABLE "published"."care_types" ADD COLUMN "metadata" JSONB NOT NULL DEFAULT '{}';

-- AddColumn
ALTER TABLE "published"."fee_rates" ADD COLUMN "metadata" JSONB NOT NULL DEFAULT '{}';
