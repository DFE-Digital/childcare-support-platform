import type { Scheme } from "@/types/scheme";

interface IneligibleSchemeCardProps {
  scheme: Scheme;
  reason: string;
}

export function IneligibleSchemeCard({
  scheme,
  reason,
}: IneligibleSchemeCardProps) {
  return (
    <div className="bg-white rounded-xl border border-zinc-200 p-6 pl-8 relative overflow-hidden">
      <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-zinc-400" />
      <div className="flex-1">
        <div className="flex items-center gap-2 flex-wrap mb-2">
          <span className="text-xs font-bold uppercase tracking-wide px-2 py-0.5 rounded text-center text-zinc-600 bg-zinc-100">
            Ending
          </span>
        </div>
        <h3 className="font-bold text-lg mb-1">{scheme.name}</h3>
        <p className="text-sm text-zinc-600">{reason}</p>
      </div>
    </div>
  );
}
