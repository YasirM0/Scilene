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

    # -- About page (#129) --------------------------------------------
    "about.title": {"en": "About", "ar": "حول", "id": "Tentang"},
    "about.hero_title": {
        "en": "Navigate Scholarly Publishing with Confidence",
        "ar": "تصفّح النشر العلمي بثقة",
        "id": "Jelajahi Penerbitan Ilmiah dengan Percaya Diri",
    },
    "about.hero_description": {
        "en": "Scilene helps researchers find the right academic journals through transparent, explainable recommendations — and understand the thinking behind every one of them.",
        "ar": "يساعد Scilene الباحثين على إيجاد المجلات الأكاديمية المناسبة من خلال توصيات شفافة وقابلة للتفسير — مع فهم التفكير الكامن وراء كل توصية.",
        "id": "Scilene membantu peneliti menemukan jurnal akademik yang tepat melalui rekomendasi yang transparan dan dapat dijelaskan — serta memahami pemikiran di balik setiap rekomendasi.",
    },
    "about.section.what_is.title": {
        "en": "What is Scilene?",
        "ar": "ما هو Scilene؟",
        "id": "Apa itu Scilene?",
    },
    "about.section.what_is.body1": {
        "en": "Scilene is an open-source platform that helps researchers discover the right academic journals for their work — and understand why each one is recommended. Every match is backed by a transparent, plain-language explanation rather than an opaque score.",
        "ar": "Scilene منصة مفتوحة المصدر تساعد الباحثين على اكتشاف المجلات الأكاديمية المناسبة لعملهم — وفهم سبب التوصية بكل واحدة منها. كل تطابق مدعوم بشرح شفاف وواضح بدلاً من درجة مبهمة.",
        "id": "Scilene adalah platform sumber terbuka yang membantu peneliti menemukan jurnal akademik yang tepat untuk karya mereka — serta memahami mengapa setiap jurnal direkomendasikan. Setiap kecocokan didukung oleh penjelasan yang transparan dan mudah dipahami, bukan skor yang tidak jelas.",
    },
    "about.section.what_is.body2": {
        "en": "Long term, Scilene is growing beyond journal discovery into a broader research intelligence platform: a tool that helps researchers understand, interpret, and navigate the scholarly landscape, not just search it.",
        "ar": "على المدى الطويل، يتطور Scilene ليتجاوز اكتشاف المجلات نحو منصة أشمل لذكاء البحث العلمي: أداة تساعد الباحثين على فهم المشهد العلمي وتفسيره والتنقل فيه، لا مجرد البحث فيه.",
        "id": "Dalam jangka panjang, Scilene berkembang melampaui penemuan jurnal menjadi platform intelijen riset yang lebih luas: alat yang membantu peneliti memahami, menafsirkan, dan menavigasi lanskap ilmiah, bukan sekadar mencarinya.",
    },
    "about.section.why_created.title": {
        "en": "Why was Scilene created?",
        "ar": "لماذا تم إنشاء Scilene؟",
        "id": "Mengapa Scilene dibuat?",
    },
    "about.section.why_created.body": {
        "en": "Many existing journal finders return a ranked list without explaining their reasoning — relying on paid services or prestige-based scoring instead. Scilene was created as a transparent alternative: recommendations grounded in verifiable, publicly available scholarly metadata, with every match paired with a plain-language explanation of why it's there.",
        "ar": "تعيد العديد من أدوات البحث عن المجلات الحالية قائمة مرتبة دون شرح منطقها — معتمدة بدلاً من ذلك على خدمات مدفوعة أو تقييم قائم على المكانة العلمية. أُنشئ Scilene كبديل شفاف: توصيات مبنية على بيانات علمية يمكن التحقق منها ومتاحة للعموم، مع شرح واضح لكل تطابق يبيّن سبب ظهوره.",
        "id": "Banyak alat pencari jurnal yang ada mengembalikan daftar peringkat tanpa menjelaskan alasannya — mengandalkan layanan berbayar atau penilaian berbasis prestise. Scilene dibuat sebagai alternatif yang transparan: rekomendasi didasarkan pada metadata ilmiah yang dapat diverifikasi dan tersedia untuk umum, dengan setiap kecocokan disertai penjelasan sederhana mengapa jurnal itu muncul.",
    },
    "about.section.name.title": {
        "en": 'Why the name "Scilene"?',
        "ar": '‏لماذا اسم "Scilene"؟',
        "id": 'Mengapa nama "Scilene"?',
    },
    "about.section.name.body1": {
        "en": "Scilene combines {sci}, for science, with {selene}, the Greek personification of the moon.",
        "ar": "يجمع اسم Scilene بين {sci}، إشارة إلى العلم (Science)، و{selene}، تجسيد القمر في الأساطير اليونانية.",
        "id": "Scilene menggabungkan {sci}, untuk sains (science), dengan {selene}, personifikasi bulan dalam mitologi Yunani.",
    },
    "about.section.name.body2": {
        "en": "The moon has long served as a natural guide for navigation and exploration. In the same way, Scilene aims to guide researchers through an increasingly complex scholarly landscape toward the right journals, literature, and decisions — guidance through science, rather than just a search over it.",
        "ar": "لطالما كان القمر دليلاً طبيعياً للملاحة والاستكشاف. وبالمثل، يهدف Scilene إلى إرشاد الباحثين عبر مشهد علمي متزايد التعقيد نحو المجلات والأدبيات والقرارات الصحيحة — إرشاد من خلال العلم، لا مجرد بحث فيه.",
        "id": "Bulan telah lama menjadi penunjuk alami untuk navigasi dan eksplorasi. Dengan cara yang sama, Scilene bertujuan memandu peneliti melewati lanskap ilmiah yang semakin kompleks menuju jurnal, literatur, dan keputusan yang tepat — panduan melalui sains, bukan sekadar pencarian di dalamnya.",
    },
    "about.section.logo.title": {
        "en": "What does the logo represent?",
        "ar": "ماذا يمثل الشعار؟",
        "id": "Apa makna logonya?",
    },
    "about.section.logo.body": {
        "en": 'The mark is the letter "S," traced by a subtle, abstract crescent meant to suggest an orbit or research journey — only a very quiet nod to Selene, not a literal moon. Above it, a small gold star stands in for a guiding star: discovery, direction, and confidence.',
        "ar": 'الرمز هو حرف "S"، يحيط به هلال تجريدي خفيف يوحي بمدار أو رحلة بحثية — إشارة هادئة جداً إلى سيلين، وليست قمراً حرفياً. وفوقه، نجمة ذهبية صغيرة ترمز إلى نجم هادٍ: الاكتشاف والاتجاه والثقة.',
        "id": 'Lambangnya adalah huruf "S," dilingkupi bulan sabit abstrak yang halus, menyiratkan orbit atau perjalanan riset — hanya isyarat lembut terhadap Selene, bukan bulan secara harfiah. Di atasnya, sebuah bintang emas kecil melambangkan bintang penuntun: penemuan, arah, dan kepercayaan diri.',
    },
    "about.color.navy": {
        "en": "Navy — night sky, trust, academic credibility",
        "ar": "الكحلي — سماء الليل، الثقة، المصداقية الأكاديمية",
        "id": "Navy — langit malam, kepercayaan, kredibilitas akademik",
    },
    "about.color.gold": {
        "en": "Gold — discovery, insight, progress",
        "ar": "الذهبي — الاكتشاف، البصيرة، التقدم",
        "id": "Emas — penemuan, wawasan, kemajuan",
    },
    "about.section.offline.title": {
        "en": "Why offline-first?",
        "ar": "لماذا العمل دون اتصال أولاً؟",
        "id": "Mengapa offline-first?",
    },
    "about.section.offline.body": {
        "en": "Scilene's core recommendation engine is designed to work without depending on external APIs or an internet connection. Optional AI-assisted features may be added later, but they will never become mandatory for getting a recommendation.",
        "ar": "صُمم محرك التوصيات الأساسي في Scilene للعمل دون الاعتماد على واجهات برمجة خارجية أو اتصال بالإنترنت. قد تُضاف لاحقاً ميزات اختيارية مدعومة بالذكاء الاصطناعي، لكنها لن تصبح أبداً شرطاً للحصول على توصية.",
        "id": "Mesin rekomendasi inti Scilene dirancang untuk bekerja tanpa bergantung pada API eksternal atau koneksi internet. Fitur berbasis AI yang bersifat opsional mungkin ditambahkan di kemudian hari, tetapi tidak akan pernah menjadi wajib untuk mendapatkan rekomendasi.",
    },
    "about.section.offline.callout": {
        "en": "In practice: the same search returns the same results whether you're at a conference with no signal or at your desk — no service outage ever blocks a recommendation.",
        "ar": "من الناحية العملية: يعطي البحث نفسه النتائج نفسها سواء كنت في مؤتمر بلا إشارة أو على مكتبك — لا يعطل انقطاع أي خدمة توصيةً أبداً.",
        "id": "Dalam praktiknya: pencarian yang sama menghasilkan hasil yang sama baik Anda berada di konferensi tanpa sinyal maupun di meja kerja — gangguan layanan apa pun tidak pernah menghalangi rekomendasi.",
    },
    "about.section.ai_optional.title": {
        "en": "Why is AI optional?",
        "ar": "لماذا الذكاء الاصطناعي اختياري؟",
        "id": "Mengapa AI bersifat opsional?",
    },
    "about.section.ai_optional.body": {
        "en": "Scilene's recommendations come from a deterministic, explainable ranking engine, not a black box. Where AI is introduced, it's meant to enrich and assist that process, never to replace it.",
        "ar": "تنبثق توصيات Scilene من محرك ترتيب حتمي وقابل للتفسير، وليس صندوقاً أسود. وحيثما يُستخدم الذكاء الاصطناعي، فالغرض منه إثراء هذه العملية ومساعدتها، لا استبدالها.",
        "id": "Rekomendasi Scilene berasal dari mesin peringkat yang deterministik dan dapat dijelaskan, bukan kotak hitam. Jika AI digunakan, tujuannya adalah memperkaya dan membantu proses tersebut, bukan menggantikannya.",
    },
    "about.section.ai_optional.callout": {
        "en": "In practice: turning AI features off never changes which journals get recommended — only how much help you get finding the right words to search with.",
        "ar": "من الناحية العملية: إيقاف ميزات الذكاء الاصطناعي لا يغيّر أبداً المجلات التي تتم التوصية بها — بل يؤثر فقط في مقدار المساعدة التي تحصل عليها لإيجاد الكلمات المناسبة للبحث.",
        "id": "Dalam praktiknya: menonaktifkan fitur AI tidak pernah mengubah jurnal mana yang direkomendasikan — hanya memengaruhi seberapa banyak bantuan yang Anda dapatkan untuk menemukan kata yang tepat untuk pencarian.",
    },
    "about.section.open_source.title": {
        "en": "Why open source?",
        "ar": "لماذا مفتوح المصدر؟",
        "id": "Mengapa sumber terbuka?",
    },
    "about.section.open_source.body1": {
        "en": "Scilene is developed in the open so that anyone can inspect how recommendations are produced, suggest improvements, or contribute new features.",
        "ar": "يُطوَّر Scilene بشكل علني بحيث يمكن لأي شخص فحص كيفية إنتاج التوصيات، أو اقتراح تحسينات، أو المساهمة بميزات جديدة.",
        "id": "Scilene dikembangkan secara terbuka sehingga siapa pun dapat memeriksa bagaimana rekomendasi dihasilkan, mengusulkan perbaikan, atau berkontribusi dengan fitur baru.",
    },
    "about.section.open_source.body2": {
        "en": "Transparency in code is the same principle as transparency in recommendations — nothing about how Scilene works should be hidden from the researchers who rely on it.",
        "ar": "الشفافية في الكود هي نفس مبدأ الشفافية في التوصيات — لا ينبغي أن يظل أي جانب من عمل Scilene خفياً عن الباحثين الذين يعتمدون عليه.",
        "id": "Transparansi dalam kode mengikuti prinsip yang sama dengan transparansi dalam rekomendasi — tidak ada bagian dari cara kerja Scilene yang seharusnya disembunyikan dari peneliti yang mengandalkannya.",
    },
    "about.section.vision.title": {
        "en": "Our vision",
        "ar": "رؤيتنا",
        "id": "Visi kami",
    },
    "about.section.vision.body1": {
        "en": "Scilene aims to become a trusted, open-source reference tool for journal selection — and, over time, a broader research intelligence platform that helps researchers navigate scholarly publishing with confidence.",
        "ar": "يهدف Scilene إلى أن يصبح أداة مرجعية موثوقة ومفتوحة المصدر لاختيار المجلات — وأن يتطور مع الوقت إلى منصة أشمل لذكاء البحث العلمي تساعد الباحثين على تصفّح النشر العلمي بثقة.",
        "id": "Scilene bertujuan menjadi alat referensi tepercaya dan sumber terbuka untuk pemilihan jurnal — dan, seiring waktu, berkembang menjadi platform intelijen riset yang lebih luas yang membantu peneliti menavigasi penerbitan ilmiah dengan percaya diri.",
    },
    "about.section.vision.body2": {
        "en": "Every new feature is measured against the same question: does this make Scilene more transparent, more understandable, or more useful to a researcher deciding where to submit their work?",
        "ar": "تُقاس كل ميزة جديدة بالسؤال نفسه: هل يجعل هذا Scilene أكثر شفافية، أو أسهل فهماً، أو أكثر فائدة لباحث يقرر أين يرسل عمله؟",
        "id": "Setiap fitur baru diukur dengan pertanyaan yang sama: apakah ini membuat Scilene lebih transparan, lebih mudah dipahami, atau lebih bermanfaat bagi peneliti yang memutuskan ke mana harus mengirimkan karyanya?",
    },

    # -- Journal card (#129) -------------------------------------------
    "journal_card.scopus_coverage": {"en": "Scopus coverage: {coverage}", "ar": "تغطية Scopus: {coverage}", "id": "Cakupan Scopus: {coverage}"},
    "journal_card.indexed_since": {"en": "Indexed in Scopus since {date}", "ar": "مفهرسة في Scopus منذ {date}", "id": "Terindeks di Scopus sejak {date}"},
    "journal_card.also_listed_in": {"en": "Also listed in: {badges}", "ar": "مدرجة أيضاً في: {badges}", "id": "Juga terdaftar di: {badges}"},
    "journal_card.country": {"en": "Country", "ar": "الدولة", "id": "Negara"},
    "journal_card.language": {"en": "Language", "ar": "اللغة", "id": "Bahasa"},
    "journal_card.apc": {"en": "APC", "ar": "رسوم النشر (APC)", "id": "APC"},
    "journal_card.free": {"en": "Free", "ar": "مجانية", "id": "Gratis"},
    "journal_card.paid_unconfirmed": {"en": "Paid (unconfirmed)", "ar": "مدفوعة (غير مؤكدة)", "id": "Berbayar (belum dikonfirmasi)"},
    "journal_card.compare": {"en": "Compare", "ar": "مقارنة", "id": "Bandingkan"},
    "journal_card.show_more": {"en": "Show more", "ar": "عرض المزيد", "id": "Tampilkan lebih banyak"},
    "journal_card.publisher": {"en": "Publisher:", "ar": "الناشر:", "id": "Penerbit:"},
    "journal_card.not_listed": {"en": "Not listed", "ar": "غير مُدرج", "id": "Tidak tercantum"},
    "journal_card.subjects": {"en": "Subjects:", "ar": "المواضيع:", "id": "Subjek:"},
    "journal_card.review_time": {"en": "Typical review time:", "ar": "مدة المراجعة المعتادة:", "id": "Waktu tinjauan biasa:"},
    "journal_card.weeks": {"en": "weeks", "ar": "أسابيع", "id": "minggu"},
    "journal_card.issn": {"en": "ISSN: {print} (print) / {online} (online)", "ar": "الترقيم الدولي: {print} (مطبوع) / {online} (إلكتروني)", "id": "ISSN: {print} (cetak) / {online} (daring)"},
    "journal_card.license": {"en": "License: {license}", "ar": "الترخيص: {license}", "id": "Lisensi: {license}"},
    "journal_card.visit_journal": {"en": "Visit Journal ↗", "ar": "زيارة المجلة ↗", "id": "Kunjungi Jurnal ↗"},
    "journal_card.view_on_doaj": {"en": "View on DOAJ ↗", "ar": "عرض على DOAJ ↗", "id": "Lihat di DOAJ ↗"},
    "journal_card.get_more_info": {"en": "Get more info online (OpenAlex / Crossref)", "ar": "مزيد من المعلومات عبر الإنترنت (OpenAlex / Crossref)", "id": "Info lebih lanjut secara daring (OpenAlex / Crossref)"},

    # -- Compare page (#129) --------------------------------------------
    "compare.title": {"en": "Compare Journals", "ar": "مقارنة المجلات", "id": "Bandingkan Jurnal"},
    "compare.subtitle": {
        "en": "Side-by-side comparison of your selected journals to support an informed submission decision.",
        "ar": "مقارنة جنباً إلى جنب للمجلات التي اخترتها لدعم قرار إرسال مدروس.",
        "id": "Perbandingan berdampingan untuk jurnal yang Anda pilih guna mendukung keputusan pengiriman yang tepat.",
    },
    "compare.empty_state": {
        "en": "No journals selected yet. Go to {search_link} and tick \"Compare\" on up to 4 journal cards.",
        "ar": "لم يتم اختيار أي مجلات بعد. اذهب إلى {search_link} وفعّل خيار \"مقارنة\" على ما يصل إلى 4 بطاقات مجلات.",
        "id": "Belum ada jurnal yang dipilih. Buka {search_link} lalu centang \"Bandingkan\" pada hingga 4 kartu jurnal.",
    },
    "compare.link_search": {"en": "Search", "ar": "البحث", "id": "Pencarian"},
    "compare.row.recommendation": {"en": "Recommendation", "ar": "التوصية", "id": "Rekomendasi"},
    "compare.cell.not_in_results": {"en": "Not in your current search results", "ar": "غير موجودة في نتائج بحثك الحالية", "id": "Tidak ada dalam hasil pencarian Anda saat ini"},
    "compare.row.publisher": {"en": "Publisher", "ar": "الناشر", "id": "Penerbit"},
    "compare.row.country": {"en": "Country", "ar": "الدولة", "id": "Negara"},
    "compare.row.subjects": {"en": "Subject Areas", "ar": "المجالات الموضوعية", "id": "Bidang Subjek"},
    "compare.row.indexing": {"en": "Indexing", "ar": "الفهرسة", "id": "Pengindeksan"},
    "compare.row.metrics": {"en": "Metrics (SJR / H-index)", "ar": "المقاييس (SJR / H-index)", "id": "Metrik (SJR / H-index)"},
    "compare.row.open_access": {"en": "Open Access / APC", "ar": "الوصول المفتوح / رسوم النشر", "id": "Akses Terbuka / APC"},
    "compare.cell.free": {"en": "Free (No APC)", "ar": "مجانية (بلا رسوم نشر)", "id": "Gratis (Tanpa APC)"},
    "compare.cell.paid_unconfirmed": {"en": "Paid (unconfirmed)", "ar": "مدفوعة (غير مؤكدة)", "id": "Berbayar (belum dikonfirmasi)"},
    "compare.row.languages": {"en": "Language(s)", "ar": "اللغة (اللغات)", "id": "Bahasa"},
    "compare.row.review_time": {"en": "Typical Review Time", "ar": "مدة المراجعة المعتادة", "id": "Waktu Tinjauan Biasa"},
    "compare.unit.weeks": {"en": "weeks", "ar": "أسابيع", "id": "minggu"},
    "compare.row.issn": {"en": "ISSN", "ar": "الترقيم الدولي (ISSN)", "id": "ISSN"},
    "compare.button.clear": {"en": "Clear comparison", "ar": "مسح المقارنة", "id": "Hapus perbandingan"},

    # -- Statistics dashboard (#129) -------------------------------------
    "statistics.title": {"en": "Statistics", "ar": "الإحصائيات", "id": "Statistik"},
    "statistics.heading": {"en": "Statistics Dashboard", "ar": "لوحة الإحصائيات", "id": "Dasbor Statistik"},
    "statistics.subtitle": {
        "en": "A snapshot of the journal database and recommendation engine's coverage.",
        "ar": "لمحة عن قاعدة بيانات المجلات ونطاق تغطية محرك التوصيات.",
        "id": "Gambaran singkat basis data jurnal dan cakupan mesin rekomendasi.",
    },
    "statistics.empty": {
        "en": "Statistics are unavailable right now — the database couldn't be reached.",
        "ar": "الإحصائيات غير متاحة حالياً — تعذّر الوصول إلى قاعدة البيانات.",
        "id": "Statistik saat ini tidak tersedia — basis data tidak dapat dijangkau.",
    },
    "statistics.stat.total_journals": {"en": "Total Journals", "ar": "إجمالي المجلات", "id": "Total Jurnal"},
    "statistics.chart.indexing_sources": {"en": "Indexing Sources", "ar": "مصادر الفهرسة", "id": "Sumber Pengindeksan"},
    "statistics.chart.metadata_enrichment": {"en": "Metadata Enrichment", "ar": "إثراء البيانات الوصفية", "id": "Pengayaan Metadata"},
    "statistics.chart.top_countries": {"en": "Top Countries", "ar": "أبرز الدول", "id": "Negara Teratas"},
    "statistics.chart.top_publishers": {"en": "Top Publishers", "ar": "أبرز الناشرين", "id": "Penerbit Teratas"},
    "statistics.chart.top_subjects": {"en": "Top Subject Areas", "ar": "أبرز المجالات الموضوعية", "id": "Bidang Subjek Teratas"},
    "statistics.chart.publication_type": {"en": "Publication Type", "ar": "نوع النشر", "id": "Jenis Publikasi"},
    "statistics.chart.quartile": {"en": "Scopus / WoS Quartile", "ar": "ربعية Scopus / WoS", "id": "Kuartil Scopus / WoS"},
    "statistics.chart.sinta_accreditation": {"en": "SINTA Accreditation", "ar": "اعتماد SINTA", "id": "Akreditasi SINTA"},
    "statistics.chart.open_access_cost": {"en": "Open Access Cost", "ar": "تكلفة الوصول المفتوح", "id": "Biaya Akses Terbuka"},
    "statistics.footnote": {
        "en": "\"Top\" lists are capped at the 10 largest categories. Publication Type only reflects journals matched to the Elsevier Source List (#128) — unmatched journals aren't counted here as a guess either way.",
        "ar": 'قوائم "الأبرز" مقتصرة على أكبر 10 فئات. يعكس "نوع النشر" فقط المجلات المطابقة لقائمة مصادر Elsevier (#128) — لا تُحتسب المجلات غير المطابقة هنا كتخمين في أي اتجاه.',
        "id": 'Daftar "teratas" dibatasi pada 10 kategori terbesar. Jenis Publikasi hanya mencerminkan jurnal yang cocok dengan Elsevier Source List (#128) — jurnal yang tidak cocok tidak dihitung di sini sebagai tebakan ke arah mana pun.',
    },
    "bar_list.no_data": {"en": "No data available.", "ar": "لا توجد بيانات متاحة.", "id": "Tidak ada data yang tersedia."},

    # -- Submission Search page (#129) -----------------------------------
    "search.title": {"en": "Submission Search", "ar": "بحث الإرسال", "id": "Pencarian Naskah"},
    "search.heading": {"en": "Journal Search", "ar": "بحث المجلات", "id": "Pencarian Jurnal"},
    "search.subtitle": {
        "en": "Enter your manuscript information to discover journals that best match your research.",
        "ar": "أدخل معلومات مخطوطتك لاكتشاف المجلات الأنسب لبحثك.",
        "id": "Masukkan informasi naskah Anda untuk menemukan jurnal yang paling sesuai dengan penelitian Anda.",
    },
    "search.load_session_summary": {"en": "Load a saved session (.sls)", "ar": "تحميل جلسة محفوظة (.sls)", "id": "Muat sesi tersimpan (.sls)"},
    "search.load_session_button": {"en": "Load session", "ar": "تحميل الجلسة", "id": "Muat sesi"},
    "search.load_session_helper": {
        "en": "Re-runs the saved search live against the current database — recommendations are always regenerated, never replayed from the file.",
        "ar": "يعيد تشغيل البحث المحفوظ مباشرة على قاعدة البيانات الحالية — تُعاد التوصيات دائماً من جديد، ولا تُستعاد من الملف كما هي.",
        "id": "Menjalankan ulang pencarian tersimpan secara langsung terhadap basis data saat ini — rekomendasi selalu dibuat ulang, tidak pernah diputar ulang dari file.",
    },
    "search.find_button": {"en": "Find Best Matching Journals", "ar": "ابحث عن أفضل المجلات المطابقة", "id": "Temukan Jurnal yang Paling Cocok"},

    # -- Search form (#129) -----------------------------------------------
    "search_form.heading": {"en": "Describe Your Research", "ar": "صف بحثك", "id": "Jelaskan Riset Anda"},
    "search_form.abstract_label": {"en": "Abstract", "ar": "الملخص", "id": "Abstrak"},
    "search_form.abstract_placeholder": {
        "en": "Paste your manuscript abstract here...",
        "ar": "الصق ملخص مخطوطتك هنا...",
        "id": "Tempel abstrak naskah Anda di sini...",
    },
    "search_form.abstract_helper": {
        "en": "Scilene will suggest a field of study and a key research focus from your abstract.",
        "ar": "سيقترح Scilene مجال دراسة وتركيزاً بحثياً رئيسياً بناءً على ملخصك.",
        "id": "Scilene akan menyarankan bidang studi dan fokus riset utama dari abstrak Anda.",
    },
    "search_form.fallback_summary": {
        "en": "Don't have an abstract? Add at least 10 descriptive tags instead",
        "ar": "ليس لديك ملخص؟ أضف بدلاً منه 10 وسوم وصفية على الأقل",
        "id": "Tidak punya abstrak? Tambahkan setidaknya 10 tag deskriptif sebagai gantinya",
    },
    "search_form.fallback_placeholder": {
        "en": "digital governance, e-government, Indonesia, public administration, ...",
        "ar": "الحوكمة الرقمية، الحكومة الإلكترونية، إندونيسيا، الإدارة العامة، ...",
        "id": "tata kelola digital, e-government, Indonesia, administrasi publik, ...",
    },
    "search_form.fallback_helper": {
        "en": "Separate tags with commas or semicolons — at least 10 if you're not providing an abstract.",
        "ar": "افصل الوسوم بفواصل أو فواصل منقوطة — 10 على الأقل إذا لم تقدّم ملخصاً.",
        "id": "Pisahkan tag dengan koma atau titik koma — minimal 10 jika Anda tidak menyertakan abstrak.",
    },
    "search_form.concepts_label": {"en": "Search Concepts", "ar": "مفاهيم البحث", "id": "Konsep Pencarian"},

    # -- Filter panel (#129) ------------------------------------------------
    "filter.summary": {"en": "Publication Preferences", "ar": "تفضيلات النشر", "id": "Preferensi Publikasi"},
    "filter.search_settings": {"en": "Search Settings", "ar": "إعدادات البحث", "id": "Pengaturan Pencarian"},
    "filter.strategy_label": {"en": "Recommendation Strategy", "ar": "استراتيجية التوصية", "id": "Strategi Rekomendasi"},
    "filter.budget_label": {"en": "Publication Budget", "ar": "ميزانية النشر", "id": "Anggaran Publikasi"},
    "filter.review_time_label": {"en": "Maximum Review Time", "ar": "الحد الأقصى لمدة المراجعة", "id": "Waktu Tinjauan Maksimum"},
    "filter.group_label": {"en": "Filter by Index, Quality & Language", "ar": "التصفية حسب الفهرس والجودة واللغة", "id": "Saring berdasarkan Indeks, Kualitas & Bahasa"},
    "filter.preferred_indexing": {"en": "Preferred Indexing", "ar": "الفهرسة المفضلة", "id": "Pengindeksan Pilihan"},
    "filter.quartile": {"en": "Scopus / WoS Quartile", "ar": "ربعية Scopus / WoS", "id": "Kuartil Scopus / WoS"},
    "filter.sinta_level": {"en": "SINTA Level", "ar": "مستوى SINTA", "id": "Tingkat SINTA"},

    # Canonical option display text -- keyed by the exact English string
    # (also the literal form value/dict key used on the Python side, e.g.
    # web/search_presentation.py's STRATEGY_LABELS/BUDGET_OPTIONS/
    # REVIEW_TIME_BANDS) so translating the label never touches the
    # value the backend actually matches against.
    "filter_option.⚖️ Balanced (Recommended)": {"en": "⚖️ Balanced (Recommended)", "ar": "⚖️ متوازن (موصى به)", "id": "⚖️ Seimbang (Direkomendasikan)"},
    "filter_option.💰 Lowest APC": {"en": "💰 Lowest APC", "ar": "💰 أقل رسوم نشر", "id": "💰 APC Terendah"},
    "filter_option.🏆 Highest Prestige": {"en": "🏆 Highest Prestige", "ar": "🏆 أعلى مكانة علمية", "id": "🏆 Prestise Tertinggi"},
    "filter_option.Any": {"en": "Any", "ar": "أي", "id": "Semua"},
    "filter_option.Free (No APC)": {"en": "Free (No APC)", "ar": "مجانية (بلا رسوم نشر)", "id": "Gratis (Tanpa APC)"},
    "filter_option.Low APC (< $100)": {"en": "Low APC (< $100)", "ar": "رسوم نشر منخفضة (أقل من 100$)", "id": "APC Rendah (< $100)"},
    "filter_option.Medium APC ($100–300)": {"en": "Medium APC ($100–300)", "ar": "رسوم نشر متوسطة (100–300$)", "id": "APC Sedang ($100–300)"},
    "filter_option.High APC (> $300)": {"en": "High APC (> $300)", "ar": "رسوم نشر مرتفعة (أكثر من 300$)", "id": "APC Tinggi (> $300)"},
    "filter_option.Up to 8 weeks": {"en": "Up to 8 weeks", "ar": "حتى 8 أسابيع", "id": "Hingga 8 minggu"},
    "filter_option.Up to 12 weeks": {"en": "Up to 12 weeks", "ar": "حتى 12 أسبوعاً", "id": "Hingga 12 minggu"},
    "filter_option.Up to 20 weeks": {"en": "Up to 20 weeks", "ar": "حتى 20 أسبوعاً", "id": "Hingga 20 minggu"},
    "filter_option.Up to 30 weeks": {"en": "Up to 30 weeks", "ar": "حتى 30 أسبوعاً", "id": "Hingga 30 minggu"},
    "filter_option.English": {"en": "English", "ar": "الإنجليزية", "id": "Inggris"},
    "filter_option.Arabic": {"en": "Arabic", "ar": "العربية", "id": "Arab"},
    "filter_option.Indonesian": {"en": "Indonesian", "ar": "الإندونيسية", "id": "Indonesia"},

    "multi_select.selected_count": {"en": "{selected}/{total} selected", "ar": "{selected}/{total} محدد", "id": "{selected}/{total} dipilih"},

    "language_filter.label": {"en": "Journal Languages", "ar": "لغات المجلة", "id": "Bahasa Jurnal"},
    "language_filter.detected_hint": {
        "en": "✓ Detected {language} from your manuscript. Select additional journal languages to broaden your search.",
        "ar": "✓ تم اكتشاف {language} من مخطوطتك. اختر لغات مجلات إضافية لتوسيع نطاق بحثك.",
        "id": "✓ Terdeteksi {language} dari naskah Anda. Pilih bahasa jurnal tambahan untuk memperluas pencarian Anda.",
    },

    # -- Research Interpreter panel (#129) ---------------------------------
    "interpreter.analyzing": {"en": "Analyzing your abstract...", "ar": "جارٍ تحليل ملخصك...", "id": "Menganalisis abstrak Anda..."},
    "interpreter.field_identified": {"en": "✓ Field of Study identified", "ar": "✓ تم تحديد مجال الدراسة", "id": "✓ Bidang studi teridentifikasi"},
    "interpreter.focus_identified": {"en": "✓ Key Research Focus identified", "ar": "✓ تم تحديد التركيز البحثي الرئيسي", "id": "✓ Fokus riset utama teridentifikasi"},
    "interpreter.changed_notice": {"en": "Your abstract has changed.", "ar": "لقد تغيّر ملخصك.", "id": "Abstrak Anda telah berubah."},
    "interpreter.refresh_button": {"en": "↻ Refresh suggested tags", "ar": "↻ تحديث الوسوم المقترحة", "id": "↻ Segarkan tag yang disarankan"},
    "interpreter.keep_button": {"en": "Keep current tags", "ar": "الاحتفاظ بالوسوم الحالية", "id": "Pertahankan tag saat ini"},
    "interpreter.suggested_by": {"en": "Suggested by Scilene", "ar": "اقتراح من Scilene", "id": "Disarankan oleh Scilene"},
    "interpreter.save": {"en": "Save", "ar": "حفظ", "id": "Simpan"},
    "interpreter.cancel": {"en": "Cancel", "ar": "إلغاء", "id": "Batal"},
    "interpreter.accept_aria": {"en": "Accept {value}", "ar": "قبول {value}", "id": "Terima {value}"},
    "interpreter.suggest_another_aria": {"en": "Suggest another for {label}", "ar": "اقترح بديلاً لـ {label}", "id": "Sarankan yang lain untuk {label}"},
    "interpreter.edit_aria": {"en": "Edit {label}", "ar": "تعديل {label}", "id": "Ubah {label}"},
    "interpreter.remove_aria": {"en": "Remove {label} suggestion", "ar": "إزالة اقتراح {label}", "id": "Hapus saran {label}"},
    "interpreter.category.field_of_study": {"en": "Field of Study", "ar": "مجال الدراسة", "id": "Bidang Studi"},
    "interpreter.category.key_focus": {"en": "Key Research Focus", "ar": "التركيز البحثي الرئيسي", "id": "Fokus Riset Utama"},

    # -- Confirmed tags (#129) ---------------------------------------------
    "confirmed_tags.badge_user": {"en": "USER", "ar": "المستخدم", "id": "PENGGUNA"},
    "confirmed_tags.badge_ai": {"en": "AI", "ar": "ذكاء اصطناعي", "id": "AI"},
    "confirmed_tags.remove_aria": {"en": "Remove {value}", "ar": "إزالة {value}", "id": "Hapus {value}"},
    "confirmed_tags.empty": {
        "en": "No concepts confirmed yet — accept a suggestion below or add your own tags.",
        "ar": "لم يتم تأكيد أي مفاهيم بعد — اقبل اقتراحاً أدناه أو أضف وسومك الخاصة.",
        "id": "Belum ada konsep yang dikonfirmasi — terima saran di bawah atau tambahkan tag Anda sendiri.",
    },
    "add_tag.placeholder": {"en": "Add a tag...", "ar": "أضف وسماً...", "id": "Tambahkan tag..."},

    # -- Export panel (#129) -------------------------------------------------
    "export.heading": {"en": "Export Results", "ar": "تصدير النتائج", "id": "Ekspor Hasil"},
    "export.helper": {
        "en": "Markdown is the best choice for pasting into an AI assistant like ChatGPT or Claude.",
        "ar": "صيغة Markdown هي الأفضل للصق في مساعد ذكاء اصطناعي مثل ChatGPT أو Claude.",
        "id": "Markdown adalah pilihan terbaik untuk ditempel ke asisten AI seperti ChatGPT atau Claude.",
    },
    "export.pdf": {"en": "PDF", "ar": "PDF", "id": "PDF"},
    "export.docx": {"en": "DOCX", "ar": "DOCX", "id": "DOCX"},
    "export.markdown": {"en": "Markdown", "ar": "Markdown", "id": "Markdown"},
    "export.more": {"en": "More", "ar": "المزيد", "id": "Lainnya"},
    "export.xlsx": {"en": "XLSX", "ar": "XLSX", "id": "XLSX"},
    "export.csv": {"en": "CSV", "ar": "CSV", "id": "CSV"},
    "export.save_session": {"en": "Save Session (.sls)", "ar": "حفظ الجلسة (.sls)", "id": "Simpan Sesi (.sls)"},
    "export.save_session_title": {
        "en": "Portable Search Session — reopen on another device via \"Load a saved session\"",
        "ar": "جلسة بحث محمولة — أعد فتحها على جهاز آخر عبر \"تحميل جلسة محفوظة\"",
        "id": "Sesi Pencarian Portabel — buka kembali di perangkat lain melalui \"Muat sesi tersimpan\"",
    },

    # -- Search results (#129) -----------------------------------------------
    "search_results.showing": {
        "en": "Showing {visible} of {total} recommended journals.",
        "ar": "عرض {visible} من أصل {total} مجلة موصى بها.",
        "id": "Menampilkan {visible} dari {total} jurnal yang direkomendasikan.",
    },
    "search_results.hidden_matches": {
        "en": "{count} weaker matches hidden — tick the box below to see them.",
        "ar": "تم إخفاء {count} تطابقات أضعف — فعّل المربع أدناه لعرضها.",
        "id": "{count} kecocokan yang lebih lemah disembunyikan — centang kotak di bawah untuk melihatnya.",
    },
    "search_results.clear_button": {"en": "Clear Search", "ar": "مسح البحث", "id": "Hapus Pencarian"},
    "search_results.show_weaker": {
        "en": "Show weaker matches too (Moderate / Weak / Poor)",
        "ar": "إظهار التطابقات الأضعف أيضاً (متوسط / ضعيف / سيئ)",
        "id": "Tampilkan juga kecocokan yang lebih lemah (Sedang / Lemah / Buruk)",
    },
    "search_results.detected_areas_label": {"en": "Detected Research Areas", "ar": "المجالات البحثية المكتشفة", "id": "Bidang Riset Terdeteksi"},
    "search_results.extra_discipline_placeholder": {
        "en": "Add a missing research area...",
        "ar": "أضف مجالاً بحثياً مفقوداً...",
        "id": "Tambahkan bidang riset yang belum ada...",
    },
    "search_results.refine_button": {
        "en": "✓ Refine recommendations with selected areas",
        "ar": "✓ تحسين التوصيات بالمجالات المحددة",
        "id": "✓ Sempurnakan rekomendasi dengan bidang yang dipilih",
    },
    "search_results.detected_areas_helper": {
        "en": "Detected areas are based on subject tags shared by your top matches — not generated by AI. Add your own if something's missing; nothing here is applied without your confirmation.",
        "ar": "تعتمد المجالات المكتشفة على وسوم المواضيع المشتركة بين أفضل تطابقاتك — وليست من إنتاج الذكاء الاصطناعي. أضف مجالك الخاص إذا كان هناك شيء مفقود؛ لا يُطبَّق أي شيء هنا دون تأكيدك.",
        "id": "Bidang yang terdeteksi didasarkan pada tag subjek yang sama di antara kecocokan teratas Anda — bukan dihasilkan oleh AI. Tambahkan sendiri jika ada yang kurang; tidak ada yang diterapkan di sini tanpa konfirmasi Anda.",
    },
    "search_results.privacy_footer": {
        "en": "🔒 Search results are stored only for this browser session and are never saved permanently.",
        "ar": "🔒 تُحفظ نتائج البحث فقط لجلسة المتصفح هذه ولا تُحفظ بشكل دائم أبداً.",
        "id": "🔒 Hasil pencarian hanya disimpan untuk sesi browser ini dan tidak pernah disimpan secara permanen.",
    },
    "search_results.data_label": {"en": "Data:", "ar": "البيانات:", "id": "Data:"},

    # -- Online enrichment (#129) --------------------------------------------
    "online_enrichment.source_note": {
        "en": "Additional metadata via {source} — informational only, not part of the recommendation.",
        "ar": "بيانات وصفية إضافية عبر {source} — لأغراض معلوماتية فقط، وليست جزءاً من التوصية.",
        "id": "Metadata tambahan melalui {source} — hanya bersifat informatif, bukan bagian dari rekomendasi.",
    },
    "online_enrichment.publisher": {"en": "Publisher:", "ar": "الناشر:", "id": "Penerbit:"},
    "online_enrichment.open_access": {"en": "Open Access:", "ar": "الوصول المفتوح:", "id": "Akses Terbuka:"},
    "online_enrichment.yes": {"en": "Yes", "ar": "نعم", "id": "Ya"},
    "online_enrichment.no": {"en": "No", "ar": "لا", "id": "Tidak"},
    "online_enrichment.apc": {"en": "APC:", "ar": "رسوم النشر (APC):", "id": "APC:"},
    "online_enrichment.topics": {"en": "Topics:", "ar": "المواضيع:", "id": "Topik:"},
    "online_enrichment.indexed_works": {"en": "Indexed works:", "ar": "الأعمال المفهرسة:", "id": "Karya terindeks:"},
    "online_enrichment.citations": {"en": "Citations:", "ar": "الاستشهادات:", "id": "Sitasi:"},
    "online_enrichment.homepage_link": {"en": "Journal homepage ↗", "ar": "الصفحة الرئيسية للمجلة ↗", "id": "Beranda jurnal ↗"},
    "online_enrichment.empty": {
        "en": "No additional online metadata found for this journal.",
        "ar": "لم يتم العثور على بيانات وصفية إضافية عبر الإنترنت لهذه المجلة.",
        "id": "Tidak ditemukan metadata daring tambahan untuk jurnal ini.",
    },

    # -- Research idea form/result/modal (#129) ------------------------------
    "research_idea_modal.title": {"en": "Start from a Research Idea", "ar": "ابدأ من فكرة بحثية", "id": "Mulai dari Ide Riset"},
    "research_idea_modal.close_aria": {"en": "Close", "ar": "إغلاق", "id": "Tutup"},
    "research_idea_form.label": {"en": "Describe your research idea", "ar": "صف فكرتك البحثية", "id": "Jelaskan ide riset Anda"},
    "research_idea_form.placeholder": {
        "en": "e.g. I want to study how social media use affects academic performance among university students...",
        "ar": "مثال: أرغب في دراسة كيفية تأثير استخدام وسائل التواصل الاجتماعي على الأداء الأكاديمي لدى طلاب الجامعات...",
        "id": "misalnya: Saya ingin meneliti bagaimana penggunaan media sosial memengaruhi prestasi akademik mahasiswa...",
    },
    "research_idea_form.helper": {
        "en": "Scilene will turn this into a set of suggested search tags — you'll review and can edit them before searching. If you already have a full abstract, paste it directly on the search page instead.",
        "ar": "سيحوّل Scilene هذا إلى مجموعة من وسوم البحث المقترحة — يمكنك مراجعتها وتعديلها قبل البحث. إذا كان لديك ملخص كامل بالفعل، الصقه مباشرة في صفحة البحث بدلاً من ذلك.",
        "id": "Scilene akan mengubah ini menjadi sekumpulan tag pencarian yang disarankan — Anda dapat meninjau dan mengeditnya sebelum mencari. Jika Anda sudah memiliki abstrak lengkap, tempel langsung di halaman pencarian.",
    },
    "research_idea_form.generate_button": {"en": "Generate", "ar": "إنشاء", "id": "Hasilkan"},
    "research_idea_result.helper": {
        "en": "Review and edit before continuing — nothing here has touched the recommendation engine yet.",
        "ar": "راجع وعدّل قبل المتابعة — لم يمس أي شيء هنا محرك التوصيات بعد.",
        "id": "Tinjau dan edit sebelum melanjutkan — belum ada yang menyentuh mesin rekomendasi di sini.",
    },
    "research_idea_result.keywords_label": {"en": "Suggested keywords", "ar": "الكلمات المفتاحية المقترحة", "id": "Kata kunci yang disarankan"},
    "research_idea_result.keywords_helper": {
        "en": "Comma-separated — these become your search tags, same as typing them by hand. Scilene needs at least 10 if you're not pasting an abstract ({count} extracted from your idea{more_clause}).",
        "ar": "مفصولة بفواصل — تصبح هذه وسوم بحثك، تماماً كما لو كتبتها يدوياً. يحتاج Scilene إلى 10 على الأقل إذا لم تلصق ملخصاً ({count} مستخرجة من فكرتك{more_clause}).",
        "id": "Dipisahkan koma — ini menjadi tag pencarian Anda, sama seperti mengetiknya sendiri. Scilene memerlukan minimal 10 jika Anda tidak menempelkan abstrak ({count} diekstrak dari ide Anda{more_clause}).",
    },
    "research_idea_result.keywords_helper_more": {
        "en": ", add a few more before continuing",
        "ar": "، أضف بضعة كلمات أخرى قبل المتابعة",
        "id": ", tambahkan beberapa lagi sebelum melanjutkan",
    },
    "research_idea_result.continue_button": {"en": "Continue to Search", "ar": "المتابعة إلى البحث", "id": "Lanjutkan ke Pencarian"},
    "research_idea_result.start_over_button": {"en": "← Start over", "ar": "← البدء من جديد", "id": "← Mulai lagi"},

    # -- Small shared components (#129) --------------------------------------
    "compare_bar.selected_count": {
        "en": "{selected}/{max} selected for comparison",
        "ar": "تم تحديد {selected}/{max} للمقارنة",
        "id": "{selected}/{max} dipilih untuk dibandingkan",
    },
    "compare_bar.compare_now": {"en": "Compare Now", "ar": "قارن الآن", "id": "Bandingkan Sekarang"},
    "compare_bar.clear": {"en": "Clear", "ar": "مسح", "id": "Hapus"},

    "pagination.previous": {"en": "⬅️ Previous", "ar": "⬅️ السابق", "id": "⬅️ Sebelumnya"},
    "pagination.page_of": {"en": "Page {page} of {total}", "ar": "صفحة {page} من {total}", "id": "Halaman {page} dari {total}"},
    "pagination.next": {"en": "Next ➡️", "ar": "التالي ➡️", "id": "Berikutnya ➡️"},

    "search_history.summary": {"en": "🕘 Search History ({count})", "ar": "🕘 سجل البحث ({count})", "id": "🕘 Riwayat Pencarian ({count})"},
    "search_history.helper": {
        "en": "Kept only for this browser session — not saved anywhere.",
        "ar": "يُحفظ فقط لجلسة المتصفح هذه — ولا يُخزَّن في أي مكان آخر.",
        "id": "Hanya disimpan untuk sesi browser ini — tidak disimpan di mana pun.",
    },
    "search_history.untitled": {"en": "Untitled search", "ar": "بحث بلا عنوان", "id": "Pencarian tanpa judul"},
    "search_history.utc": {"en": "UTC", "ar": "بالتوقيت العالمي", "id": "UTC"},
    "search_history.results_count": {"en": "{count} results", "ar": "{count} نتيجة", "id": "{count} hasil"},
    "search_history.rerun": {"en": "Rerun", "ar": "إعادة التشغيل", "id": "Jalankan ulang"},

    "index_badge.journals_suffix": {"en": "{count} journals", "ar": "{count} مجلة", "id": "{count} jurnal"},

    "coming_soon.label": {"en": "Coming soon", "ar": "قريباً", "id": "Segera hadir"},
    "coming_soon.back_to_home": {"en": "← Back to Home", "ar": "← العودة إلى الرئيسية", "id": "← Kembali ke Beranda"},

    # -- Backend-supplied warnings/errors (#129) -----------------------------
    "warning.abstract_or_tags_required": {
        "en": "Please provide an abstract, or at least 10 descriptive tags if you don't have one ({count} so far).",
        "ar": "يرجى تقديم ملخص، أو 10 وسوم وصفية على الأقل إذا لم يكن لديك ملخص ({count} حتى الآن).",
        "id": "Mohon berikan abstrak, atau setidaknya 10 tag deskriptif jika Anda tidak memilikinya ({count} sejauh ini).",
    },
    "warning.no_index_selected": {
        "en": "Please select at least one journal index before searching.",
        "ar": "يرجى اختيار فهرس مجلة واحد على الأقل قبل البحث.",
        "id": "Mohon pilih setidaknya satu indeks jurnal sebelum mencari.",
    },
    "warning.no_results": {
        "en": "No journals matched your current filters. Try a broader search, a different budget/language, or fewer indexing/quartile filters.",
        "ar": "لم تتطابق أي مجلات مع المرشحات الحالية. جرّب بحثاً أوسع، ميزانية/لغة مختلفة، أو عدد أقل من مرشحات الفهرسة/الربعية.",
        "id": "Tidak ada jurnal yang cocok dengan filter Anda saat ini. Coba pencarian yang lebih luas, anggaran/bahasa berbeda, atau lebih sedikit filter pengindeksan/kuartil.",
    },
    "warning.sls_load_error": {
        "en": "Couldn't load this session file: {error}",
        "ar": "تعذّر تحميل ملف الجلسة هذا: {error}",
        "id": "Tidak dapat memuat file sesi ini: {error}",
    },
    "warning.sls_no_index": {
        "en": "This session file has no journal index selected — nothing to search with.",
        "ar": "لا يحتوي ملف الجلسة هذا على فهرس مجلة محدد — لا يوجد ما يمكن البحث به.",
        "id": "File sesi ini tidak memiliki indeks jurnal yang dipilih — tidak ada yang bisa dicari.",
    },
    # Keyed by the EXACT literal message services/sls_format.py raises
    # (that module is framework-agnostic and has no i18n of its own --
    # see web/routers/search.py's import_sls() for the lookup-with-
    # fallback that uses these).
    "error.This doesn't look like a Scilene session file (.sls, or a legacy .jis).": {
        "en": "This doesn't look like a Scilene session file (.sls, or a legacy .jis).",
        "ar": "هذا لا يبدو ملف جلسة Scilene (.sls، أو ملف .jis قديم).",
        "id": "Ini tidak terlihat seperti file sesi Scilene (.sls, atau .jis lama).",
    },
    "error.This file isn't valid JSON.": {
        "en": "This file isn't valid JSON.",
        "ar": "هذا الملف ليس بصيغة JSON صالحة.",
        "id": "File ini bukan JSON yang valid.",
    },
    "error.This session file is missing its search data.": {
        "en": "This session file is missing its search data.",
        "ar": "يفتقر ملف الجلسة هذا إلى بيانات البحث الخاصة به.",
        "id": "File sesi ini kehilangan data pencariannya.",
    },
    "error.This session has neither an abstract nor at least 10 tags -- nothing to search with.": {
        "en": "This session has neither an abstract nor at least 10 tags -- nothing to search with.",
        "ar": "لا تحتوي هذه الجلسة على ملخص ولا على 10 وسوم على الأقل — لا يوجد ما يمكن البحث به.",
        "id": "Sesi ini tidak memiliki abstrak maupun setidaknya 10 tag — tidak ada yang bisa dicari.",
    },
    # Known literal AIResponse.error strings from services/ai_provider.py
    # (framework-agnostic by design, so it never imports web/i18n.py
    # itself -- research_idea_result.html looks up the exact English
    # text it receives against this map and falls back to showing it
    # verbatim if unrecognized, e.g. a real provider's own error text).
    "ai_error.No research idea provided.": {"en": "No research idea provided.", "ar": "لم تُقدَّم أي فكرة بحثية.", "id": "Tidak ada ide riset yang diberikan."},
    "ai_error.No abstract provided.": {"en": "No abstract provided.", "ar": "لم يُقدَّم أي ملخص.", "id": "Tidak ada abstrak yang diberikan."},
    "ai_error.Provider response was not valid JSON.": {"en": "Provider response was not valid JSON.", "ar": "استجابة المزوّد لم تكن بصيغة JSON صالحة.", "id": "Respons penyedia bukan JSON yang valid."},
    "ai_error.Provider response did not match the expected contract.": {"en": "Provider response did not match the expected contract.", "ar": "لم تتطابق استجابة المزوّد مع الصيغة المتوقعة.", "id": "Respons penyedia tidak sesuai dengan kontrak yang diharapkan."},

    # -- Documentation placeholder page (#129) -------------------------------
    "documentation.title": {"en": "Documentation", "ar": "التوثيق", "id": "Dokumentasi"},
    "documentation.description": {
        "en": "User-facing documentation for {app_name} is planned for a future milestone.",
        "ar": "التوثيق الموجّه للمستخدمين الخاص بـ {app_name} مخطط له في مرحلة مستقبلية.",
        "id": "Dokumentasi untuk pengguna {app_name} direncanakan untuk milestone mendatang.",
    },

    # -- Stragglers caught by the #129 completeness audit --------------------
    "nav.theme_toggle_aria": {
        "en": "Switch between dark and light appearance",
        "ar": "التبديل بين المظهر الداكن والفاتح",
        "id": "Beralih antara tampilan gelap dan terang",
    },
    "home.title": {
        "en": "{app_name} — Find the right journal for your research",
        "ar": "{app_name} — اعثر على المجلة المناسبة لبحثك",
        "id": "{app_name} — Temukan jurnal yang tepat untuk riset Anda",
    },
    "about.logo_alt": {"en": "Scilene logo", "ar": "شعار Scilene", "id": "Logo Scilene"},
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
