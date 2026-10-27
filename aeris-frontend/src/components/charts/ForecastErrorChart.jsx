import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import ChartTooltip from './ChartTooltip'
import { formatAxisTick } from '../../utils/time'
import { formatInt } from '../../utils/formatters'

export default function ForecastErrorChart({ data }) {
  return (
    <div className="chart" role="img" aria-label="Line chart of forecast error in megawatts over time">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 8, left: 8 }}>
          <CartesianGrid stroke="var(--border)" strokeOpacity={0.5} vertical={false} />
          <XAxis dataKey="ts" type="number" scale="time" domain={['dataMin', 'dataMax']} tickFormatter={formatAxisTick} stroke="var(--text-muted)" tick={{ fontSize: 12 }} minTickGap={48} />
          <YAxis tickFormatter={formatInt} stroke="var(--text-muted)" tick={{ fontSize: 12 }} width={64} label={{ value: 'Error (MW)', angle: -90, position: 'insideLeft', fill: 'var(--text-muted)', fontSize: 12 }} />
          <Tooltip content={<ChartTooltip />} />
          <ReferenceLine y={0} stroke="var(--text)" strokeDasharray="4 4" label={{ value: 'Zero error', fill: 'var(--text-muted)', fontSize: 11, position: 'insideTopRight' }} />
          <Line name="Error" dataKey="error" stroke="var(--warn)" strokeWidth={1.4} dot={false} isAnimationActive={false} connectNulls={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
