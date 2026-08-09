"""
Multilingual User Interface (#84).

Deliberately a narrow, honest slice, not full coverage: navigation,
footer, and the homepage are fully translated in all three languages
(English, Arabic, Indonesian) -- the pages every visitor sees
regardless of what they came to do. Every other page (Submission
Search, About, Documentation, Settings, Statistics, Compare) is NOT
yet translated and still renders in English regardless of the chosen
locale -- see docs/UI.md for the exact boundary and why (translating
the entire app's ~150+ remaining strings accurately, especially into
Arabic, is real ongoing work, not something to rush through inside a
single pass alongside several other issues).

Journal metadata (title, publisher, subjects, ...) is never
translated by this module -- it's factual source data imported
verbatim from DOAJ/Scopus/SINTA, and translating it would misrepresent
what the journal actually says about itself. Runtime language
switching is a session preference (like show_weaker or the dark-mode
toggle), not a URL prefix -- every route/URL is identical regardless
of locale, satisfying the issue's "preserve URL and API compatibility"
requirement by construction.

RTL: Arabic sets `dir="rtl"` on `<html>` (see base.html) -- real
browser-native right-to-left text flow and block direction for
translated content. This does NOT re-mirror every LTR-coded spacing
utility (ml-*, mr-*, text-left) across the whole existing UI -- that
audit is real, separate work belonging to full coverage, not this
first pass. Translated pages (nav, footer, home) read correctly
right-to-left; untranslated pages remain LTR-styled English text
inside an RTL document, which is honest given they're not translated
at all yet.
"""

SUPPORTED_LOCALES = {
    "en": {"label": "English", "dir": "ltr"},
    "ar": {"label": "العربية", "dir": "rtl"},
    "id": {"label": "Indonesia", "dir": "ltr"},
}

DEFAULT_LOCALE = "en"

_STRINGS = {
    "nav.home": {"en": "Home", "ar": "الرئيسية", "id": "Beranda"},
    "nav.search": {"en": "Submission Search", "ar": "بحث الإرسال", "id": "Pencarian Naskah"},
    "nav.statistics": {"en": "Statistics", "ar": "الإحصائيات", "id": "Statistik"},
    "nav.about": {"en": "About", "ar": "حول", "id": "Tentang"},
    "nav.documentation": {"en": "Documentation", "ar": "التوثيق", "id": "Dokumentasi"},
    "nav.settings": {"en": "Settings", "ar": "الإعدادات", "id": "Pengaturan"},
    "nav.language": {"en": "Language", "ar": "اللغة", "id": "Bahasa"},

    "footer.data_label": {"en": "Data:", "ar": "البيانات:", "id": "Data:"},
    "footer.license_word": {"en": "License", "ar": "الترخيص", "id": "Lisensi"},
    "footer.created_by": {
        "en": "Created and maintained by",
        "ar": "تم الإنشاء والصيانة بواسطة",
        "id": "Dibuat dan dikelola oleh",
    },

    "home.tagline": {
        "en": "Research Assistant for Journal Selection",
        "ar": "مساعد بحثي لاختيار المجلات",
        "id": "Asisten Riset untuk Pemilihan Jurnal",
    },
    "home.hero_title_line1": {
        "en": "Find the right journal",
        "ar": "اعثر على المجلة المناسبة",
        "id": "Temukan jurnal yang tepat",
    },
    "home.hero_title_line2": {
        "en": "for your manuscript",
        "ar": "لمخطوطتك",
        "id": "untuk naskah Anda",
    },
    "home.hero_description_with_stats": {
        "en": "{app_name} matches your manuscript's title, abstract, and keywords against {count} journals across DOAJ, Scopus, Web of Science, and SINTA — with a plain-language explanation for every recommendation.",
        "ar": "يقارن {app_name} عنوان مخطوطتك وملخصها وكلماتها المفتاحية بأكثر من {count} مجلة عبر DOAJ وScopus وWeb of Science وSINTA — مع شرح مبسّط لكل توصية.",
        "id": "{app_name} mencocokkan judul, abstrak, dan kata kunci naskah Anda dengan {count} jurnal dari DOAJ, Scopus, Web of Science, dan SINTA — disertai penjelasan yang mudah dipahami untuk setiap rekomendasi.",
    },
    "home.hero_description_no_stats": {
        "en": "{app_name} matches your manuscript against journals from DOAJ, Scopus, Web of Science, and SINTA — with a plain-language explanation for every recommendation.",
        "ar": "يقارن {app_name} مخطوطتك بمجلات من DOAJ وScopus وWeb of Science وSINTA — مع شرح مبسّط لكل توصية.",
        "id": "{app_name} mencocokkan naskah Anda dengan jurnal dari DOAJ, Scopus, Web of Science, dan SINTA — disertai penjelasan yang mudah dipahami untuk setiap rekomendasi.",
    },
    "home.cta_manuscript": {
        "en": "I have a manuscript",
        "ar": "لدي مخطوطة",
        "id": "Saya punya naskah",
    },
    "home.cta_idea": {
        "en": "I have a research idea",
        "ar": "لدي فكرة بحثية",
        "id": "Saya punya ide penelitian",
    },
    "home.section_journal_database": {
        "en": "Journal Database",
        "ar": "قاعدة بيانات المجلات",
        "id": "Basis Data Jurnal",
    },
    "home.stat_total_journals": {
        "en": "Total Journals",
        "ar": "إجمالي المجلات",
        "id": "Total Jurnal",
    },
    "home.sublabel_wos": {
        "en": "{count} also indexed in Web of Science",
        "ar": "{count} مفهرسة أيضًا في Web of Science",
        "id": "{count} juga terindeks di Web of Science",
    },
    "home.sublabel_garuda": {
        "en": "{count} also indexed in Garuda",
        "ar": "{count} مفهرسة أيضًا في Garuda",
        "id": "{count} juga terindeks di Garuda",
    },
    "home.no_database": {
        "en": "Could not reach the database — see server logs.",
        "ar": "تعذّر الوصول إلى قاعدة البيانات — راجع سجلات الخادم.",
        "id": "Tidak dapat menjangkau basis data — lihat log server.",
    },
    "home.section_coverage": {
        "en": "Supported Indexes & Coverage",
        "ar": "الفهارس المدعومة ونطاق التغطية",
        "id": "Indeks yang Didukung & Cakupan",
    },
    "home.coverage_description": {
        "en": "Some journals are indexed in multiple databases — for example, every Web of Science journal here is also Scopus-indexed (Web of Science is tracked as a tag on Scopus journals, not a separate catalog). The counts below are not additive.",
        "ar": "بعض المجلات مفهرسة في أكثر من قاعدة بيانات — على سبيل المثال، كل مجلة في Web of Science هنا مفهرسة أيضًا في Scopus (يُسجَّل Web of Science كوسم على مجلات Scopus، وليس كفهرس منفصل). الأعداد أدناه غير تراكمية.",
        "id": "Beberapa jurnal terindeks di lebih dari satu basis data — misalnya, setiap jurnal Web of Science di sini juga terindeks Scopus (Web of Science dicatat sebagai tag pada jurnal Scopus, bukan katalog terpisah). Jumlah di bawah ini tidak bersifat akumulatif.",
    },
    "home.section_what_it_does": {
        "en": "What It Does",
        "ar": "ما الذي يقدّمه",
        "id": "Apa yang Dilakukannya",
    },
    "home.feature.transparent.title": {
        "en": "Transparent Matching",
        "ar": "مطابقة شفافة",
        "id": "Pencocokan Transparan",
    },
    "home.feature.transparent.body": {
        "en": "Every recommendation includes a plain-language explanation of why that journal fits — never a black-box score.",
        "ar": "تتضمن كل توصية شرحًا مبسّطًا لسبب ملاءمة تلك المجلة — وليست درجة مبهمة بلا تفسير.",
        "id": "Setiap rekomendasi disertai penjelasan sederhana mengapa jurnal tersebut cocok — bukan sekadar skor tanpa penjelasan.",
    },
    "home.feature.prestige.title": {
        "en": "Prestige-Aware",
        "ar": "واعٍ بالمكانة العلمية",
        "id": "Memperhatikan Prestise",
    },
    "home.feature.prestige.body": {
        "en": "Sort by Scopus / Web of Science quartile and SJR, not just topical match.",
        "ar": "الترتيب حسب ربعية Scopus / Web of Science ومؤشر SJR، وليس فقط التطابق الموضوعي.",
        "id": "Urutkan berdasarkan kuartil Scopus / Web of Science dan SJR, tidak hanya kecocokan topik.",
    },
    "home.feature.budget.title": {
        "en": "Budget-Aware",
        "ar": "واعٍ بالميزانية",
        "id": "Memperhatikan Anggaran",
    },
    "home.feature.budget.body": {
        "en": "Filter by APC, including free/no-fee journals — no guessed currency conversions.",
        "ar": "التصفية حسب رسوم النشر (APC)، بما في ذلك المجلات المجانية — دون تحويلات عملة تقديرية.",
        "id": "Saring berdasarkan APC, termasuk jurnal gratis/tanpa biaya — tanpa konversi mata uang perkiraan.",
    },
    "home.feature.multiindex.title": {
        "en": "Multi-Index Coverage",
        "ar": "تغطية متعددة الفهارس",
        "id": "Cakupan Multi-Indeks",
    },
    "home.feature.multiindex.body": {
        "en": "DOAJ, Scopus, Web of Science, and SINTA in one search, deduplicated into a single database.",
        "ar": "DOAJ وScopus وWeb of Science وSINTA في بحث واحد، مدمجة دون تكرار في قاعدة بيانات واحدة.",
        "id": "DOAJ, Scopus, Web of Science, dan SINTA dalam satu pencarian, digabung tanpa duplikasi ke dalam satu basis data.",
    },
    "home.feature.export.title": {
        "en": "Flexible Export",
        "ar": "تصدير مرن",
        "id": "Ekspor Fleksibel",
    },
    "home.feature.export.body": {
        "en": "Save results as PDF, DOCX, XLSX, Markdown, or CSV — including a format made for pasting into an AI assistant.",
        "ar": "احفظ النتائج بصيغة PDF أو DOCX أو XLSX أو Markdown أو CSV — بما في ذلك صيغة مخصّصة للصق في مساعد ذكاء اصطناعي.",
        "id": "Simpan hasil sebagai PDF, DOCX, XLSX, Markdown, atau CSV — termasuk format yang dirancang untuk ditempel ke asisten AI.",
    },
    "home.feature.fast.title": {
        "en": "Fast, Local Search",
        "ar": "بحث محلي سريع",
        "id": "Pencarian Lokal yang Cepat",
    },
    "home.feature.fast.body": {
        "en": "Every search runs against a local, indexed database — no external API calls or rate limits.",
        "ar": "يعمل كل بحث على قاعدة بيانات محلية مفهرسة — دون استدعاءات API خارجية أو حدود معدل الاستخدام.",
        "id": "Setiap pencarian berjalan pada basis data lokal yang terindeks — tanpa panggilan API eksternal atau batas kecepatan.",
    },
    "home.footer_line": {
        "en": "🔒 Privacy-first · No account required · Built for researchers",
        "ar": "🔒 خصوصية أولاً · لا حاجة لحساب · مصمَّم للباحثين",
        "id": "🔒 Mengutamakan privasi · Tanpa akun · Dibuat untuk peneliti",
    },

    "validation.abstract_too_short": {
        "en": "This abstract looks too short (at least {min_words} words) for Scilene to suggest relevant concepts. Please paste your full abstract.",
        "ar": "يبدو هذا الملخص قصيرًا جدًا (يلزم {min_words} كلمات على الأقل) ليتمكن Scilene من اقتراح مفاهيم ذات صلة. يرجى لصق الملخص كاملاً.",
        "id": "Abstrak ini tampaknya terlalu pendek (minimal {min_words} kata) agar Scilene dapat menyarankan konsep yang relevan. Mohon tempel abstrak lengkap Anda.",
    },
}


def t(key, locale, **kwargs):
    """
    Looks up `key` for `locale`, falling back to DEFAULT_LOCALE (or
    the raw key itself if genuinely missing) rather than raising --
    a missing translation must never break a page render. `**kwargs`
    fill a template's {placeholders}, e.g. t("home.sublabel_wos", "ar",
    count="1,234").
    """
    entry = _STRINGS.get(key)
    if not entry:
        return key

    template = entry.get(locale) or entry.get(DEFAULT_LOCALE) or key

    if not kwargs:
        return template

    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template
