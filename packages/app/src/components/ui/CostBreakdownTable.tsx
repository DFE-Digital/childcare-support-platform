interface CostRow {
  item: string;
  weekly?: string;
  monthly?: string;
  annual: string;
  highlight?: boolean;
}

interface CostBreakdownTableProps {
  rows: CostRow[];
  title?: string;
}

export function CostBreakdownTable({ rows, title }: CostBreakdownTableProps) {
  return (
    <div className="overflow-x-auto">
      {title && <h3 className="font-bold text-lg mb-3">{title}</h3>}
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-neutral-300 text-neutral-700">
            <th scope="col" className="text-left px-4 py-3 text-sm font-bold">
              Item
            </th>
            <th scope="col" className="text-right px-4 py-3 text-sm font-bold">
              Weekly
            </th>
            <th scope="col" className="text-right px-4 py-3 text-sm font-bold">
              Monthly
            </th>
            <th scope="col" className="text-right px-4 py-3 text-sm font-bold">
              Annual
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className={`border-b border-zinc-200 ${row.highlight ? "bg-neutral-200 font-bold" : "bg-white"}`}
            >
              <td className="px-4 py-3 text-sm">{row.item}</td>
              <td className="px-4 py-3 text-sm text-right">
                {row.weekly || "-"}
              </td>
              <td className="px-4 py-3 text-sm text-right">
                {row.monthly || "-"}
              </td>
              <td className="px-4 py-3 text-sm text-right">{row.annual}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
