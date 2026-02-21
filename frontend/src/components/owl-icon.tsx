/**
 * Blue owl icon — Eva brand mascot.
 * Minimal version for sidebar/nav. Use size="lg" for larger contexts (cards, pages).
 */
export function OwlIcon({ className = "h-5 w-5", size = "sm" }: { className?: string; size?: "sm" | "lg" }) {
  if (size === "lg") {
    return (
      <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
        <ellipse cx="32" cy="38" rx="18" ry="20" fill="#2563EB" opacity="0.15" />
        <circle cx="32" cy="24" r="16" fill="#2563EB" />
        <path d="M18 12 L22 20 L16 18Z" fill="#1D4ED8" />
        <path d="M46 12 L42 20 L48 18Z" fill="#1D4ED8" />
        <circle cx="25" cy="24" r="6" fill="white" />
        <circle cx="39" cy="24" r="6" fill="white" />
        <circle cx="26" cy="24" r="3" fill="#1E293B" />
        <circle cx="40" cy="24" r="3" fill="#1E293B" />
        <circle cx="27" cy="23" r="1" fill="white" />
        <circle cx="41" cy="23" r="1" fill="white" />
        <path d="M29 29 L32 33 L35 29Z" fill="#F59E0B" />
        <ellipse cx="32" cy="46" rx="10" ry="10" fill="#3B82F6" opacity="0.3" />
        <path d="M27 42 Q32 48 37 42" stroke="#2563EB" strokeWidth="1.5" fill="none" opacity="0.4" />
        <path d="M28 46 Q32 51 36 46" stroke="#2563EB" strokeWidth="1.5" fill="none" opacity="0.3" />
        <path d="M26 55 L24 58 M26 55 L26 58 M26 55 L28 58" stroke="#F59E0B" strokeWidth="1.5" strokeLinecap="round" />
        <path d="M38 55 L36 58 M38 55 L38 58 M38 55 L40 58" stroke="#F59E0B" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }

  // Minimal: just the head with eyes and ear tufts — reads well at 20px
  return (
    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      {/* Head */}
      <circle cx="12" cy="13" r="9" fill="#2563EB" />
      {/* Ear tufts */}
      <path d="M4.5 6 L7 10 L3.5 9Z" fill="#1D4ED8" />
      <path d="M19.5 6 L17 10 L20.5 9Z" fill="#1D4ED8" />
      {/* Eyes */}
      <circle cx="9" cy="13" r="3" fill="white" />
      <circle cx="15" cy="13" r="3" fill="white" />
      <circle cx="9.5" cy="13" r="1.5" fill="#1E293B" />
      <circle cx="15.5" cy="13" r="1.5" fill="#1E293B" />
      {/* Beak */}
      <path d="M10.5 16.5 L12 18.5 L13.5 16.5Z" fill="#F59E0B" />
    </svg>
  );
}
