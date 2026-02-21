/**
 * EVA ERP brand mark — 5 tilted gradient bars.
 * Matches the canonical icon.svg (gradient: #2563EB → #60A5FA).
 */
export function EvaMark({ className = "h-8 w-auto" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 52 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="EVA ERP mark"
    >
      <defs>
        <linearGradient id="eva-mark-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#2563EB" />
          <stop offset="100%" stopColor="#60A5FA" />
        </linearGradient>
      </defs>
      <g transform="skewX(-15) translate(10, 0)">
        <rect x="0" y="12" width="6" height="16" rx="3" fill="url(#eva-mark-grad)" opacity="0.9" />
        <rect x="10" y="6" width="6" height="28" rx="3" fill="url(#eva-mark-grad)" />
        <rect x="20" y="0" width="6" height="40" rx="3" fill="url(#eva-mark-grad)" />
        <rect x="30" y="6" width="6" height="28" rx="3" fill="url(#eva-mark-grad)" />
        <rect x="40" y="12" width="6" height="16" rx="3" fill="url(#eva-mark-grad)" opacity="0.9" />
      </g>
    </svg>
  );
}
