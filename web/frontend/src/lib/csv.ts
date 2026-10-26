/** CSV 单元格转义（引号包裹 + 内部双引号翻倍） */
function escapeCell(value: string | number | null | undefined): string {
  const s = value == null ? "" : String(value);
  return `"${s.replace(/"/g, '""')}"`;
}

/** 生成 CSV 文本；开头加 UTF-8 BOM，Excel 直接打开中文不乱码 */
export function buildCsv(
  headers: string[],
  rows: (string | number | null)[][],
): string {
  const lines = [headers, ...rows].map((row) => row.map(escapeCell).join(","));
  return "\uFEFF" + lines.join("\r\n");
}

/** 触发浏览器下载 CSV 文件 */
export function downloadCsv(
  filename: string,
  headers: string[],
  rows: (string | number | null)[][],
): void {
  const content = buildCsv(headers, rows);
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}