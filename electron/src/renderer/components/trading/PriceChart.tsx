/**
 * JARVIS Price Chart Component — Lightweight candlestick chart for trading.
 *
 * Uses HTML Canvas for performant rendering.
 * Supports real-time price updates via WebSocket.
 */
import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { COLORS, FONT } from '../../lib/theme';

interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface PriceChartProps {
  symbol: string;
  candles: Candle[];
  width?: number;
  height?: number;
  showVolume?: boolean;
  entryPrice?: number;
  tpPrice?: number;
  slPrice?: number;
}

const CHART_COLORS = {
  bullish: '#22c55e',
  bearish: '#ef4444',
  grid: 'rgba(255,255,255,0.05)',
  text: 'rgba(255,255,255,0.5)',
  entry: '#f59e0b',
  tp: '#22c55e',
  sl: '#ef4444',
  volume: 'rgba(255,255,255,0.08)',
  bg: '#0a0a12',
};

export default function PriceChart({
  symbol,
  candles,
  width = 600,
  height = 300,
  showVolume = true,
  entryPrice,
  tpPrice,
  slPrice,
}: PriceChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hoveredCandle, setHoveredCandle] = useState<Candle | null>(null);

  const drawChart = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || candles.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    // Clear
    ctx.fillStyle = CHART_COLORS.bg;
    ctx.fillRect(0, 0, width, height);

    const padding = { top: 10, right: 60, bottom: showVolume ? 60 : 30, left: 10 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;
    const volumeH = showVolume ? 40 : 0;
    const priceH = chartH - volumeH;

    // Calculate price range
    const prices = candles.flatMap(c => [c.high, c.low]);
    let minPrice = Math.min(...prices);
    let maxPrice = Math.max(...prices);
    const priceRange = maxPrice - minPrice || 1;
    // Add 5% padding
    minPrice -= priceRange * 0.05;
    maxPrice += priceRange * 0.05;
    const adjRange = maxPrice - minPrice;

    // Volume range
    const maxVol = Math.max(...candles.map(c => c.volume)) || 1;

    const candleW = Math.max(1, chartW / candles.length - 1);
    const gap = 1;

    // Draw grid lines
    ctx.strokeStyle = CHART_COLORS.grid;
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const y = padding.top + (priceH * i) / 4;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();

      // Price label
      const price = maxPrice - (adjRange * i) / 4;
      ctx.fillStyle = CHART_COLORS.text;
      ctx.font = '9px monospace';
      ctx.textAlign = 'left';
      ctx.fillText(price.toFixed(2), width - padding.right + 4, y + 3);
    }

    // Draw candles
    candles.forEach((candle, i) => {
      const x = padding.left + i * (candleW + gap);
      const isBullish = candle.close >= candle.open;
      const color = isBullish ? CHART_COLORS.bullish : CHART_COLORS.bearish;

      // Wick
      const wickX = x + candleW / 2;
      const highY = padding.top + ((maxPrice - candle.high) / adjRange) * priceH;
      const lowY = padding.top + ((maxPrice - candle.low) / adjRange) * priceH;
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(wickX, highY);
      ctx.lineTo(wickX, lowY);
      ctx.stroke();

      // Body
      const openY = padding.top + ((maxPrice - candle.open) / adjRange) * priceH;
      const closeY = padding.top + ((maxPrice - candle.close) / adjRange) * priceH;
      const bodyTop = Math.min(openY, closeY);
      const bodyH = Math.max(1, Math.abs(closeY - openY));
      ctx.fillStyle = isBullish ? color : color;
      ctx.globalAlpha = isBullish ? 0.3 : 0.8;
      ctx.fillRect(x, bodyTop, candleW, bodyH);
      ctx.globalAlpha = 1;
      ctx.strokeStyle = color;
      ctx.strokeRect(x, bodyTop, candleW, bodyH);

      // Volume bar
      if (showVolume) {
        const volH = (candle.volume / maxVol) * volumeH;
        const volY = padding.top + priceH + (volumeH - volH);
        ctx.fillStyle = color;
        ctx.globalAlpha = 0.15;
        ctx.fillRect(x, volY, candleW, volH);
        ctx.globalAlpha = 1;
      }
    });

    // Draw horizontal levels (entry, TP, SL)
    const drawLevel = (price: number, color: string, label: string) => {
      if (price < minPrice || price > maxPrice) return;
      const y = padding.top + ((maxPrice - price) / adjRange) * priceH;
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
      ctx.setLineDash([]);

      // Label
      ctx.fillStyle = color;
      ctx.font = 'bold 9px monospace';
      ctx.textAlign = 'left';
      ctx.fillText(`${label} ${price.toFixed(2)}`, width - padding.right + 4, y - 4);
    };

    if (entryPrice) drawLevel(entryPrice, CHART_COLORS.entry, 'ENTRY');
    if (tpPrice) drawLevel(tpPrice, CHART_COLORS.tp, 'TP');
    if (slPrice) drawLevel(slPrice, CHART_COLORS.sl, 'SL');

    // Symbol label
    ctx.fillStyle = COLORS.text;
    ctx.font = 'bold 14px monospace';
    ctx.textAlign = 'left';
    ctx.fillText(symbol, padding.left + 4, padding.top + 16);

    // Current price
    if (candles.length > 0) {
      const last = candles[candles.length - 1];
      const priceColor = last.close >= last.open ? CHART_COLORS.bullish : CHART_COLORS.bearish;
      ctx.fillStyle = priceColor;
      ctx.font = 'bold 12px monospace';
      ctx.fillText(last.close.toFixed(2), padding.left + 4 + ctx.measureText(symbol).width + 10, padding.top + 16);
    }
  }, [candles, width, height, showVolume, symbol, entryPrice, tpPrice, slPrice]);

  useEffect(() => {
    drawChart();
  }, [drawChart]);

  return (
    <div style={{
      borderRadius: 8,
      border: `1px solid ${COLORS.border}`,
      overflow: 'hidden',
      backgroundColor: CHART_COLORS.bg,
    }}>
      <canvas
        ref={canvasRef}
        style={{ width, height, display: 'block' }}
      />
      {hoveredCandle && (
        <div style={{
          padding: '4px 8px',
          fontSize: 10,
          color: COLORS.textDim,
          fontFamily: 'monospace',
          borderTop: `1px solid ${COLORS.border}`,
        }}>
          O:{hoveredCandle.open.toFixed(2)} H:{hoveredCandle.high.toFixed(2)}{' '}
          L:{hoveredCandle.low.toFixed(2)} C:{hoveredCandle.close.toFixed(2)}{' '}
          V:{hoveredCandle.volume.toFixed(0)}
        </div>
      )}
    </div>
  );
}
