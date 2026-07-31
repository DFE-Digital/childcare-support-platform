/**
 * Validate all published providers against the Zod schema spec.
 *
 * Reads from published.providers via Prisma, validates each provider
 * (with relations) against the generated Zod schemas, and writes
 * results back into metadata.validation.
 *
 * Outputs a JSON summary report to stdout for Dagster to capture.
 */

import { PrismaClient, Prisma } from "@prisma/client";
import { z } from "zod";
import {
  ProviderSchema,
  CareTypeSchema,
  FeeRateSchema,
  AdditionalChargeSchema,
  WaitingListEntrySchema,
  CareTypeNoteSchema,
} from "./generated/index.js";

// Build a validation schema that matches the Prisma include shape
// (no circular provider back-reference on care types)
const CareTypeValidationSchema = CareTypeSchema.extend({
  feeRates: FeeRateSchema.omit({ careType: true } as never).array(),
  additionalCharges: AdditionalChargeSchema.omit({
    careType: true,
  } as never).array(),
  waitingListEntries: WaitingListEntrySchema.omit({
    careType: true,
  } as never).array(),
  careTypeNotes: CareTypeNoteSchema.omit({ careType: true } as never).array(),
}).refine(
  (ct) => {
    const hasMin = ct.eligibleMinMonths != null || ct.eligibleMinYears != null;
    const hasMax = ct.eligibleMaxYears != null;
    return hasMin === hasMax;
  },
  {
    message: "eligibleAgeRange must have both min and max, or neither",
    path: ["eligibleMaxYears"],
  },
);

const ProviderValidationSchema = ProviderSchema.extend({
  careTypes: CareTypeValidationSchema.array(),
});

const BATCH_SIZE = 1000;

interface ErrorEntry {
  path: string;
  code: string;
  message: string;
}

interface ValidationResult {
  id: bigint;
  pass: boolean;
  errors?: ErrorEntry[];
}

async function main() {
  const prisma = new PrismaClient();

  try {
    const total = await prisma.provider.count();
    if (total === 0) {
      const report = {
        timestamp: new Date().toISOString(),
        total: 0,
        valid: 0,
        invalid: 0,
        error_summary: {},
        sample_failures: [],
      };
      console.log(JSON.stringify(report));
      return;
    }

    let valid = 0;
    let invalid = 0;
    const errorSummary: Record<string, Record<string, number>> = {};
    const sampleFailures: { id: string; errors: string[] }[] = [];

    let skip = 0;
    while (skip < total) {
      const providers = await prisma.provider.findMany({
        skip,
        take: BATCH_SIZE,
        include: {
          careTypes: {
            include: {
              feeRates: true,
              additionalCharges: true,
              waitingListEntries: true,
              careTypeNotes: true,
            },
          },
        },
        orderBy: { id: "asc" },
      });

      if (providers.length === 0) break;

      const results: ValidationResult[] = [];

      for (const provider of providers) {
        const parsed = ProviderValidationSchema.safeParse(provider);

        if (parsed.success) {
          results.push({ id: provider.id, pass: true });
          valid++;
        } else {
          const errors: ErrorEntry[] = parsed.error.issues.map((issue) => ({
            path: issue.path.join("."),
            code: issue.code,
            message: issue.message,
          }));

          results.push({ id: provider.id, pass: false, errors });
          invalid++;

          // Aggregate error summary
          for (const err of errors) {
            const pathKey = err.path || "(root)";
            if (!errorSummary[pathKey]) errorSummary[pathKey] = {};
            errorSummary[pathKey][err.code] =
              (errorSummary[pathKey][err.code] || 0) + 1;
          }

          // Collect sample failures (up to 10)
          if (sampleFailures.length < 10) {
            sampleFailures.push({
              id: provider.id.toString(),
              errors: errors.map((e) => `${e.path}: ${e.message}`),
            });
          }
        }
      }

      // Batch-update metadata.validation for this batch
      const now = new Date().toISOString();
      const cases: string[] = [];
      const ids: bigint[] = [];

      for (const result of results) {
        const validation: Record<string, unknown> = {
          pass: result.pass,
          validated_at: now,
        };
        if (result.errors) {
          validation.errors = result.errors;
        }

        const jsonStr = JSON.stringify({ validation });
        cases.push(
          `WHEN id = ${result.id} THEN metadata || '${jsonStr.replace(/'/g, "''")}'::jsonb`,
        );
        ids.push(result.id);
      }

      if (ids.length > 0) {
        const idList = ids.join(",");
        await prisma.$executeRawUnsafe(
          `UPDATE published.providers SET metadata = CASE ${cases.join(" ")} END WHERE id IN (${idList})`,
        );
      }

      process.stderr.write(
        `Validated ${Math.min(skip + BATCH_SIZE, total)}/${total}\n`,
      );
      skip += BATCH_SIZE;
    }

    const report = {
      timestamp: new Date().toISOString(),
      total,
      valid,
      invalid,
      error_summary: errorSummary,
      sample_failures: sampleFailures,
    };

    console.log(JSON.stringify(report));
  } finally {
    await prisma.$disconnect();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
