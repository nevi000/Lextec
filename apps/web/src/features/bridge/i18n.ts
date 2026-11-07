/** Static phone UI texts (no machine translation of interface text). Question texts are translated server-side. */
export type Lang = "de" | "en" | "ar" | "uk";

export const LANGUAGES: { code: Lang; name: string }[] = [
  { code: "de", name: "Deutsch" },
  { code: "en", name: "English" },
  { code: "ar", name: "العربية" },
  { code: "uk", name: "Українська" },
];

export interface Strings {
  intro: string;
  chooseLanguage: string;
  privacy: string;
  workerGuides: string;
  connected: string;
  waitingQuestion: string;
  yes: string;
  no: string;
  unknown: string;
  send: string;
  sending: string;
  sent: string;
  reviewing: string;
  paused: string;
  completed: string;
  ended: string;
  connectionLost: string;
  preparing: string;
  retrying: string;
  translationFailed: string;
  why: string;
  yourAnswer: string;
  invalid: string;
  stale: string;
  noLink: string;
}

export const T: Record<Lang, Strings> = {
  de: {
    intro: "Beantworten Sie die Fragen der Sozialarbeiterin bequem auf Ihrem Smartphone.",
    chooseLanguage: "Sprache wählen",
    privacy:
      "Ihre Antworten werden an die Sozialarbeiterin übertragen. Fragen und Antworten können maschinell übersetzt werden. Es werden keine Fallakten auf Ihr Gerät geladen.",
    workerGuides: "Die Sozialarbeiterin begleitet den Ablauf.",
    connected: "Mit der Sozialarbeiterin verbunden",
    waitingQuestion: "Einen Moment bitte. Die nächste Frage erscheint automatisch.",
    yes: "Ja",
    no: "Nein",
    unknown: "Weiss nicht",
    send: "Antwort senden",
    sending: "Wird gesendet …",
    sent: "Antwort gesendet",
    reviewing: "Die Sozialarbeiterin prüft Ihre Antwort.",
    paused: "Die Befragung wurde vorübergehend pausiert.",
    completed: "Vielen Dank. Die Befragung ist abgeschlossen.",
    ended: "Diese Befragung wurde beendet. Bitte wenden Sie sich an Ihre Sozialarbeiterin.",
    connectionLost: "Verbindung wird wiederhergestellt …",
    preparing: "Die Frage wird vorbereitet …",
    retrying: "Verbindung wird wiederhergestellt …",
    translationFailed: "Diese Frage kann gerade nicht übersetzt werden. Die Sozialarbeiterin erklärt sie Ihnen.",
    why: "Warum wird das gefragt?",
    yourAnswer: "Ihre Antwort",
    invalid: "Bitte prüfen Sie Ihre Eingabe.",
    stale: "Die Frage hat sich geändert. Bitte antworten Sie auf die neue Frage.",
    noLink: "Dieser Link ist ungültig. Bitte scannen Sie den QR-Code erneut.",
  },
  en: {
    intro: "Answer the social worker's questions comfortably on your phone.",
    chooseLanguage: "Choose your language",
    privacy:
      "Your answers are sent to the social worker. Questions and answers may be machine-translated. No case file is loaded onto your device.",
    workerGuides: "The social worker guides the process.",
    connected: "Connected to the social worker",
    waitingQuestion: "One moment please. The next question will appear automatically.",
    yes: "Yes",
    no: "No",
    unknown: "I don't know",
    send: "Send answer",
    sending: "Sending …",
    sent: "Answer sent",
    reviewing: "The social worker is reviewing your answer.",
    paused: "The interview has been paused for now.",
    completed: "Thank you. The interview is complete.",
    ended: "This interview has ended. Please contact your social worker.",
    connectionLost: "Reconnecting …",
    preparing: "Preparing the question …",
    retrying: "Reconnecting …",
    translationFailed: "This question cannot be translated right now. The social worker will explain it to you.",
    why: "Why is this asked?",
    yourAnswer: "Your answer",
    invalid: "Please check your input.",
    stale: "The question has changed. Please answer the new question.",
    noLink: "This link is not valid. Please scan the QR code again.",
  },
  ar: {
    intro: "أجب عن أسئلة الأخصائية الاجتماعية بسهولة على هاتفك.",
    chooseLanguage: "اختر لغتك",
    privacy:
      "تُرسل إجاباتك إلى الأخصائية الاجتماعية. قد تُترجم الأسئلة والإجابات آليًا. لا يتم تحميل أي ملف قضية على جهازك.",
    workerGuides: "ترافق الأخصائية الاجتماعية سير العملية.",
    connected: "متصل بالأخصائية الاجتماعية",
    waitingQuestion: "لحظة من فضلك. سيظهر السؤال التالي تلقائيًا.",
    yes: "نعم",
    no: "لا",
    unknown: "لا أعرف",
    send: "إرسال الإجابة",
    sending: "جارٍ الإرسال …",
    sent: "تم إرسال الإجابة",
    reviewing: "تراجع الأخصائية الاجتماعية إجابتك.",
    paused: "تم إيقاف المقابلة مؤقتًا.",
    completed: "شكرًا لك. انتهت المقابلة.",
    ended: "انتهت هذه المقابلة. يرجى التواصل مع الأخصائية الاجتماعية.",
    connectionLost: "جارٍ استعادة الاتصال …",
    preparing: "جارٍ تجهيز السؤال …",
    retrying: "جارٍ إعادة الاتصال …",
    translationFailed: "تعذّرت ترجمة هذا السؤال الآن. ستشرحه لك الأخصائية الاجتماعية.",
    why: "لماذا يُطرح هذا السؤال؟",
    yourAnswer: "إجابتك",
    invalid: "يرجى التحقق مما أدخلته.",
    stale: "تغيّر السؤال. يرجى الإجابة عن السؤال الجديد.",
    noLink: "هذا الرابط غير صالح. يرجى مسح رمز QR مرة أخرى.",
  },
  uk: {
    intro: "Відповідайте на запитання соціальної працівниці зручно на своєму смартфоні.",
    chooseLanguage: "Оберіть мову",
    privacy:
      "Ваші відповіді передаються соціальній працівниці. Запитання та відповіді можуть перекладатися машинним способом. Жодна справа не завантажується на ваш пристрій.",
    workerGuides: "Соціальна працівниця супроводжує процес.",
    connected: "Підключено до соціальної працівниці",
    waitingQuestion: "Зачекайте, будь ласка. Наступне запитання з’явиться автоматично.",
    yes: "Так",
    no: "Ні",
    unknown: "Не знаю",
    send: "Надіслати відповідь",
    sending: "Надсилання …",
    sent: "Відповідь надіслано",
    reviewing: "Соціальна працівниця перевіряє вашу відповідь.",
    paused: "Опитування тимчасово призупинено.",
    completed: "Дякуємо. Опитування завершено.",
    ended: "Це опитування завершено. Зверніться до вашої соціальної працівниці.",
    connectionLost: "Відновлення з’єднання …",
    preparing: "Запитання готується …",
    retrying: "Відновлення з’єднання …",
    translationFailed: "Це запитання зараз неможливо перекласти. Соціальна працівниця пояснить його вам.",
    why: "Чому це запитують?",
    yourAnswer: "Ваша відповідь",
    invalid: "Перевірте введені дані.",
    stale: "Запитання змінилося. Відповідайте на нове запитання.",
    noLink: "Це посилання недійсне. Скануйте QR-код ще раз.",
  },
};

export const isLang = (v: string | null | undefined): v is Lang => !!v && v in T;
