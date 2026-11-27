/**
 * Small, dependency-free SVG charts for single-series data.
 *
 * Mark specs: bars at most 24px thick, a 4px rounded data end and a square
 * baseline, hairline solid gridlines, text in text colours (never the mark
 * colour), a hover/focus tooltip on every mark, and a table view so no value
 * depends on reading the chart.
 */
import { useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { niceTicks } from '@/components/charts/scale'
import { cn } from '@/utils/cn'

const INK = '#27272a' // zinc-800, the single series colour
const INK_ACTIVE = '#09090b' // zinc-950
const GRID = '#e4e4e7' // zinc-200
const AXIS_TEXT = '#71717a' // zinc-500
const BAR_MAX = 24
const RADIUS = 4

export interface Datum {
  key: string
  label: string
  value: number
  /** Tooltip text; defaults to the formatted value. */
  detail?: string
}

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(0)
  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return
    setWidth(element.clientWidth)
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(([entry]) => setWidth(entry!.contentRect.width))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  return [ref, width] as const
}

/** Column path: square at the baseline, rounded at the top (the data end). */
function columnPath(x: number, y: number, w: number, h: number) {
  const r = Math.min(RADIUS, h, w / 2)
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`
}

/** Bar path: square at the left baseline, rounded at the right (the data end). */
function barPath(x: number, y: number, w: number, h: number) {
  const r = Math.min(RADIUS, w, h / 2)
  return `M${x},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h - r}Q${x + w},${y + h} ${x + w - r},${y + h}H${x}Z`
}

function Tooltip({ x, y, below, children }: { x: number; y: number; below?: boolean; children: ReactNode }) {
  return (
    <div
      role="presentation"
      className={cn(
        'pointer-events-none absolute z-10 -translate-x-1/2 rounded-md border border-zinc-200 bg-white px-2.5 py-1.5 text-xs whitespace-nowrap text-zinc-700 shadow-sm',
        !below && '-translate-y-full',
      )}
      style={{ left: x, top: below ? y + 6 : y - 8 }}
    >
      {children}
    </div>
  )
}

interface ChartProps {
  data: Datum[]
  /** Accessible summary of what the chart shows. */
  title: string
  format?: (value: number) => string
  /** Fixed axis maximum (e.g. 100 for percentages). */
  max?: number
  className?: string
}

const defaultFormat = (value: number) => String(value)

/** Vertical columns, one per category, e.g. a score distribution. */
export function ColumnChart({ data, title, format = defaultFormat, max, height = 220, className }: ChartProps & { height?: number }) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [active, setActive] = useState<number | null>(null)
  const ticks = niceTicks(max ?? Math.max(...data.map((d) => d.value), 0))
  const top = ticks[ticks.length - 1]!
  const margin = { top: 12, right: 8, bottom: 28, left: 32 }
  const plotW = Math.max(0, width - margin.left - margin.right)
  const plotH = height - margin.top - margin.bottom
  const slot = data.length ? plotW / data.length : 0
  const barW = Math.min(BAR_MAX, Math.max(2, slot - 8))
  const labelEvery = slot >= 44 ? 1 : slot >= 22 ? 2 : 5
  const y = (v: number) => margin.top + plotH - (v / top) * plotH

  return (
    <div ref={ref} className={cn('relative', className)}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={title} className="block overflow-visible">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={margin.left} x2={width - margin.right} y1={y(t)} y2={y(t)} stroke={GRID} strokeWidth={1} shapeRendering="crispEdges" />
              <text x={margin.left - 8} y={y(t)} dy="0.32em" textAnchor="end" fontSize={11} fill={AXIS_TEXT} className="tabular-nums">
                {format(t)}
              </text>
            </g>
          ))}
          {data.map((d, i) => {
            const cx = margin.left + slot * i + slot / 2
            const h = (d.value / top) * plotH
            return (
              <g
                key={d.key}
                tabIndex={0}
                role="img"
                aria-label={`${d.label}: ${d.detail ?? format(d.value)}`}
                onMouseEnter={() => setActive(i)}
                onMouseLeave={() => setActive(null)}
                onFocus={() => setActive(i)}
                onBlur={() => setActive(null)}
                className="outline-none"
              >
                {/* Hit target: the whole slot, larger than the mark. */}
                <rect x={cx - slot / 2} y={margin.top} width={slot} height={plotH} fill="transparent" />
                {h > 0 && <path d={columnPath(cx - barW / 2, y(d.value), barW, h)} fill={active === i ? INK_ACTIVE : INK} />}
                {i % labelEvery === 0 && (
                  <text x={cx} y={height - 10} textAnchor="middle" fontSize={11} fill={AXIS_TEXT}>
                    {d.label}
                  </text>
                )}
              </g>
            )
          })}
        </svg>
      )}
      {active !== null && data[active] && (
        <Tooltip x={margin.left + slot * active + slot / 2} y={y(data[active].value)}>
          <span className="font-medium text-zinc-900">{data[active].label}</span> · {data[active].detail ?? format(data[active].value)}
        </Tooltip>
      )}
    </div>
  )
}

/** Horizontal bars with the value at the tip, e.g. average score per question. */
export function BarChart({ data, title, format = defaultFormat, max, className }: ChartProps) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [active, setActive] = useState<number | null>(null)
  const ticks = niceTicks(max ?? Math.max(...data.map((d) => d.value), 0))
  const top = ticks[ticks.length - 1]!
  const row = 36
  const margin = { top: 4, right: 48, bottom: 22, left: 56 }
  const plotW = Math.max(0, width - margin.left - margin.right)
  const height = margin.top + row * data.length + margin.bottom
  const barH = Math.min(BAR_MAX, row - 14)
  const x = (v: number) => margin.left + (v / top) * plotW

  return (
    <div ref={ref} className={cn('relative', className)}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={title} className="block overflow-visible">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={x(t)} x2={x(t)} y1={margin.top} y2={height - margin.bottom} stroke={GRID} strokeWidth={1} shapeRendering="crispEdges" />
              <text x={x(t)} y={height - 6} textAnchor="middle" fontSize={11} fill={AXIS_TEXT} className="tabular-nums">
                {format(t)}
              </text>
            </g>
          ))}
          {data.map((d, i) => {
            const cy = margin.top + row * i + row / 2
            const w = (d.value / top) * plotW
            return (
              <g
                key={d.key}
                tabIndex={0}
                role="img"
                aria-label={`${d.label}: ${d.detail ?? format(d.value)}`}
                onMouseEnter={() => setActive(i)}
                onMouseLeave={() => setActive(null)}
                onFocus={() => setActive(i)}
                onBlur={() => setActive(null)}
                className="outline-none"
              >
                <rect x={0} y={cy - row / 2} width={width} height={row} fill="transparent" />
                <text x={margin.left - 10} y={cy} dy="0.32em" textAnchor="end" fontSize={12} fill="#3f3f46">
                  {d.label}
                </text>
                {w > 0 && <path d={barPath(margin.left, cy - barH / 2, w, barH)} fill={active === i ? INK_ACTIVE : INK} />}
                <text x={margin.left + w + 6} y={cy} dy="0.32em" fontSize={12} fill="#3f3f46" className="tabular-nums">
                  {format(d.value)}
                </text>
              </g>
            )
          })}
        </svg>
      )}
      {active !== null && data[active]?.detail && (
        <Tooltip below x={margin.left + Math.max(80, (data[active].value / top) * plotW) / 2} y={margin.top + row * active + row / 2 + barH / 2}>
          <span className="font-medium text-zinc-900">{data[active].label}</span> · {data[active].detail}
        </Tooltip>
      )}
    </div>
  )
}

/** A chart with a "Show table" toggle so every value is also readable as text. */
export function ChartWithTable({
  chart,
  columns,
  rows,
}: {
  chart: ReactNode
  columns: [string, string]
  rows: [string, string][]
}) {
  const [table, setTable] = useState(false)
  return (
    <div>
      {table ? (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-200 text-left text-xs text-zinc-500">
              <th className="py-2 font-medium">{columns[0]}</th>
              <th className="py-2 text-right font-medium">{columns[1]}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, value]) => (
              <tr key={label} className="border-b border-zinc-100 last:border-0">
                <td className="py-1.5 text-zinc-700">{label}</td>
                <td className="py-1.5 text-right text-zinc-900 tabular-nums">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        chart
      )}
      <button type="button" onClick={() => setTable((t) => !t)} className="mt-3 text-xs font-medium text-zinc-500 hover:text-zinc-900">
        {table ? 'Show chart' : 'Show table'}
      </button>
    </div>
  )
}
