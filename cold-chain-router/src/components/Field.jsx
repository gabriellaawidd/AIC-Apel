// Primitif form yang dipakai bareng-bareng di baris input.
// Tinggi 46px menjaga target sentuh tetap di atas minimum HIG (44pt).

export const FIELD_SHELL =
  'flex h-[46px] w-full items-center gap-2.5 rounded-field border border-separator bg-surface px-3.5 ' +
  'transition-colors duration-150 focus-within:border-ios-blue focus-within:ring-4 focus-within:ring-ios-blue/20';

export const FIELD_INPUT =
  'min-w-0 flex-1 border-0 bg-transparent p-0 text-callout text-label placeholder:text-label-tertiary focus:outline-none focus:ring-0';

// Label di atas kontrol — footnote sekunder, sesuai pola form iOS.
export function Field({ label, htmlFor, children, hint }) {
  return (
    <div className="min-w-0">
      <label htmlFor={htmlFor} className="mb-2 block text-footnote text-label-secondary">
        {label}
      </label>
      {children}
      {hint && <p className="mt-1.5 text-caption text-label-tertiary">{hint}</p>}
    </div>
  );
}

// Ikon pemimpin di dalam field — selalu tersier supaya tidak bersaing dengan nilai.
export function FieldIcon({ as: Icon }) {
  return (
    <span className="flex-shrink-0 text-label-tertiary">
      <Icon size={18} />
    </span>
  );
}
