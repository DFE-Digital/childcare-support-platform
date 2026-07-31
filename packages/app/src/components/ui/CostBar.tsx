interface CostBarProps {
  total: number;
  governmentSupport: number;
  familyPays: number;
}

function formatCurrency(n: number): string {
  return (
    "£" +
    n.toLocaleString("en-GB", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    })
  );
}

export function CostBar({
  total,
  governmentSupport,
  familyPays,
}: CostBarProps) {
  const govPct = total > 0 ? (governmentSupport / total) * 100 : 0;
  const famPct = total > 0 ? (familyPays / total) * 100 : 0;

  return (
    <div className="space-y-3">
      <div
        className="h-10 rounded-full overflow-hidden flex bg-zinc-200"
        role="img"
        aria-label={`Government support: ${formatCurrency(governmentSupport)} (${govPct.toFixed(0)}%). Family pays: ${formatCurrency(familyPays)} (${famPct.toFixed(0)}%).`}
      >
        {govPct > 0 && (
          <div
            className="bg-green-600 h-full flex items-center justify-center text-white text-xs font-bold px-2 min-w-[40px]"
            style={{ width: `${govPct}%` }}
          >
            {govPct > 15 ? formatCurrency(governmentSupport) : ""}
          </div>
        )}
        {famPct > 0 && (
          <div
            className="bg-neutral-700 h-full flex items-center justify-center text-white text-xs font-bold px-2 min-w-[40px]"
            style={{ width: `${famPct}%` }}
          >
            {famPct > 15 ? formatCurrency(familyPays) : ""}
          </div>
        )}
      </div>

      <div className="flex items-center gap-6 text-xs" aria-hidden="true">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-sm bg-green-600" />
          <span>Government support ({govPct.toFixed(0)}%)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-sm bg-neutral-700" />
          <span>Family pays ({famPct.toFixed(0)}%)</span>
        </div>
      </div>
    </div>
  );
}
