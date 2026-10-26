export type CsvCell = string | number | null | undefined;

function escapeCell(value: CsvCell): string {
  const s = value == null ? "" : String(value);
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function buildCsv(rows: CsvCell[][]): string {
  return rows.map((row) => row.map(escapeCell).join(",")).join("\r\n");
}

/** 导出带 UTF-8 BOM 的 CSV，Excel 打开中文不乱码 */
export function downloadCsv(filename: string, rows: CsvCell[][]): void {
  const blob = new Blob([`\ufeff${buildCsv(rows)}`], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
