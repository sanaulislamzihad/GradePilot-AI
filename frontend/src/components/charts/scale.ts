/** Round the axis maximum up to a clean value and return evenly spaced ticks. */
export function niceTicks(max: number, count = 4): number[] {
  if (max <= 0) return [0, 1]
  const rough = max / count
  const magnitude = 10 ** Math.floor(Math.log10(rough))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= rough) ?? rough
  const ticks: number[] = []
  for (let t = 0; t <= max + step * 0.001 || ticks.length < 2; t += step) ticks.push(Number(t.toFixed(6)))
  if (ticks[ticks.length - 1]! < max) ticks.push(Number((ticks[ticks.length - 1]! + step).toFixed(6)))
  return ticks
}
