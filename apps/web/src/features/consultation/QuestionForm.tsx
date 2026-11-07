import { ChevronDown, CircleHelp, Clock3 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { NextQuestion } from "@/types";
import { ValueField } from "./ValueField";

function Choice({ label, selected, disabled, onClick }: { label: string; selected: boolean; disabled: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "rounded-lg border px-5 py-2.5 text-[14px] font-medium transition-colors disabled:opacity-50",
        selected ? "border-brand-600 bg-brand-600 text-white" : "border-line-strong bg-surface hover:bg-brand-50",
      )}
    >
      {label}
    </button>
  );
}

/**
 * One question at a time. Yes/No and short choices are selected, then saved with one primary button.
 * «Weiss nicht» is a separate action (stored as asked-but-unknown, never re-asked); «Später beantworten» /
 * «Überspringen» are secondary. Optional questions use the lighter «Weiter» / «Überspringen» wording.
 */
export function QuestionForm({
  question,
  busy,
  disabled,
  optionalMode = false,
  onAnswer,
  onUnknown,
  onDefer,
}: {
  question: NextQuestion;
  busy: boolean;
  disabled: boolean;
  optionalMode?: boolean;
  onAnswer: (text: string) => void;
  onUnknown: () => void;
  onDefer: () => void;
}) {
  const [value, setValue] = useState("");
  const isBool = question.data_type === "boolean";
  const labels = question.enum_labels_de ?? {};
  const enumValues = question.enum_values ?? [];
  const isChoice = question.data_type === "enum" && enumValues.length > 0 && enumValues.length <= 4;
  const off = busy || disabled;

  function submit() {
    const v = value.trim();
    if (!v) return;
    // enum answers are sent as their readable label (the server maps it back to the value)
    onAnswer(question.data_type === "enum" ? (labels[v] ?? v) : v);
    setValue("");
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <p className="text-[19px] font-semibold leading-snug">{question.question_de}</p>
      {question.deferred && (
        <p className="mt-1 inline-flex items-center gap-1.5 text-[12.5px] text-ask-fg">
          <Clock3 className="size-3.5" aria-hidden /> Früher zurückgestellt, daher erneut gefragt.
        </p>
      )}
      {question.why_needed_de && (
        <details className="group mt-2">
          <summary className="inline-flex cursor-pointer list-none items-center gap-1 text-[12.5px] font-medium text-brand-600 hover:underline">
            <ChevronDown className="size-3.5 transition-transform group-open:rotate-180" aria-hidden />
            Warum ist das wichtig?
          </summary>
          <p className="mt-1.5 max-w-xl text-[13px] text-ink-muted">{question.why_needed_de}</p>
        </details>
      )}

      <div className="mt-4">
        {isBool ? (
          <div role="radiogroup" aria-label="Antwort" className="flex flex-wrap gap-2">
            <Choice label="Ja" selected={value === "Ja"} disabled={off} onClick={() => setValue("Ja")} />
            <Choice label="Nein" selected={value === "Nein"} disabled={off} onClick={() => setValue("Nein")} />
          </div>
        ) : isChoice ? (
          <div role="radiogroup" aria-label="Antwort" className="flex flex-wrap gap-2">
            {enumValues.map((v) => (
              <Choice key={v} label={labels[v] ?? v} selected={value === v} disabled={off} onClick={() => setValue(v)} />
            ))}
          </div>
        ) : (
          <ValueField
            id="answer-input"
            dataType={question.data_type}
            enumValues={enumValues}
            enumLabels={labels}
            value={value}
            onChange={setValue}
            placeholder="Antwort erfassen …"
          />
        )}
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <Button type="submit" variant="primary" size="lg" loading={busy} disabled={disabled || !value.trim()}>
          Antwort speichern und weiter
        </Button>
        <Button type="button" variant="ghost" disabled={off} onClick={onUnknown} title="Gefragt, die Klientin weiss es nicht">
          <CircleHelp /> Weiss nicht
        </Button>
        <Button type="button" variant="ghost" disabled={off} onClick={onDefer}>
          <Clock3 /> {optionalMode ? "Überspringen" : "Später beantworten"}
        </Button>
      </div>
    </form>
  );
}
