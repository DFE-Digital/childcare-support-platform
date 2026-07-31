-- CreateTable
CREATE TABLE "published"."opening_hours" (
    "id" BIGSERIAL NOT NULL,
    "care_type_id" BIGINT NOT NULL,
    "monday" BOOLEAN NOT NULL DEFAULT false,
    "tuesday" BOOLEAN NOT NULL DEFAULT false,
    "wednesday" BOOLEAN NOT NULL DEFAULT false,
    "thursday" BOOLEAN NOT NULL DEFAULT false,
    "friday" BOOLEAN NOT NULL DEFAULT false,
    "saturday" BOOLEAN NOT NULL DEFAULT false,
    "sunday" BOOLEAN NOT NULL DEFAULT false,
    "open" TIME NOT NULL,
    "close" TIME NOT NULL,

    CONSTRAINT "opening_hours_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "idx_opening_hours_care_type_id" ON "published"."opening_hours"("care_type_id");

-- AddForeignKey
ALTER TABLE "published"."opening_hours" ADD CONSTRAINT "opening_hours_care_type_id_fkey" FOREIGN KEY ("care_type_id") REFERENCES "published"."care_types"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AlterTable: remove old columns from care_types
ALTER TABLE "published"."care_types" DROP COLUMN "opening_hour_open";
ALTER TABLE "published"."care_types" DROP COLUMN "opening_hour_close";
