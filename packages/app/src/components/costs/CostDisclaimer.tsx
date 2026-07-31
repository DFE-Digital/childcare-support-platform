import { Button } from "@/components/ui/Button";

export function CostDisclaimer({ onAccept }: { onAccept: () => void }) {
  return (
    <div className="bg-white rounded-xl border border-zinc-200 p-6 md:p-8">
      <div className="max-w-prose mx-auto">
        <h2 className="text-2xl font-bold mb-4">Before you continue</h2>

        <p className="text-base text-zinc-700 mb-4">
          We have estimated your childcare costs using the answers you provided.
          Please be aware that your actual costs may be higher or lower. Here is
          why:
        </p>

        <ul className="list-disc pl-5 space-y-3 text-base text-zinc-700 mb-6">
          <li>
            <strong>We use average costs for your area.</strong> Real provider
            fees may differ from these averages.
          </li>
          <li>
            <strong>Funded hours are calculated annually.</strong> We deduct the
            funded childcare hours you may be entitled to across the year, but
            individual providers may offer entitlement places at different
            times, days, or weeks. You should discuss with your provider.
          </li>
          <li>
            <strong>Monthly costs will vary.</strong> We show a simple monthly
            average across the year. Your actual bills may differ depending on
            how you use childcare and how your provider bills you.
          </li>
          <li>
            <strong>There may be additional charges.</strong> Providers can
            offer additional extras such as meals, nappies, suncream, additional
            classes, or extra hours beyond your entitlements. These are not
            included in this estimate and you should discuss with your provider.
          </li>
          <li>
            <strong>Universal Credit</strong> can cover up to 85% of eligible
            childcare costs (subject to monthly limits), but the amount received
            in your Universal Credit award will depend on your individual
            circumstances.
          </li>
        </ul>

        <p className="text-base text-zinc-700 mb-8">
          Please speak to your provider if you have any questions about their
          costs or how their entitlement places are offered.
        </p>

        <div className="flex flex-col gap-3 sm:flex-row-reverse sm:justify-center sm:gap-4">
          <Button variant="dark" onClick={onAccept} arrow>
            Show my estimate
          </Button>
          <Button to="/costs#main-content">Go back</Button>
        </div>
      </div>
    </div>
  );
}
