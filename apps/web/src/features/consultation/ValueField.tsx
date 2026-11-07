import { Input, Select, Textarea } from "@/components/ui/input";

interface Props {
  dataType: string;
  enumValues?: string[];
  enumLabels?: Record<string, string>;
  value: string;
  onChange: (v: string) => void;
  id?: string;
  invalid?: boolean;
  autoFocus?: boolean;
  placeholder?: string;
}

/** Input matched to a fact's data type. Value is always handled as a string. */
export function ValueField({
  dataType,
  enumValues = [],
  enumLabels = {},
  value,
  onChange,
  id,
  invalid,
  autoFocus,
  placeholder,
}: Props) {
  const common = { id, "aria-invalid": invalid || undefined, autoFocus } as const;
  switch (dataType) {
    case "boolean":
      return (
        <Select {...common} value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">Bitte wählen …</option>
          <option value="ja">Ja</option>
          <option value="nein">Nein</option>
        </Select>
      );
    case "date":
      return <Input {...common} type="date" value={value} onChange={(e) => onChange(e.target.value)} />;
    case "integer":
      return (
        <Input
          {...common}
          type="number"
          inputMode="numeric"
          min={0}
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    case "enum":
      return (
        <Select {...common} value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">Bitte wählen …</option>
          {enumValues.map((v) => (
            <option key={v} value={v}>
              {enumLabels[v] ?? v}
            </option>
          ))}
        </Select>
      );
    default:
      return (
        <Textarea
          {...common}
          rows={2}
          className="min-h-[64px]"
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      );
  }
}

/** Convert an existing typed fact value into the string used by ValueField. */
export function valueToField(value: unknown): string {
  if (value === true) return "ja";
  if (value === false) return "nein";
  if (value === null || value === undefined) return "";
  return String(value);
}
