export interface PricePoint {
  date: string;
  price: number;
}

export interface TrendResult {
  type: 'lowest' | 'down' | 'up';
  label: string;
  color: string;
}

export function getPriceTrend(prices: PricePoint[]): TrendResult | null {
  if (!prices || prices.length < 7) return null;
  const sorted = [...prices].sort((a, b) => a.date.localeCompare(b.date));
  const recent7 = sorted.slice(-7).map(p => p.price);
  const past30 = sorted.slice(-30).map(p => p.price);
  const avg7 = recent7.reduce((s, v) => s + v, 0) / recent7.length;
  const avg30 = past30.reduce((s, v) => s + v, 0) / past30.length;
  const minAll = Math.min(...sorted.map(p => p.price));
  const currentPrice = sorted[sorted.length - 1].price;

  if (currentPrice <= minAll) return { type: 'lowest', label: '🎉最安値更新', color: 'pink' };
  if (avg7 < avg30 * 0.95) return { type: 'down', label: '🔻値下がり中', color: 'green' };
  if (avg7 > avg30 * 1.05) return { type: 'up', label: '📈高騰注意', color: 'orange' };
  return null;
}
