interface BetaBannerProps {
  children?: React.ReactNode;
}

const defaultContent = (
  <>
    This is a new service. Help us improve it by{" "}
    <a
      href="https://dferesearch.fra1.qualtrics.com/jfe/form/SV_73U1lSDggAf4MPY"
      target="_blank"
      rel="noopener noreferrer"
      className="underline hover:no-underline"
    >
      giving feedback
    </a>
  </>
);

export function BetaBanner({ children }: BetaBannerProps) {
  return (
    <p className="text-sm bg-blue-50 border border-blue-200 text-blue-900 rounded-md px-4 py-3 text-center">
      <span className="inline-block bg-blue-700 text-white text-xs font-bold uppercase px-2 py-0.5 rounded mr-2 align-middle">
        Beta
      </span>
      {children ?? defaultContent}
    </p>
  );
}
