function xmlEscape(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function cellXml(value) {
  if (value == null) {
    return '<Cell><Data ss:Type="String"></Data></Cell>';
  }
  const isNumber = typeof value === "number" && Number.isFinite(value);
  const type = isNumber ? "Number" : "String";
  return `<Cell><Data ss:Type="${type}">${xmlEscape(value)}</Data></Cell>`;
}

export function downloadExcel(filename, rows, sheetName = "Sheet1") {
  const rowsXml = (rows || [])
    .map((row) => `<Row>${(row || []).map(cellXml).join("")}</Row>`)
    .join("");

  const xml = [
    '<?xml version="1.0"?>',
    '<?mso-application progid="Excel.Sheet"?>',
    '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">',
    `<Worksheet ss:Name="${xmlEscape(sheetName)}"><Table>`,
    rowsXml,
    "</Table></Worksheet>",
    "</Workbook>",
  ].join("");

  const blob = new Blob([xml], { type: "application/vnd.ms-excel;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
