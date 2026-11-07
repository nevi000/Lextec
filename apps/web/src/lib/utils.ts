import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const dateTime = new Intl.DateTimeFormat("de-CH", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});
const dateOnly = new Intl.DateTimeFormat("de-CH", { day: "2-digit", month: "2-digit", year: "numeric" });

/** Server timestamps are UTC; naive strings (no offset) are treated as UTC. */
export function parseServerDate(value: string): Date {
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(value);
  return new Date(hasZone ? value : `${value}Z`);
}

export function formatDateTime(value: string | null | undefined): string {
  return value ? dateTime.format(parseServerDate(value)) : "–";
}

export function formatDate(value: string | null | undefined): string {
  return value ? dateOnly.format(parseServerDate(value)) : "–";
}

export function relativeTime(value: string): string {
  const diff = Date.now() - parseServerDate(value).getTime();
  const min = Math.round(diff / 60000);
  if (min < 1) return "gerade eben";
  if (min < 60) return `vor ${min} Min.`;
  const h = Math.round(min / 60);
  if (h < 24) return `vor ${h} Std.`;
  return formatDate(value);
}

/** Display a typed fact value (booleans -> Ja/Nein, ISO dates -> dd.mm.yyyy). */
export function displayValue(value: unknown): string {
  if (value === true) return "Ja";
  if (value === false) return "Nein";
  if (value === null || value === undefined || value === "") return "–";
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [y, m, d] = value.split("-");
    return `${d}.${m}.${y}`;
  }
  return String(value);
}
