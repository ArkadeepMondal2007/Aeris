import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import ChartTooltip from './ChartTooltip'
import { formatAxisTick } from '../../utils/time'
import { formatInt } from '../../utils/formatters'

export default function ForecastActualChart({ data }) {
  return (
    <div className="chart" role="img" aria-label="Line chart of forecast and actual wind generation in megawatts">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 8, left: 8 }}>
          <CartesianGrid stroke="var(--border)" strokeOpacity={0.5} vertical={false} />
          <XAxis dataKey="ts" type="number" scale="time" domain={['dataMin', 'dataMax']} tickFormatter={formatAxisTick} stroke="var(--text-muted)" tick={{ fontSize: 12 }} minTickGap={48} />
          <YAxis tickFormatter={formatInt} stroke="var(--text-muted)" tick={{ fontSize: 12 }} width={64} label={{ value: 'Generation (MW)', angle: -90, position: 'insideLeft', fill: 'var(--text-muted)', fontSize: 12 }} />
          <Tooltip content={<ChartTooltip />} />
          <Legend verticalAlign="top" height={28} />
          <Line name="Actual" dataKey="actual" stroke="var(--actual)" strokeWidth={1.6} dot={false} isAnimationActive={false} connectNulls={false} />
          <Line name="Forecast" dataKey="forecast" stroke="var(--forecast)" strokeWidth={1.6} dot={false} isAnimationActive={false} connectNulls={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
