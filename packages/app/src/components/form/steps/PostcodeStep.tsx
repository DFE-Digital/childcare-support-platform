import { useState } from "react";
import type { FormLocalStorageData } from "@/types/formData";
import { FormStep } from "@/components/ui/FormStep";
import { PostcodeInput } from "@/components/ui/PostcodeInput";
import { Explainer } from "@/components/ui/Explainer";
import { Button } from "@/components/ui/Button";
import { usePostcodeLookup } from "@/hooks/usePostcodeLookup";
import { useFamily } from "@/hooks/useFamily";
import {
  normalisePostcode,
  isPostcodeFormatValid,
  isCrownDependency,
} from "@/lib/postcode";
import { scrollToFirstError } from "@/lib/scrollToFirstError";

interface Props {
  formData: FormLocalStorageData;
  updateFormData: (patch: Partial<FormLocalStorageData>) => void;
  onContinue: () => void;
  onBack: () => void;
  showSchemesLink?: boolean;
}

export function PostcodeStep({
  formData,
  updateFormData,
  onContinue,
  showSchemesLink,
}: Props) {
  const { isValid, ensureInward, getLaCodes } = usePostcodeLookup();
  const { devolvedNationLinks } = useFamily();
  const [error, setError] = useState(false);
  const [notEngland, setNotEngland] = useState(false);

  const handleContinue = async () => {
    const normalised = normalisePostcode(formData.location.postcode);
    if (!isPostcodeFormatValid(normalised, true)) {
      setError(true);
      scrollToFirstError();
      return;
    }
    if (isCrownDependency(normalised)) {
      setNotEngland(true);
      return;
    }
    const [outward] = normalised.split(" ");
    await ensureInward(outward);
    if (!isValid(normalised)) {
      setError(true);
      scrollToFirstError();
      return;
    }
    const [, inward] = normalised.split(" ");
    const ladCodes = getLaCodes(outward, inward);
    updateFormData({ location: { postcode: normalised, ladCodes } });
    if (!ladCodes.some((c) => c.startsWith("E"))) {
      setNotEngland(true);
      return;
    }
    onContinue();
  };

  return (
    <>
      <FormStep
        title="Where do you live?"
        onContinue={handleContinue}
        showBack={false}
        secondaryAction={
          showSchemesLink ? (
            <Button to="/support/schemes#main-content" arrow>
              View all schemes
            </Button>
          ) : undefined
        }
        footer={
          <>
            <Explainer
              label="Why do you need my postcode?"
              modalTitle="Why we ask for your postcode"
            >
              <p>
                Your postcode helps us work out which childcare support you may
                be eligible for and show you local providers and estimated
                costs. If you are interested in childcare in another area, such
                as your place of work, you can enter that postcode instead.
              </p>
              <p className="font-bold">Your privacy</p>
              <p>
                Your postcode is only used in your browser to look up local
                information. It is never sent to a server, stored in a database,
                or linked to you personally. We collect anonymous usage
                statistics to help improve this service. No personal details are
                included.
              </p>
              <p>We use your postcode to:</p>
              <ul className="list-disc pl-5 space-y-1">
                <li>Find childcare providers near you</li>
                <li>Show average childcare costs for your area</li>
                <li>
                  Determine your country within the UK, which affects which
                  schemes are available.
                </li>
              </ul>
            </Explainer>
            <Explainer label="What if I don't live in England?">
              <p>
                This tool covers childcare support schemes available in England.
                If you live in Scotland, Wales, or Northern Ireland, you can
                find information about childcare support in your nation here:
              </p>
              <ul className="space-y-2">
                {devolvedNationLinks.map((link) => (
                  <li key={link.nation}>
                    <a
                      href={link.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-700 underline hover:no-underline inline-flex items-center gap-1"
                    >
                      {link.label}
                      <i
                        className="bi bi-box-arrow-up-right text-xs"
                        aria-hidden="true"
                      />
                      <span className="sr-only">(opens in new tab)</span>
                    </a>
                  </li>
                ))}
              </ul>
            </Explainer>
          </>
        }
      >
        <p className="text-base text-zinc-600">
          Enter your postcode to find more about what you may be eligible for.
        </p>
        <PostcodeInput
          label="Postcode"
          value={formData.location.postcode}
          error={error}
          onChange={(value) => {
            setError(false);
            setNotEngland(false);
            updateFormData({
              location: {
                postcode: value,
                ladCodes: formData.location.ladCodes,
              },
            });
          }}
        />
        {error && (
          <p
            role="alert"
            data-error-field
            className="text-base text-white bg-red-600 rounded-md px-4 py-2 inline-block"
          >
            Enter a valid UK postcode to continue
          </p>
        )}
        {notEngland && (
          <div
            role="status"
            className="flex items-start gap-2 border-2 border-blue-600 bg-blue-50 text-blue-800 rounded-md px-4 py-3 text-base"
          >
            <i
              className="bi bi-info-circle shrink-0 mt-0.5"
              aria-hidden="true"
            />
            <span>Unfortunately this tool only covers England.</span>
          </div>
        )}
      </FormStep>
    </>
  );
}
