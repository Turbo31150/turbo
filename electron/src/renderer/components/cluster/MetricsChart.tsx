/**
 * JARVIS Metrics Chart — Real-time line chart for cluster metrics.
 *
 * Displays GPU temperatures, latency, throughput over time.
 * Uses HTML Canvas for performant rendering with rolling window.
 */
import React, { useRef, useEffect, useCallback } from 'react';
import { COLORS } from '../../lib/theme';

interface DataPoint {
  time: number;
  value: number;
  label?: string;
}

interface MetricSeries {
  name: string;
  color: string;
  data: DataPoint[];
}

interface MetricsChartProps {
  series: MetricSeries[];
  width?: number;
  height?: number;
  title?: string;
  yLabel?: string;
  yMin?: number;
  yMax?: number;
  showLegend?: boolean;
}

export default function MetricsChart({
  series,
  width = 400,
  height = 200,
  title,
  yLabel,
  yMin,
  yMax,
  showLegend = true,
}: MetricsChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    // Background
    ctx.fillStyle = '#0a0a12';
    ctx.fillRect(0, 0, width, height);

    const padding = { top: title ? 28 : 10, right: 50, bottom: 20, left: 10 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    // Calculate ranges
    const allValues = series.flatMap(s => s.data.map(d => d.value));
    if (allValues.length === 0) {
      ctx.fillStyle = COLORS.textDim;
      ctx.font = '11px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('No data', width / 2, height / 2);
      return;
    }

    const dataMin = yMin ?? Math.min(...allValues);
    const dataMax = yMax ?? Math.max(...allValues);
    const range = dataMax - dataMin || 1;

    const allTimes = series.flatMap(s => s.data.map(d => d.time));
    const timeMin = Math.min(...allTimes);
    const timeMax = Math.max(...allTimes);
    const timeRange = timeMax - timeMin || 1;

    // Title
    if (title) {
      ctx.fillStyle = COLORS.text;
      ctx.font = 'bold 11px monospace';
      ctx.textAlign = 'left';
      ctx.fillText(title, padding.left, 16);
    }

    // Grid
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const y = padding.top + (chartH * i) / 4;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();

      const val = dataMax - (range * i) / 4;
      ctx.fillStyle = 'rgba(255,255,255,0.4)';
      ctx.font = '9px monospace';
      ctx.textAlign = 'left';
      ctx.fillText(val.toFixed(1), width - padding.right + 4, y + 3);
    }

    // Draw series
    series.forEach(s => {
      if (s.data.length < 2) return;

      ctx.strokeStyle = s.color;
      ctx.lineWidth = 1.5;
      ctx.beginPath();

      s.data.forEach((d, i) => {
        const x = padding.left + ((d.time - timeMin) / timeRange) * chartW;
        const y = padding.top + ((dataMax - d.value) / range) * chartH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });

      ctx.stroke();

      // Fill area under line
      ctx.globalAlpha = 0.05;
      const lastPoint = s.data[s.data.length - 1];
      const lastX = padding.left + ((lastPoint.time - timeMin) / timeRange) * chartW;
      ctx.lineTo(lastX, padding.top + chartH);
      const firstPoint = s.data[0];
      const firstX = padding.left + ((firstPoint.time - timeMin) / timeRange) * chartW;
      ctx.lineTo(firstX, padding.top + chartH);
      ctx.closePath();
      ctx.fillStyle = s.color;
      ctx.fill();
      ctx.globalAlpha = 1;

      // Current value dot
      const curY = padding.top + ((dataMax - lastPoint.value) / range) * chartH;
      ctx.fillStyle = s.color;
      ctx.beginPath();
      ctx.arc(lastX, curY, 3, 0, Math.PI * 2);
      ctx.fill();
    });

    // Legend
    if (showLegend && series.length > 1) {
      let legendX = padding.left + 4;
      const legendY = height - 8;
      ctx.font = '9px monospace';
      series.forEach(s => {
        ctx.fillStyle = s.color;
        ctx.fillRect(legendX, legendY - 6, 8, 8);
        ctx.fillStyle = COLORS.textDim;
        ctx.textAlign = 'left';
        ctx.fillText(s.name, legendX + 12, legendY + 1);
        legendX += ctx.measureText(s.name).width + 24;
      });
    }

    // Y-axis label
    if (yLabel) {
      ctx.save();
      ctx.translate(6, padding.top + chartH / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.fillStyle = COLORS.textDim;
      ctx.font = '8px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(yLabel, 0, 0);
      ctx.restore();
    }
  }, [series, width, height, title, yLabel, yMin, yMax, showLegend]);

  useEffect(() => {
    draw();
  }, [draw]);

  return (
    <div style={{
      borderRadius: 8,
      border: `1px solid ${COLORS.border}`,
      overflow: 'hidden',
    }}>
      <canvas
        ref={canvasRef}
        style={{ width, height, display: 'block' }}
      />
    </div>
  );
}
