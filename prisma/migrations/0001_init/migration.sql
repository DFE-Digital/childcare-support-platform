-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "published";

-- CreateTable
CREATE TABLE "published"."providers" (
    "id" BIGINT NOT NULL,
    "name" TEXT,
    "address_line1" TEXT,
    "address_line2" TEXT,
    "city" TEXT,
    "postcode" TEXT,
    "latitude" DOUBLE PRECISION,
    "longitude" DOUBLE PRECISION,
    "bbox_geo_type" TEXT,
    "bbox_geo_code" TEXT,
    "phone" TEXT,
    "email" TEXT,
    "website" TEXT,
    "ofsted_legacy_rating" TEXT,
    "ofsted_inspection_date" DATE,
    "ofsted_framework" TEXT,
    "ofsted_safeguarding_met" BOOLEAN,
    "ofsted_achievement" TEXT,
    "ofsted_curriculum_and_teaching" TEXT,
    "ofsted_behaviour_attitudes_routines" TEXT,
    "ofsted_childrens_welfare_wellbeing" TEXT,
    "ofsted_attendance_and_behaviour" TEXT,
    "ofsted_personal_development_wellbeing" TEXT,
    "ofsted_inclusion" TEXT,
    "ofsted_leadership_and_governance" TEXT,
    "ofsted_early_years" TEXT,
    "ofsted_sixth_form" TEXT,
    "ofsted_legacy_quality_of_education" TEXT,
    "ofsted_legacy_behaviour_and_attitudes" TEXT,
    "ofsted_legacy_personal_development" TEXT,
    "ofsted_legacy_leadership_and_management" TEXT,
    "ofsted_legacy_early_years" TEXT,
    "ofsted_legacy_sixth_form" TEXT,
    "ofsted_ccr_met" BOOLEAN,
    "ofsted_vcr_met" BOOLEAN,
    "ofsted_oosc_met" BOOLEAN,
    "registered_places" INTEGER,
    "staff_graduate_percentage" DECIMAL(5,2),
    "staff_turnover_percentage" DECIMAL(5,2),
    "has_garden" BOOLEAN,
    "has_kitchen" BOOLEAN,
    "institution_type" TEXT,
    "lad23cd" TEXT,
    "metadata" JSONB NOT NULL DEFAULT '{}',

    CONSTRAINT "providers_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "published"."care_types" (
    "id" BIGINT GENERATED ALWAYS AS IDENTITY,
    "provider_id" BIGINT NOT NULL,
    "care_type" TEXT NOT NULL,
    "opening_hour_open" TIME,
    "opening_hour_close" TIME,
    "operating_weeks_per_year" INTEGER,
    "session_hours_morning" DECIMAL(4,2),
    "session_hours_afternoon" DECIMAL(4,2),
    "session_hours_full_day" DECIMAL(4,2),
    "eligible_min_months" INTEGER,
    "eligible_min_years" INTEGER,
    "eligible_max_years" INTEGER,
    "eligible_attendees_only" BOOLEAN NOT NULL DEFAULT false,
    "eligible_institutions" TEXT[],
    "eligible_other" TEXT[],
    "funded_hours_accepted" BOOLEAN,
    "min_commitment_amount" INTEGER,
    "min_commitment_unit" TEXT,
    "min_commitment_duration" TEXT,
    "no_minimum_commitment" BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT "care_types_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "published"."fee_rates" (
    "id" BIGINT GENERATED ALWAYS AS IDENTITY,
    "care_type_id" BIGINT NOT NULL,
    "age_band" TEXT NOT NULL,
    "morning_session" DECIMAL(8,2),
    "afternoon_session" DECIMAL(8,2),
    "full_day" DECIMAL(8,2),
    "per_session" DECIMAL(8,2),
    "per_hour" DECIMAL(8,2),
    "per_day" DECIMAL(8,2),

    CONSTRAINT "fee_rates_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "published"."additional_charges" (
    "id" BIGINT GENERATED ALWAYS AS IDENTITY,
    "care_type_id" BIGINT NOT NULL,
    "item" TEXT NOT NULL,
    "cost" DECIMAL(8,2) NOT NULL,
    "unit" TEXT NOT NULL,
    "description" TEXT NOT NULL,

    CONSTRAINT "additional_charges_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "published"."waiting_list_entries" (
    "id" BIGINT GENERATED ALWAYS AS IDENTITY,
    "care_type_id" BIGINT NOT NULL,
    "age_band" TEXT NOT NULL,
    "weeks" INTEGER,
    "months" INTEGER,

    CONSTRAINT "waiting_list_entries_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "published"."care_type_notes" (
    "id" BIGINT GENERATED ALWAYS AS IDENTITY,
    "care_type_id" BIGINT NOT NULL,
    "note_type" TEXT NOT NULL,
    "description" TEXT NOT NULL,

    CONSTRAINT "care_type_notes_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "published"."bounding_boxes" (
    "geo_type" TEXT NOT NULL,
    "geo_code" TEXT NOT NULL,
    "geo_name" TEXT,
    "bbox_north" DOUBLE PRECISION NOT NULL,
    "bbox_south" DOUBLE PRECISION NOT NULL,
    "bbox_east" DOUBLE PRECISION NOT NULL,
    "bbox_west" DOUBLE PRECISION NOT NULL,

    CONSTRAINT "bounding_boxes_pkey" PRIMARY KEY ("geo_type","geo_code")
);

-- CreateIndex
CREATE INDEX "idx_providers_postcode" ON "published"."providers"("postcode");

-- CreateIndex
CREATE INDEX "idx_providers_lad23cd" ON "published"."providers"("lad23cd");

-- CreateIndex
CREATE INDEX "idx_care_types_provider_id" ON "published"."care_types"("provider_id");

-- CreateIndex
CREATE INDEX "idx_care_types_care_type" ON "published"."care_types"("care_type");

-- CreateIndex
CREATE INDEX "idx_fee_rates_care_type_id" ON "published"."fee_rates"("care_type_id");

-- CreateIndex
CREATE INDEX "idx_additional_charges_care_type_id" ON "published"."additional_charges"("care_type_id");

-- CreateIndex
CREATE INDEX "idx_waiting_list_entries_care_type_id" ON "published"."waiting_list_entries"("care_type_id");

-- CreateIndex
CREATE INDEX "idx_care_type_notes_care_type_id" ON "published"."care_type_notes"("care_type_id");

-- AddForeignKey
ALTER TABLE "published"."care_types" ADD CONSTRAINT "care_types_provider_id_fkey" FOREIGN KEY ("provider_id") REFERENCES "published"."providers"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "published"."fee_rates" ADD CONSTRAINT "fee_rates_care_type_id_fkey" FOREIGN KEY ("care_type_id") REFERENCES "published"."care_types"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "published"."additional_charges" ADD CONSTRAINT "additional_charges_care_type_id_fkey" FOREIGN KEY ("care_type_id") REFERENCES "published"."care_types"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "published"."waiting_list_entries" ADD CONSTRAINT "waiting_list_entries_care_type_id_fkey" FOREIGN KEY ("care_type_id") REFERENCES "published"."care_types"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "published"."care_type_notes" ADD CONSTRAINT "care_type_notes_care_type_id_fkey" FOREIGN KEY ("care_type_id") REFERENCES "published"."care_types"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- CHECK constraints
ALTER TABLE "published"."providers"
  ADD CONSTRAINT "providers_ofsted_rating_check"
  CHECK ("ofsted_legacy_rating" IN (
    'Outstanding', 'Good', 'Requires Improvement',
    'Needs Attention', 'Inadequate', 'Urgent Improvement'
  ));

ALTER TABLE "published"."care_types"
  ADD CONSTRAINT "care_types_care_type_check"
  CHECK ("care_type" IN (
    'private_nursery', 'school_based_nursery', 'childminder',
    'breakfast_club', 'free_breakfast_club', 'after_school_club', 'holiday_club'
  ));

ALTER TABLE "published"."care_types"
  ADD CONSTRAINT "care_types_min_commitment_unit_check"
  CHECK ("min_commitment_unit" IN ('full_days', 'sessions', 'hours'));

ALTER TABLE "published"."care_types"
  ADD CONSTRAINT "care_types_min_commitment_duration_check"
  CHECK ("min_commitment_duration" IN ('half_term', 'term', 'year'));

ALTER TABLE "published"."fee_rates"
  ADD CONSTRAINT "fee_rates_age_band_check"
  CHECK ("age_band" IN ('all', 'under2', 'age2', 'age3to4', 'age2plus', 'age5plus'));

ALTER TABLE "published"."fee_rates"
  ADD CONSTRAINT "chk_fee_rates_has_value"
  CHECK (
    "morning_session" IS NOT NULL OR "afternoon_session" IS NOT NULL OR "full_day" IS NOT NULL
    OR "per_session" IS NOT NULL OR "per_hour" IS NOT NULL OR "per_day" IS NOT NULL
  );

ALTER TABLE "published"."additional_charges"
  ADD CONSTRAINT "additional_charges_unit_check"
  CHECK ("unit" IN ('per day', 'per week', 'per session'));

ALTER TABLE "published"."waiting_list_entries"
  ADD CONSTRAINT "waiting_list_entries_age_band_check"
  CHECK ("age_band" IN ('all', 'under2', 'age2', 'age3to4', 'age2plus', 'age5plus'));

ALTER TABLE "published"."waiting_list_entries"
  ADD CONSTRAINT "chk_waiting_list_one_unit"
  CHECK (
    ("weeks" IS NOT NULL AND "months" IS NULL) OR ("weeks" IS NULL AND "months" IS NOT NULL)
  );

ALTER TABLE "published"."care_type_notes"
  ADD CONSTRAINT "care_type_notes_note_type_check"
  CHECK ("note_type" IN ('tick', 'warn'));
