'use client';

import React, { useMemo } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  ChartData,
  ChartOptions,
} from 'chart.js';
import { Bar, Line, Pie, Doughnut } from 'react-chartjs-2';
import { useTheme } from 'next-themes';
import { ChartConfig } from '@/types/chat';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
);

interface ChartViewProps {
  columns: string[];
  rows: any[][];
  config?: ChartConfig;
  height?: number | string;
}

const MODERN_PALETTE = [
  '#2563eb', // Blue
  '#10b981', // Emerald
  '#6366f1', // Indigo
  '#f59e0b', // Amber
  '#ec4899', // Pink
  '#8b5cf6', // Violet
  '#14b8a6', // Teal
  '#06b6d4', // Cyan
  '#f97316', // Orange
];

export default function ChartView({ columns, rows, config, height = 300 }: ChartViewProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const chartDataAndType = useMemo(() => {
    if (!rows || rows.length === 0 || !columns || columns.length === 0) {
      return null;
    }

    let labelColIdx = 0;
    let valColIdx = columns.length > 1 ? 1 : 0;

    // Detect numeric column
    for (let i = 0; i < columns.length; i++) {
      const sampleVal = rows[0][i];
      if (typeof sampleVal === 'number' || (!isNaN(Number(sampleVal)) && sampleVal !== '' && sampleVal !== null)) {
        valColIdx = i;
        labelColIdx = i === 0 ? (columns.length > 1 ? 1 : 0) : 0;
        break;
      }
    }

    const labels = rows.map(r => String(r[labelColIdx] ?? ''));
    const values = rows.map(r => {
      const v = r[valColIdx];
      if (typeof v === 'number') return v;
      const parsed = parseFloat(String(v));
      return isNaN(parsed) ? 0 : parsed;
    });

    const determinedType = config?.type || (rows.length <= 5 ? 'pie' : 'bar');

    const data: ChartData<any> = {
      labels,
      datasets: [
        {
          label: columns[valColIdx] || 'Giá trị',
          data: values,
          backgroundColor: determinedType === 'pie' || determinedType === 'doughnut'
            ? MODERN_PALETTE
            : isDark ? 'rgba(59, 130, 246, 0.85)' : 'rgba(37, 99, 235, 0.85)',
          borderColor: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)',
          borderWidth: 1,
          borderRadius: determinedType === 'bar' ? 6 : 0,
        },
      ],
    };

    return { data, type: determinedType };
  }, [columns, rows, config, isDark]);

  if (!chartDataAndType) {
    return (
      <div className="flex items-center justify-center h-48 text-sm text-zinc-400">
        Không có dữ liệu định lượng để vẽ biểu đồ
      </div>
    );
  }

  const textColor = isDark ? '#a1a1aa' : '#52525b';
  const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)';

  const options: ChartOptions<any> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: chartDataAndType.type === 'pie' || chartDataAndType.type === 'doughnut' ? 'right' : 'top',
        labels: {
          color: textColor,
          font: { family: 'Inter', size: 12 },
          padding: 12,
        },
      },
      tooltip: {
        backgroundColor: isDark ? '#18181b' : '#ffffff',
        titleColor: isDark ? '#f4f4f5' : '#09090b',
        bodyColor: isDark ? '#d4d4d8' : '#27272a',
        borderColor: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
        borderWidth: 1,
        padding: 10,
        boxPadding: 4,
        cornerRadius: 8,
      },
    },
    scales:
      chartDataAndType.type === 'pie' || chartDataAndType.type === 'doughnut'
        ? {}
        : {
            x: {
              ticks: { color: textColor, font: { family: 'Inter', size: 11 } },
              grid: { color: gridColor },
            },
            y: {
              ticks: { color: textColor, font: { family: 'Inter', size: 11 } },
              grid: { color: gridColor },
            },
          },
  };

  return (
    <div style={{ height }} className="w-full relative">
      {chartDataAndType.type === 'bar' && <Bar data={chartDataAndType.data} options={options} />}
      {chartDataAndType.type === 'line' && <Line data={chartDataAndType.data} options={options} />}
      {chartDataAndType.type === 'pie' && <Pie data={chartDataAndType.data} options={options} />}
      {chartDataAndType.type === 'doughnut' && <Doughnut data={chartDataAndType.data} options={options} />}
    </div>
  );
}
