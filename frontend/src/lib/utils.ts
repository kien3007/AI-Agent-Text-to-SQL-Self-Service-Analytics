import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function normalizeData(rawCols?: string[], rawRows?: any[]): { columns: string[]; rows: any[][] } {
  if (!rawRows || !Array.isArray(rawRows) || rawRows.length === 0) {
    return { columns: rawCols || [], rows: [] };
  }

  let cols = rawCols && rawCols.length > 0 ? [...rawCols] : null;
  if (!cols || cols.length === 0) {
    if (typeof rawRows[0] === 'object' && !Array.isArray(rawRows[0]) && rawRows[0] !== null) {
      cols = Object.keys(rawRows[0]);
    } else {
      cols = ['Value'];
    }
  }

  const rows = rawRows.map(r => {
    if (Array.isArray(r)) return r;
    if (typeof r === 'object' && r !== null) {
      return cols!.map(c => r[c]);
    }
    return [r];
  });

  return { columns: cols, rows: rows };
}

export function formatCellValue(val: any): string {
  if (typeof val === 'number') {
    return val.toLocaleString('vi-VN');
  }
  return String(val ?? '');
}

export function formatStepName(stepKey: string): string {
  const map: Record<string, string> = {
    'intent_clarifier': '1. Phân tích Ý định & Làm rõ (Intent Clarifier)',
    'intent_detector': '1. Phân tích Ý định & Làm rõ (Intent Clarifier)',
    'schema_linking': '2. Liên kết Ngữ nghĩa (Schema Linker)',
    'schema_linker': '2. Liên kết Ngữ nghĩa (Schema Linker)',
    'sql_generator': '3. Sinh SQL (DIN/DAIL-SQL)',
    'plan_validator': '4. Kiểm duyệt An toàn (5-Tier Guardrail)',
    'self_correction_retry': '4.1. Tự sửa lỗi truy vấn (Self-Correction)',
    'hitl_gate': '5. Cổng kiểm duyệt Con người (HITL Gate)',
    'executor': '6. Thực thi Warehouse OLAP',
    'response_formatter': '7. Định dạng Nhận định (Business Insights)'
  };
  return map[stepKey] || stepKey;
}

export function exportDataToCsv(columns: string[], rows: any[][], filenamePrefix: string = 'sana_analytics') {
  if (!columns || !rows || rows.length === 0) {
    alert('Không có dữ liệu để xuất file CSV.');
    return;
  }

  let csvContent = 'data:text/csv;charset=utf-8,\uFEFF';
  csvContent += columns.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',') + '\r\n';
  rows.forEach(r => {
    csvContent += r.map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(',') + '\r\n';
  });

  const encodedUri = encodeURI(csvContent);
  const link = document.createElement('a');
  link.setAttribute('href', encodedUri);
  link.setAttribute('download', `${filenamePrefix}_${Date.now()}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
