-- AlterTable
ALTER TABLE "published"."care_types" ALTER COLUMN "session_hours_morning" SET DATA TYPE DECIMAL(5,2),
ALTER COLUMN "session_hours_afternoon" SET DATA TYPE DECIMAL(5,2),
ALTER COLUMN "session_hours_full_day" SET DATA TYPE DECIMAL(5,2);

