import { useEffect, useRef, useState } from 'react';

// Popover penjelasan ala iOS: dipicu lewat tombol "?" bundar.
// Target sentuhnya diperluas dengan padding transparan supaya tetap nyaman
// walau ikonnya kecil (HIG: minimum 44pt).
export default function InfoTip({ label, children, align = 'center' }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const pos =
    align === 'left' ? 'left-0' : align === 'right' ? 'right-0' : 'left-1/2 -translate-x-1/2';

  return (
    <span ref={wrapRef} className="relative inline-flex items-center">
      <button
        type="button"
        aria-label={label ? `Penjelasan ${label}` : 'Penjelasan'}
        aria-expanded={open}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="focus-ring -m-2 inline-flex h-[34px] w-[34px] cursor-help items-center justify-center rounded-full"
      >
        <span className="inline-flex h-[16px] w-[16px] items-center justify-center rounded-full bg-fill-tertiary text-[10px] font-semibold leading-none text-label-secondary transition-colors hover:bg-ios-blue hover:text-white">
          ?
        </span>
      </button>

      {open && (
        <span
          role="tooltip"
          className={`absolute bottom-[calc(100%+10px)] z-[60] w-[230px] animate-fadeIn rounded-[14px] bg-[rgba(28,28,30,0.92)] px-3.5 py-2.5 text-left text-caption font-normal normal-case leading-[1.45] tracking-normal text-white/90 shadow-popover backdrop-blur-xl ${pos}`}
        >
          {label && <span className="mb-1 block text-footnote font-semibold text-white">{label}</span>}
          {children}
        </span>
      )}
    </span>
  );
}
