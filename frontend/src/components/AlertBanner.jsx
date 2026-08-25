export default function AlertBanner({ alert, deadlineFeasible }) {
  if (!alert) return null;

  return (
    <div className="mb-6 flex items-start gap-3 rounded-2xl bg-[#fff4f3] px-5 py-4">
      <span className="mt-px flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-[#ff3b30] text-[12px] font-bold leading-none text-white">
        !
      </span>
      <div>
        <p className="text-[13.5px] leading-[1.55] text-[#7f1d1d]">{alert}</p>
        {!deadlineFeasible && (
          <p className="mt-1 text-[12px] text-[#b45252]">
            Tidak ada rute yang memenuhi batas waktu pada skenario perjalanan terburuk.
          </p>
        )}
      </div>
    </div>
  );
}
