/**
 * Formats a raw number into an abbreviated compact string form:
 * - 24330 -> "24.33K"
 * - 1223330 -> "1.22M"
 * - 2400000000 -> "2.4B"
 * Rounds to 2 decimal places and strips trailing zeros where sensible (e.g. "1.20K" -> "1.2K").
 */
export function formatCompactNumber(num: number): string {
  if (num === 0) return "0";

  const absNum = Math.abs(num);
  let value: number;
  let suffix: string;

  if (absNum >= 1.0e9) {
    value = num / 1.0e9;
    suffix = "B";
  } else if (absNum >= 1.0e6) {
    value = num / 1.0e6;
    suffix = "M";
  } else if (absNum >= 1.0e3) {
    value = num / 1.0e3;
    suffix = "K";
  } else {
    value = num;
    suffix = "";
  }

  // Round to 2 decimal places
  let formatted = value.toFixed(2);

  // Strip trailing decimal parts if they are zeros
  if (formatted.includes(".")) {
    // e.g. "1.20" -> "1.2"
    // e.g. "1.00" -> "1"
    while (formatted.endsWith("0")) {
      formatted = formatted.slice(0, -1);
    }
    if (formatted.endsWith(".")) {
      formatted = formatted.slice(0, -1);
    }
  }

  return formatted + suffix;
}
