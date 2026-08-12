// Office Script for the Excel Online (Business) "Run script" action in
// Shared-AppraisalReviewOrchestrator. Add this to the tracker template file
// via Excel Online > Automate > New Script, paste this file's contents,
// save it as "PopulateAppraisalReviewCells", then select it in the flow's
// Run Script action (see DEPLOYMENT.md, Part D).
//
// Every parameter is typed as string so the flow can always pass
// "Not Stated" for a missing value without a type mismatch; this script
// decides whether a value belongs in the cell as a number, a date, or text.

function main(
  workbook: ExcelScript.Workbook,
  occupancyType: string,
  cityState: string,
  streetAddress: string,
  collateralAnalysisValue: string,
  valuationType: string,
  appraiserNames: string,
  appraisalDate: string,
  reviewerName: string,
  reviewDate: string,
  grossBuildingAreaSqFt: string,
  netRentableAreaSqFt: string,
  numberOfBuildings: string,
  yearBuiltOrRemodeled: string,
  remainingEconomicLifeYears: string,
  generalCondition: string,
  marketExposureTime: string,
  meetsHighestAndBestUse: string
) {
  const sheet = workbook.getWorksheet("RE Collateral");
  if (!sheet) {
    throw new Error("Worksheet 'RE Collateral' was not found in this workbook. Confirm the template's sheet name matches exactly (case-sensitive).");
  }

  setText(sheet, "F23", occupancyType);
  setText(sheet, "F24", cityState);
  setText(sheet, "F25", streetAddress);
  setNumberOrText(sheet, "F26", collateralAnalysisValue);
  setText(sheet, "F27", valuationType);
  setText(sheet, "F29", appraiserNames);
  setDateOrText(sheet, "F30", appraisalDate);
  setText(sheet, "F31", reviewerName);
  setDateOrText(sheet, "F32", reviewDate);

  setNumberOrText(sheet, "I21", grossBuildingAreaSqFt);
  setNumberOrText(sheet, "I22", netRentableAreaSqFt);
  setNumberOrText(sheet, "I23", numberOfBuildings);
  setText(sheet, "I24", yearBuiltOrRemodeled);
  setNumberOrText(sheet, "I25", remainingEconomicLifeYears);
  setText(sheet, "I26", generalCondition);
  setText(sheet, "I27", marketExposureTime);
  setText(sheet, "I28", meetsHighestAndBestUse);
}

function setText(sheet: ExcelScript.Worksheet, address: string, value: string): void {
  sheet.getRange(address).setValue(value ? value : "Not Stated");
}

function setNumberOrText(sheet: ExcelScript.Worksheet, address: string, value: string): void {
  const num = Number(value);
  const cellValue = value && !isNaN(num) ? num : (value ? value : "Not Stated");
  sheet.getRange(address).setValue(cellValue);
}

function setDateOrText(sheet: ExcelScript.Worksheet, address: string, isoDate: string): void {
  const serial = toExcelSerialDate(isoDate);
  sheet.getRange(address).setValue(serial !== null ? serial : (isoDate ? isoDate : "Not Stated"));
}

// Converts a "YYYY-MM-DD" string to an Excel date serial number so the cell
// stays a real date (sortable, formattable) instead of text. Office Scripts
// has no built-in string-to-date parser, so this mirrors Excel's own date
// system (day 0 = 1899-12-30, which correctly absorbs the 1900 leap-year bug).
function toExcelSerialDate(isoDate: string): number | null {
  if (!isoDate || !/^\d{4}-\d{2}-\d{2}$/.test(isoDate)) {
    return null;
  }
  const parsed = new Date(isoDate + "T00:00:00Z");
  if (isNaN(parsed.getTime())) {
    return null;
  }
  const excelEpoch = Date.UTC(1899, 11, 30);
  return (parsed.getTime() - excelEpoch) / 86400000;
}
