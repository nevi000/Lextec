/** Synthetic demo case "Mietkündigung Zürich" (Issue 1). All data is invented. */
export const DEMO_TITLE = "Demo: Mietkündigung Zürich";

export interface DemoStep {
  id: number;
  title: string;
  /** Prepared answer that goes through the NORMAL analysis pipeline (nothing is hard-coded). */
  text: string | null;
  optional?: boolean;
  expect: string[];
}

export const DEMO_STEPS: DemoStep[] = [
  {
    id: 1,
    title: "Unvollständige Schilderung",
    text:
      "Ich betreue eine Klientin in Zürich. Sie hat von ihrem Vermieter die Kündigung für ihre Wohnung erhalten und weiss nicht, ob sie ausziehen muss.",
    expect: [
      "Rechtsgebiet «Kündigung durch die Vermieterschaft» wird erkannt.",
      "Im Fallüberblick erscheint die Gemeinde «Zürich» als KI-extrahierte, noch nicht bestätigte Angabe.",
      "Nächste Rückfrage: ob die Klientin selbst Mieterin laut Vertrag ist, mit «Warum ist das wichtig?».",
    ],
  },
  {
    id: 2,
    title: "Angaben zum Mietverhältnis",
    text:
      "Die Klientin ist alleinige Mieterin einer normalen Wohnung in der Stadt Zürich. Der Vertrag ist unbefristet. Es handelt sich nicht um eine Untermiete oder Ferienwohnung.",
    expect: [
      "Mieterrolle, Objektart und Vertragsart werden ergänzt; Mitmieter «Nein».",
      "Bereits bekannte Angaben werden nicht erneut gefragt.",
      "Nächste Rückfrage: wie die Kündigung zugestellt wurde.",
    ],
  },
  {
    id: 3,
    title: "Zustellung und Form",
    text:
      "Die Kündigung hat sie am 4. November 2026 mit normaler Post erhalten. Es war nur ein gewöhnlicher Brief ohne amtliches Kündigungsformular. Die Kündigung soll per 31. Januar 2027 gelten.",
    expect: [
      "Zustellart «Normale Post», Empfangsdatum 04.11.2026 und Kündigungstermin 31.01.2027 werden erkannt.",
      "«Fachperson nötig»: Regel TT_FORM_MISSING (möglicher Formmangel), Dringlichkeit «bald».",
      "Interne Einschätzung: wenige Tage seit Empfang. Es wird KEIN Fristende berechnet und keine Aussage zur Gültigkeit gemacht.",
      "Unter «Allgemeine Hinweise» stehen freigegebene Aussagen mit Quellen (z. B. 30-Tage-Anfechtung, amtliches Formular).",
    ],
  },
  {
    id: 4,
    title: "Weitere Kontextinformationen",
    optional: true,
    text:
      "Die Klientin hat keine Mietrückstände. Es gibt keine weiteren Mitmieter und keine Ehe- oder eingetragene Partnerperson in der Wohnung. Sie hat noch nichts unterschrieben und keine Anfechtung eingereicht.",
    expect: [
      "Weitere Pflichtangaben sind bekannt; es bleiben nur noch optionale Fragen (z. B. Härtegründe, Kündigungsgrund).",
      "Zusätzlich greift die Regel «alle Angaben bekannt, noch nicht zeitkritisch».",
      "Tipp: Beantworten Sie eine offene Frage mit «Weiss nicht», um den Unterschied zu «noch nicht gefragt» zu sehen.",
    ],
  },
  {
    id: 5,
    title: "Expert Briefing öffnen",
    text: null,
    expect: [
      "Fachliche Übersicht mit Vorprüfung, Zustellung, Form, Inhalt, Vorgeschichte und sozialen Umständen.",
      "Pro Angabe die Herkunft: angegeben, KI-extrahiert, bestätigt oder noch ungeklärt.",
      "Ausgelöste Regeln mit Dringlichkeit, offene Fragen, Quellen (Law-Dossier-Status getrennt von der Systemprüfung).",
      "Über «Drucken / Als PDF speichern» als PDF sicherbar.",
    ],
  },
];
