export default function DateRangeFilter({ period, value, onChange }) {
  const set = (patch) => onChange({ ...value, ...patch })
  return (
    <div className="filter">
      <label>From
        <input type="date" value={value.from} min={period?.start} max={value.to || period?.end} disabled={!period} onChange={(e) => set({ from: e.target.value })} />
      </label>
      <label>To
        <input type="date" value={value.to} min={value.from || period?.start} max={period?.end} disabled={!period} onChange={(e) => set({ to: e.target.value })} />
      </label>
      <button type="button" className="btn" disabled={!value.from && !value.to} onClick={() => onChange({ from: '', to: '' })}>Reset</button>
    </div>
  )
}
