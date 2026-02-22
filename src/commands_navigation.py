"""JARVIS — Commandes navigation web supplementaires (sites et services)."""

from __future__ import annotations

from src.commands import JarvisCommand

NAVIGATION_COMMANDS: list[JarvisCommand] = [
    # ══════════════════════════════════════════════════════════════════════
    # RESEAUX SOCIAUX
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_twitter", "navigation", "Ouvrir Twitter/X", [
        "ouvre twitter", "va sur twitter", "ouvre x",
        "va sur x", "lance twitter",
    ], "browser", "navigate:https://x.com"),
    JarvisCommand("ouvrir_reddit", "navigation", "Ouvrir Reddit", [
        "ouvre reddit", "va sur reddit", "lance reddit",
        "ouvrir reddit",
    ], "browser", "navigate:https://www.reddit.com"),
    JarvisCommand("ouvrir_linkedin", "navigation", "Ouvrir LinkedIn", [
        "ouvre linkedin", "va sur linkedin", "lance linkedin",
        "ouvrir linkedin",
    ], "browser", "navigate:https://www.linkedin.com"),
    JarvisCommand("ouvrir_instagram", "navigation", "Ouvrir Instagram", [
        "ouvre instagram", "va sur instagram", "lance instagram",
        "ouvre insta", "va sur insta",
    ], "browser", "navigate:https://www.instagram.com"),
    JarvisCommand("ouvrir_tiktok", "navigation", "Ouvrir TikTok", [
        "ouvre tiktok", "va sur tiktok", "lance tiktok",
    ], "browser", "navigate:https://www.tiktok.com"),
    JarvisCommand("ouvrir_twitch", "navigation", "Ouvrir Twitch", [
        "ouvre twitch", "va sur twitch", "lance twitch",
        "ouvrir twitch",
    ], "browser", "navigate:https://www.twitch.tv"),

    # ══════════════════════════════════════════════════════════════════════
    # IA & RECHERCHE
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_chatgpt", "navigation", "Ouvrir ChatGPT", [
        "ouvre chatgpt", "va sur chatgpt", "lance chatgpt",
        "ouvre chat gpt", "ouvrir chatgpt",
    ], "browser", "navigate:https://chat.openai.com"),
    JarvisCommand("ouvrir_claude", "navigation", "Ouvrir Claude AI", [
        "ouvre claude", "va sur claude", "lance claude",
        "ouvre claude ai", "ouvrir claude",
    ], "browser", "navigate:https://claude.ai"),
    JarvisCommand("ouvrir_perplexity", "navigation", "Ouvrir Perplexity", [
        "ouvre perplexity", "va sur perplexity", "lance perplexity",
        "ouvrir perplexity",
    ], "browser", "navigate:https://www.perplexity.ai"),
    JarvisCommand("ouvrir_huggingface", "navigation", "Ouvrir Hugging Face", [
        "ouvre hugging face", "va sur hugging face",
        "lance hugging face", "ouvre huggingface",
    ], "browser", "navigate:https://huggingface.co"),
    JarvisCommand("ouvrir_wikipedia", "navigation", "Ouvrir Wikipedia", [
        "ouvre wikipedia", "va sur wikipedia", "lance wikipedia",
        "ouvre wiki",
    ], "browser", "navigate:https://fr.wikipedia.org"),

    # ══════════════════════════════════════════════════════════════════════
    # SHOPPING & SERVICES
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_amazon", "navigation", "Ouvrir Amazon", [
        "ouvre amazon", "va sur amazon", "lance amazon",
        "ouvrir amazon",
    ], "browser", "navigate:https://www.amazon.fr"),
    JarvisCommand("ouvrir_leboncoin", "navigation", "Ouvrir Leboncoin", [
        "ouvre leboncoin", "va sur leboncoin", "lance leboncoin",
        "le bon coin", "ouvre le bon coin",
    ], "browser", "navigate:https://www.leboncoin.fr"),
    JarvisCommand("ouvrir_netflix", "navigation", "Ouvrir Netflix", [
        "ouvre netflix", "va sur netflix", "lance netflix",
    ], "browser", "navigate:https://www.netflix.com"),
    JarvisCommand("ouvrir_spotify_web", "navigation", "Ouvrir Spotify Web Player", [
        "ouvre spotify web", "spotify web", "lance spotify en ligne",
        "ouvre le lecteur spotify web",
    ], "browser", "navigate:https://open.spotify.com"),
    JarvisCommand("ouvrir_disney_plus", "navigation", "Ouvrir Disney+", [
        "ouvre disney plus", "va sur disney plus", "lance disney",
        "ouvre disney+",
    ], "browser", "navigate:https://www.disneyplus.com"),

    # ══════════════════════════════════════════════════════════════════════
    # DEV & TECH
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_stackoverflow", "navigation", "Ouvrir Stack Overflow", [
        "ouvre stackoverflow", "va sur stackoverflow",
        "ouvre stack overflow", "lance stackoverflow",
    ], "browser", "navigate:https://stackoverflow.com"),
    JarvisCommand("ouvrir_npmjs", "navigation", "Ouvrir NPM", [
        "ouvre npm", "va sur npm", "ouvre npmjs",
        "npm registry",
    ], "browser", "navigate:https://www.npmjs.com"),
    JarvisCommand("ouvrir_pypi", "navigation", "Ouvrir PyPI", [
        "ouvre pypi", "va sur pypi", "lance pypi",
        "python packages",
    ], "browser", "navigate:https://pypi.org"),
    JarvisCommand("ouvrir_docker_hub", "navigation", "Ouvrir Docker Hub", [
        "ouvre docker hub", "va sur docker hub",
        "lance docker hub",
    ], "browser", "navigate:https://hub.docker.com"),

    # ══════════════════════════════════════════════════════════════════════
    # OUTILS EN LIGNE
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_google_drive", "navigation", "Ouvrir Google Drive", [
        "ouvre google drive", "va sur google drive", "ouvre drive",
        "ouvre mon drive", "lance google drive",
    ], "browser", "navigate:https://drive.google.com"),
    JarvisCommand("ouvrir_google_docs", "navigation", "Ouvrir Google Docs", [
        "ouvre google docs", "va sur google docs", "ouvre docs",
        "nouveau document google",
    ], "browser", "navigate:https://docs.google.com"),
    JarvisCommand("ouvrir_google_sheets", "navigation", "Ouvrir Google Sheets", [
        "ouvre google sheets", "va sur google sheets", "ouvre sheets",
        "nouveau tableur google",
    ], "browser", "navigate:https://sheets.google.com"),
    JarvisCommand("ouvrir_google_maps", "navigation", "Ouvrir Google Maps", [
        "ouvre google maps", "va sur google maps", "ouvre maps",
        "lance google maps", "ouvre la carte",
    ], "browser", "navigate:https://maps.google.com"),
    JarvisCommand("ouvrir_google_calendar", "navigation", "Ouvrir Google Calendar", [
        "ouvre google calendar", "ouvre l'agenda", "ouvre le calendrier",
        "va sur google calendar", "ouvre agenda google",
    ], "browser", "navigate:https://calendar.google.com"),
    JarvisCommand("ouvrir_notion", "navigation", "Ouvrir Notion", [
        "ouvre notion", "va sur notion", "lance notion",
        "ouvre mon notion",
    ], "browser", "navigate:https://www.notion.so"),

    # ══════════════════════════════════════════════════════════════════════
    # RECHERCHE SPECIALISEE
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("chercher_images", "navigation", "Rechercher des images sur Google", [
        "cherche des images de {requete}", "images de {requete}",
        "google images {requete}", "trouve des images de {requete}",
    ], "browser", "navigate:https://www.google.com/search?tbm=isch&q={requete}", ["requete"]),
    JarvisCommand("chercher_reddit", "navigation", "Rechercher sur Reddit", [
        "cherche sur reddit {requete}", "reddit {requete}",
        "recherche reddit {requete}",
    ], "browser", "navigate:https://www.reddit.com/search/?q={requete}", ["requete"]),
    JarvisCommand("chercher_wikipedia", "navigation", "Rechercher sur Wikipedia", [
        "cherche sur wikipedia {requete}", "wikipedia {requete}",
        "wiki {requete}",
    ], "browser", "navigate:https://fr.wikipedia.org/w/index.php?search={requete}", ["requete"]),
    JarvisCommand("chercher_amazon", "navigation", "Rechercher sur Amazon", [
        "cherche sur amazon {requete}", "amazon {requete}",
        "recherche amazon {requete}", "acheter {requete}",
    ], "browser", "navigate:https://www.amazon.fr/s?k={requete}", ["requete"]),

    # ══════════════════════════════════════════════════════════════════════
    # CRYPTO & TRADING
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_tradingview_web", "navigation", "Ouvrir TradingView", [
        "ouvre tradingview", "va sur tradingview", "lance tradingview",
        "ouvre trading view",
    ], "browser", "navigate:https://www.tradingview.com"),
    JarvisCommand("ouvrir_coingecko", "navigation", "Ouvrir CoinGecko", [
        "ouvre coingecko", "va sur coingecko", "lance coingecko",
        "ouvre coin gecko",
    ], "browser", "navigate:https://www.coingecko.com"),
    JarvisCommand("ouvrir_coinmarketcap", "navigation", "Ouvrir CoinMarketCap", [
        "ouvre coinmarketcap", "va sur coinmarketcap",
        "lance coinmarketcap", "ouvre cmc",
    ], "browser", "navigate:https://coinmarketcap.com"),
    JarvisCommand("ouvrir_mexc_exchange", "navigation", "Ouvrir MEXC Exchange", [
        "ouvre mexc", "va sur mexc", "lance mexc",
        "ouvre l'exchange",
    ], "browser", "navigate:https://www.mexc.com"),
    JarvisCommand("ouvrir_dexscreener", "navigation", "Ouvrir DexScreener", [
        "ouvre dexscreener", "va sur dexscreener", "lance dexscreener",
        "ouvre dex screener",
    ], "browser", "navigate:https://dexscreener.com"),

    # ══════════════════════════════════════════════════════════════════════
    # COMMUNICATION WEB
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_telegram_web", "navigation", "Ouvrir Telegram Web", [
        "ouvre telegram web", "telegram web", "telegram en ligne",
        "va sur telegram web",
    ], "browser", "navigate:https://web.telegram.org"),
    JarvisCommand("ouvrir_whatsapp_web", "navigation", "Ouvrir WhatsApp Web", [
        "ouvre whatsapp web", "whatsapp web", "whatsapp en ligne",
        "va sur whatsapp web",
    ], "browser", "navigate:https://web.whatsapp.com"),
    JarvisCommand("ouvrir_slack_web", "navigation", "Ouvrir Slack Web", [
        "ouvre slack web", "slack web", "slack en ligne",
        "va sur slack web",
    ], "browser", "navigate:https://app.slack.com"),
    JarvisCommand("ouvrir_teams_web", "navigation", "Ouvrir Microsoft Teams Web", [
        "ouvre teams web", "teams web", "teams en ligne",
        "va sur teams web",
    ], "browser", "navigate:https://teams.microsoft.com"),

    # ══════════════════════════════════════════════════════════════════════
    # VIDEO & STREAMING
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_youtube_music", "navigation", "Ouvrir YouTube Music", [
        "ouvre youtube music", "youtube music", "lance youtube music",
        "ouvre la musique youtube",
    ], "browser", "navigate:https://music.youtube.com"),
    JarvisCommand("ouvrir_prime_video", "navigation", "Ouvrir Amazon Prime Video", [
        "ouvre prime video", "va sur prime video", "lance prime video",
        "ouvre amazon prime",
    ], "browser", "navigate:https://www.primevideo.com"),
    JarvisCommand("ouvrir_crunchyroll", "navigation", "Ouvrir Crunchyroll", [
        "ouvre crunchyroll", "va sur crunchyroll", "lance crunchyroll",
        "ouvre crunchy",
    ], "browser", "navigate:https://www.crunchyroll.com"),

    # ══════════════════════════════════════════════════════════════════════
    # DEV & TECH — Sites supplementaires
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_github_web", "navigation", "Ouvrir GitHub", [
        "ouvre github", "va sur github", "lance github",
        "ouvrir github",
    ], "browser", "navigate:https://github.com"),
    JarvisCommand("ouvrir_vercel", "navigation", "Ouvrir Vercel", [
        "ouvre vercel", "va sur vercel", "lance vercel",
    ], "browser", "navigate:https://vercel.com"),
    JarvisCommand("ouvrir_crates_io", "navigation", "Ouvrir crates.io (Rust packages)", [
        "ouvre crates io", "va sur crates", "crates rust",
        "packages rust",
    ], "browser", "navigate:https://crates.io"),

    # ══════════════════════════════════════════════════════════════════════
    # RECHERCHE SPECIALISEE — Supplementaire
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("chercher_video_youtube", "navigation", "Rechercher sur YouTube", [
        "cherche sur youtube {requete}", "youtube {requete}",
        "recherche youtube {requete}", "video {requete}",
    ], "browser", "navigate:https://www.youtube.com/results?search_query={requete}", ["requete"]),
    JarvisCommand("chercher_github", "navigation", "Rechercher sur GitHub", [
        "cherche sur github {requete}", "github {requete}",
        "recherche github {requete}", "repo {requete}",
    ], "browser", "navigate:https://github.com/search?q={requete}", ["requete"]),
    JarvisCommand("chercher_stackoverflow", "navigation", "Rechercher sur Stack Overflow", [
        "cherche sur stackoverflow {requete}", "stackoverflow {requete}",
        "stack overflow {requete}",
    ], "browser", "navigate:https://stackoverflow.com/search?q={requete}", ["requete"]),
    JarvisCommand("chercher_npm", "navigation", "Rechercher un package NPM", [
        "cherche sur npm {requete}", "npm {requete}",
        "recherche npm {requete}", "package npm {requete}",
    ], "browser", "navigate:https://www.npmjs.com/search?q={requete}", ["requete"]),
    JarvisCommand("chercher_pypi", "navigation", "Rechercher un package PyPI", [
        "cherche sur pypi {requete}", "pypi {requete}",
        "recherche pypi {requete}", "package python {requete}",
    ], "browser", "navigate:https://pypi.org/search/?q={requete}", ["requete"]),

    # ══════════════════════════════════════════════════════════════════════
    # OUTILS EN LIGNE — Developpement & Utilitaires
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_google_translate", "navigation", "Ouvrir Google Translate", [
        "ouvre google translate", "traducteur", "google traduction",
        "ouvre le traducteur", "lance google translate",
    ], "browser", "navigate:https://translate.google.com"),
    JarvisCommand("ouvrir_google_news", "navigation", "Ouvrir Google Actualites", [
        "ouvre google news", "google actualites", "lance les news",
        "ouvre les actualites",
    ], "browser", "navigate:https://news.google.com"),
    JarvisCommand("ouvrir_figma", "navigation", "Ouvrir Figma", [
        "ouvre figma", "va sur figma", "lance figma",
    ], "browser", "navigate:https://www.figma.com"),
    JarvisCommand("ouvrir_canva", "navigation", "Ouvrir Canva", [
        "ouvre canva", "va sur canva", "lance canva",
    ], "browser", "navigate:https://www.canva.com"),
    JarvisCommand("ouvrir_pinterest", "navigation", "Ouvrir Pinterest", [
        "ouvre pinterest", "va sur pinterest", "lance pinterest",
    ], "browser", "navigate:https://www.pinterest.com"),
    JarvisCommand("ouvrir_udemy", "navigation", "Ouvrir Udemy", [
        "ouvre udemy", "va sur udemy", "lance udemy",
        "cours en ligne",
    ], "browser", "navigate:https://www.udemy.com"),
    JarvisCommand("ouvrir_regex101", "navigation", "Ouvrir Regex101 (testeur de regex)", [
        "ouvre regex101", "testeur regex", "lance regex101",
        "regex en ligne",
    ], "browser", "navigate:https://regex101.com"),
    JarvisCommand("ouvrir_jsonformatter", "navigation", "Ouvrir un formatteur JSON en ligne", [
        "ouvre json formatter", "formatte du json", "json en ligne",
        "json formatter",
    ], "browser", "navigate:https://jsonformatter.org"),
    JarvisCommand("ouvrir_speedtest", "navigation", "Ouvrir Speedtest", [
        "ouvre speedtest", "lance un speed test", "test de debit",
        "teste ma connexion",
    ], "browser", "navigate:https://www.speedtest.net"),
    JarvisCommand("ouvrir_excalidraw", "navigation", "Ouvrir Excalidraw (tableau blanc)", [
        "ouvre excalidraw", "tableau blanc", "lance excalidraw",
        "whiteboard en ligne",
    ], "browser", "navigate:https://excalidraw.com"),
    JarvisCommand("ouvrir_soundcloud", "navigation", "Ouvrir SoundCloud", [
        "ouvre soundcloud", "va sur soundcloud", "lance soundcloud",
    ], "browser", "navigate:https://soundcloud.com"),
    JarvisCommand("ouvrir_google_scholar", "navigation", "Ouvrir Google Scholar", [
        "ouvre google scholar", "google scholar", "recherche academique",
        "articles scientifiques",
    ], "browser", "navigate:https://scholar.google.com"),

    # ══════════════════════════════════════════════════════════════════════
    # RECHERCHE SPECIALISEE — Supplementaire
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("chercher_traduction", "navigation", "Traduire un texte via Google Translate", [
        "traduis {requete}", "traduction de {requete}",
        "translate {requete}", "comment on dit {requete}",
    ], "browser", "navigate:https://translate.google.com/?sl=auto&tl=fr&text={requete}", ["requete"]),
    JarvisCommand("chercher_google_scholar", "navigation", "Rechercher sur Google Scholar", [
        "cherche sur scholar {requete}", "article sur {requete}",
        "recherche academique {requete}", "scholar {requete}",
    ], "browser", "navigate:https://scholar.google.com/scholar?q={requete}", ["requete"]),
    JarvisCommand("chercher_huggingface", "navigation", "Rechercher un modele sur Hugging Face", [
        "cherche sur hugging face {requete}", "modele {requete} huggingface",
        "hugging face {requete}",
    ], "browser", "navigate:https://huggingface.co/models?search={requete}", ["requete"]),
    JarvisCommand("chercher_docker_hub", "navigation", "Rechercher une image Docker Hub", [
        "cherche sur docker hub {requete}", "image docker {requete}",
        "docker hub {requete}",
    ], "browser", "navigate:https://hub.docker.com/search?q={requete}", ["requete"]),

    # ══════════════════════════════════════════════════════════════════════
    # GOOGLE WORKSPACE
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_gmail_web", "navigation", "Ouvrir Gmail", [
        "ouvre gmail", "va sur gmail", "lance gmail",
        "ouvre mes mails", "ouvre ma boite mail",
    ], "browser", "navigate:https://mail.google.com"),
    JarvisCommand("ouvrir_google_keep", "navigation", "Ouvrir Google Keep (notes)", [
        "ouvre google keep", "ouvre keep", "lance keep",
        "mes notes google", "ouvre les notes",
    ], "browser", "navigate:https://keep.google.com"),
    JarvisCommand("ouvrir_google_photos", "navigation", "Ouvrir Google Photos", [
        "ouvre google photos", "va sur google photos", "mes photos",
        "ouvre les photos", "lance google photos",
    ], "browser", "navigate:https://photos.google.com"),
    JarvisCommand("ouvrir_google_meet", "navigation", "Ouvrir Google Meet", [
        "ouvre google meet", "lance meet", "google meet",
        "ouvre meet", "visio google",
    ], "browser", "navigate:https://meet.google.com"),

    # ══════════════════════════════════════════════════════════════════════
    # TRADUCTION & RÉFÉRENCE
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_deepl", "navigation", "Ouvrir DeepL Traducteur", [
        "ouvre deepl", "va sur deepl", "lance deepl",
        "traducteur deepl", "deepl traduction",
    ], "browser", "navigate:https://www.deepl.com/translator"),
    JarvisCommand("ouvrir_wayback_machine", "navigation", "Ouvrir la Wayback Machine (archive web)", [
        "ouvre wayback machine", "wayback machine", "archive internet",
        "web archive", "ancienne version d'un site",
    ], "browser", "navigate:https://web.archive.org"),

    # ══════════════════════════════════════════════════════════════════════
    # DEV — Playgrounds & Communautés
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_codepen", "navigation", "Ouvrir CodePen", [
        "ouvre codepen", "va sur codepen", "lance codepen",
        "code pen", "playground codepen",
    ], "browser", "navigate:https://codepen.io"),
    JarvisCommand("ouvrir_jsfiddle", "navigation", "Ouvrir JSFiddle", [
        "ouvre jsfiddle", "va sur jsfiddle", "lance jsfiddle",
        "js fiddle",
    ], "browser", "navigate:https://jsfiddle.net"),
    JarvisCommand("ouvrir_dev_to", "navigation", "Ouvrir dev.to (communaute dev)", [
        "ouvre dev to", "va sur dev to", "lance dev.to",
        "ouvre dev point to", "communaute dev",
    ], "browser", "navigate:https://dev.to"),
    JarvisCommand("ouvrir_medium", "navigation", "Ouvrir Medium", [
        "ouvre medium", "va sur medium", "lance medium",
        "articles medium",
    ], "browser", "navigate:https://medium.com"),
    JarvisCommand("ouvrir_hacker_news", "navigation", "Ouvrir Hacker News", [
        "ouvre hacker news", "va sur hacker news", "lance hacker news",
        "ouvre hn", "ycombinator news",
    ], "browser", "navigate:https://news.ycombinator.com"),
    JarvisCommand("ouvrir_producthunt", "navigation", "Ouvrir Product Hunt", [
        "ouvre product hunt", "va sur product hunt", "lance product hunt",
        "producthunt", "nouveaux produits tech",
    ], "browser", "navigate:https://www.producthunt.com"),

    # ══════════════════════════════════════════════════════════════════════
    # ÉDUCATION & DATA SCIENCE
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_coursera", "navigation", "Ouvrir Coursera", [
        "ouvre coursera", "va sur coursera", "lance coursera",
        "cours coursera", "formation coursera",
    ], "browser", "navigate:https://www.coursera.org"),
    JarvisCommand("ouvrir_kaggle", "navigation", "Ouvrir Kaggle", [
        "ouvre kaggle", "va sur kaggle", "lance kaggle",
        "datasets kaggle", "competitions kaggle",
    ], "browser", "navigate:https://www.kaggle.com"),
    JarvisCommand("ouvrir_arxiv", "navigation", "Ouvrir arXiv (articles scientifiques)", [
        "ouvre arxiv", "va sur arxiv", "lance arxiv",
        "papers arxiv", "articles arxiv",
    ], "browser", "navigate:https://arxiv.org"),
    JarvisCommand("ouvrir_gitlab", "navigation", "Ouvrir GitLab", [
        "ouvre gitlab", "va sur gitlab", "lance gitlab",
    ], "browser", "navigate:https://gitlab.com"),
    JarvisCommand("ouvrir_bitbucket", "navigation", "Ouvrir Bitbucket", [
        "ouvre bitbucket", "va sur bitbucket", "lance bitbucket",
    ], "browser", "navigate:https://bitbucket.org"),
    JarvisCommand("ouvrir_leetcode", "navigation", "Ouvrir LeetCode", [
        "ouvre leetcode", "va sur leetcode", "lance leetcode",
        "exercices code", "algo leetcode",
    ], "browser", "navigate:https://leetcode.com"),
    JarvisCommand("ouvrir_codewars", "navigation", "Ouvrir Codewars", [
        "ouvre codewars", "va sur codewars", "lance codewars",
        "kata codewars", "challenges code",
    ], "browser", "navigate:https://www.codewars.com"),

    # ══════════════════════════════════════════════════════════════════════
    # RECHERCHE SPÉCIALISÉE — Nouvelles
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("chercher_deepl", "navigation", "Traduire via DeepL", [
        "traduis avec deepl {requete}", "deepl {requete}",
        "traduction deepl {requete}", "deepl traduction {requete}",
    ], "browser", "navigate:https://www.deepl.com/translator#auto/fr/{requete}", ["requete"]),
    JarvisCommand("chercher_arxiv", "navigation", "Rechercher sur arXiv", [
        "cherche sur arxiv {requete}", "arxiv {requete}",
        "paper sur {requete}", "articles scientifiques sur {requete}",
    ], "browser", "navigate:https://arxiv.org/search/?query={requete}", ["requete"]),
    JarvisCommand("chercher_kaggle", "navigation", "Rechercher sur Kaggle", [
        "cherche sur kaggle {requete}", "kaggle {requete}",
        "dataset {requete}", "competition {requete}",
    ], "browser", "navigate:https://www.kaggle.com/search?q={requete}", ["requete"]),
    JarvisCommand("chercher_leetcode", "navigation", "Rechercher un probleme LeetCode", [
        "cherche sur leetcode {requete}", "leetcode {requete}",
        "probleme {requete} leetcode",
    ], "browser", "navigate:https://leetcode.com/problemset/?search={requete}", ["requete"]),
    JarvisCommand("chercher_medium", "navigation", "Rechercher sur Medium", [
        "cherche sur medium {requete}", "medium {requete}",
        "article medium {requete}",
    ], "browser", "navigate:https://medium.com/search?q={requete}", ["requete"]),
    JarvisCommand("chercher_hacker_news", "navigation", "Rechercher sur Hacker News", [
        "cherche sur hacker news {requete}", "hn {requete}",
        "hacker news {requete}",
    ], "browser", "navigate:https://hn.algolia.com/?q={requete}", ["requete"]),

    # ══════════════════════════════════════════════════════════════════════
    # DEV MODERNE — Cloud & DevOps platforms
    # (source: Raycast extensions, Alfred workflows)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_linear", "navigation", "Ouvrir Linear (gestion de projet dev)", [
        "ouvre linear", "va sur linear", "lance linear",
        "issues linear", "board linear",
    ], "browser", "navigate:https://linear.app"),
    JarvisCommand("ouvrir_miro", "navigation", "Ouvrir Miro (whiteboard collaboratif)", [
        "ouvre miro", "va sur miro", "lance miro",
        "whiteboard miro", "tableau miro",
    ], "browser", "navigate:https://miro.com"),
    JarvisCommand("ouvrir_loom", "navigation", "Ouvrir Loom (enregistrement ecran)", [
        "ouvre loom", "va sur loom", "lance loom",
        "enregistre avec loom",
    ], "browser", "navigate:https://www.loom.com"),
    JarvisCommand("ouvrir_supabase", "navigation", "Ouvrir Supabase", [
        "ouvre supabase", "va sur supabase", "lance supabase",
        "dashboard supabase",
    ], "browser", "navigate:https://supabase.com/dashboard"),
    JarvisCommand("ouvrir_firebase", "navigation", "Ouvrir Firebase Console", [
        "ouvre firebase", "va sur firebase", "lance firebase",
        "console firebase",
    ], "browser", "navigate:https://console.firebase.google.com"),
    JarvisCommand("ouvrir_railway", "navigation", "Ouvrir Railway (deploy)", [
        "ouvre railway", "va sur railway", "lance railway",
        "dashboard railway",
    ], "browser", "navigate:https://railway.app/dashboard"),
    JarvisCommand("ouvrir_cloudflare", "navigation", "Ouvrir Cloudflare Dashboard", [
        "ouvre cloudflare", "va sur cloudflare", "lance cloudflare",
        "dashboard cloudflare",
    ], "browser", "navigate:https://dash.cloudflare.com"),
    JarvisCommand("ouvrir_render", "navigation", "Ouvrir Render (hosting)", [
        "ouvre render", "va sur render", "lance render",
        "dashboard render",
    ], "browser", "navigate:https://dashboard.render.com"),
    JarvisCommand("ouvrir_fly_io", "navigation", "Ouvrir Fly.io", [
        "ouvre fly io", "va sur fly", "lance fly io",
        "dashboard fly",
    ], "browser", "navigate:https://fly.io/dashboard"),

    # ══════════════════════════════════════════════════════════════════════
    # DOCUMENTATION DEV — Références essentielles
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_mdn", "navigation", "Ouvrir MDN Web Docs", [
        "ouvre mdn", "va sur mdn", "docs mdn",
        "mozilla docs", "mdn web docs",
    ], "browser", "navigate:https://developer.mozilla.org"),
    JarvisCommand("ouvrir_devdocs", "navigation", "Ouvrir DevDocs.io (toute la doc dev)", [
        "ouvre devdocs", "va sur devdocs", "lance devdocs",
        "documentation dev", "all docs",
    ], "browser", "navigate:https://devdocs.io"),
    JarvisCommand("ouvrir_can_i_use", "navigation", "Ouvrir Can I Use (compatibilite navigateurs)", [
        "ouvre can i use", "can i use", "compatibilite navigateur",
        "support navigateur",
    ], "browser", "navigate:https://caniuse.com"),
    JarvisCommand("ouvrir_bundlephobia", "navigation", "Ouvrir Bundlephobia (taille des packages)", [
        "ouvre bundlephobia", "bundlephobia", "taille package npm",
        "poids d'un package",
    ], "browser", "navigate:https://bundlephobia.com"),
    JarvisCommand("ouvrir_w3schools", "navigation", "Ouvrir W3Schools", [
        "ouvre w3schools", "va sur w3schools", "tuto w3schools",
        "w3 schools",
    ], "browser", "navigate:https://www.w3schools.com"),
    JarvisCommand("ouvrir_python_docs", "navigation", "Ouvrir la documentation Python officielle", [
        "ouvre la doc python", "doc python", "python docs",
        "documentation python officielle",
    ], "browser", "navigate:https://docs.python.org/3/"),
    JarvisCommand("ouvrir_rust_docs", "navigation", "Ouvrir la documentation Rust (The Book)", [
        "ouvre la doc rust", "doc rust", "rust book",
        "documentation rust",
    ], "browser", "navigate:https://doc.rust-lang.org/book/"),

    # ══════════════════════════════════════════════════════════════════════
    # PLAYGROUNDS & IDE EN LIGNE
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_replit", "navigation", "Ouvrir Replit (IDE en ligne)", [
        "ouvre replit", "va sur replit", "lance replit",
        "code en ligne replit",
    ], "browser", "navigate:https://replit.com"),
    JarvisCommand("ouvrir_codesandbox", "navigation", "Ouvrir CodeSandbox", [
        "ouvre codesandbox", "va sur codesandbox", "lance codesandbox",
        "sandbox en ligne",
    ], "browser", "navigate:https://codesandbox.io"),
    JarvisCommand("ouvrir_stackblitz", "navigation", "Ouvrir StackBlitz", [
        "ouvre stackblitz", "va sur stackblitz", "lance stackblitz",
        "ide stackblitz",
    ], "browser", "navigate:https://stackblitz.com"),
    JarvisCommand("ouvrir_typescript_playground", "navigation", "Ouvrir TypeScript Playground", [
        "ouvre typescript playground", "typescript playground",
        "teste du typescript", "ts playground",
    ], "browser", "navigate:https://www.typescriptlang.org/play"),
    JarvisCommand("ouvrir_rust_playground", "navigation", "Ouvrir Rust Playground", [
        "ouvre rust playground", "rust playground",
        "teste du rust", "playground rust",
    ], "browser", "navigate:https://play.rust-lang.org"),

    # ══════════════════════════════════════════════════════════════════════
    # UTILITAIRES & TENDANCES
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_google_trends", "navigation", "Ouvrir Google Trends", [
        "ouvre google trends", "google trends", "tendances google",
        "quoi est tendance",
    ], "browser", "navigate:https://trends.google.com"),
    JarvisCommand("ouvrir_alternativeto", "navigation", "Ouvrir AlternativeTo (alternatives logiciels)", [
        "ouvre alternativeto", "alternativeto", "alternative a un logiciel",
        "trouve une alternative",
    ], "browser", "navigate:https://alternativeto.net"),
    JarvisCommand("ouvrir_downdetector", "navigation", "Ouvrir DownDetector (status services)", [
        "ouvre downdetector", "downdetector", "c'est en panne",
        "status d'un service", "est ce que c'est down",
    ], "browser", "navigate:https://downdetector.com"),
    JarvisCommand("ouvrir_virustotal", "navigation", "Ouvrir VirusTotal (scan fichiers/URLs)", [
        "ouvre virustotal", "virustotal", "scan un fichier",
        "analyse de virus",
    ], "browser", "navigate:https://www.virustotal.com"),
    JarvisCommand("ouvrir_haveibeenpwned", "navigation", "Ouvrir Have I Been Pwned (verification email)", [
        "ouvre have i been pwned", "haveibeenpwned", "mon email a ete pirate",
        "check email breach", "verification piratage",
    ], "browser", "navigate:https://haveibeenpwned.com"),

    # ══════════════════════════════════════════════════════════════════════
    # RECHERCHE SPÉCIALISÉE — Nouvelles
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("chercher_crates_io", "navigation", "Rechercher un crate Rust", [
        "cherche sur crates {requete}", "crate rust {requete}",
        "package rust {requete}",
    ], "browser", "navigate:https://crates.io/search?q={requete}", ["requete"]),
    JarvisCommand("chercher_alternativeto", "navigation", "Chercher une alternative a un logiciel", [
        "alternative a {requete}", "cherche une alternative a {requete}",
        "remplace {requete}",
    ], "browser", "navigate:https://alternativeto.net/software/{requete}/", ["requete"]),
    JarvisCommand("chercher_mdn", "navigation", "Rechercher sur MDN Web Docs", [
        "cherche sur mdn {requete}", "mdn {requete}",
        "doc web {requete}",
    ], "browser", "navigate:https://developer.mozilla.org/search?q={requete}", ["requete"]),
    JarvisCommand("chercher_can_i_use", "navigation", "Verifier la compatibilite d'une feature web", [
        "can i use {requete}", "compatibilite de {requete}",
        "support de {requete}",
    ], "browser", "navigate:https://caniuse.com/?search={requete}", ["requete"]),

    # ══════════════════════════════════════════════════════════════════════
    # PRODUCTIVITÉ & OUTILS QUOTIDIENS
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_chatgpt_plugins", "navigation", "Ouvrir ChatGPT (avec GPTs)", [
        "ouvre les gpts", "chatgpt gpts", "custom gpt",
        "lance les gpts",
    ], "browser", "navigate:https://chat.openai.com/gpts"),
    JarvisCommand("ouvrir_anthropic_console", "navigation", "Ouvrir la console Anthropic API", [
        "ouvre anthropic console", "console anthropic", "api anthropic",
        "dashboard claude api",
    ], "browser", "navigate:https://console.anthropic.com"),
    JarvisCommand("ouvrir_openai_platform", "navigation", "Ouvrir la plateforme OpenAI API", [
        "ouvre openai platform", "console openai", "api openai",
        "dashboard openai",
    ], "browser", "navigate:https://platform.openai.com"),
    JarvisCommand("ouvrir_google_colab", "navigation", "Ouvrir Google Colab", [
        "ouvre google colab", "colab", "lance colab",
        "jupyter colab", "notebook colab",
    ], "browser", "navigate:https://colab.research.google.com"),
    JarvisCommand("ouvrir_overleaf", "navigation", "Ouvrir Overleaf (LaTeX en ligne)", [
        "ouvre overleaf", "va sur overleaf", "latex en ligne",
        "editeur latex",
    ], "browser", "navigate:https://www.overleaf.com"),
    JarvisCommand("ouvrir_whimsical", "navigation", "Ouvrir Whimsical (diagrams & flowcharts)", [
        "ouvre whimsical", "whimsical", "diagrammes whimsical",
        "flowchart en ligne",
    ], "browser", "navigate:https://whimsical.com"),
    JarvisCommand("ouvrir_grammarly", "navigation", "Ouvrir Grammarly", [
        "ouvre grammarly", "grammarly", "correcteur anglais",
        "check grammaire",
    ], "browser", "navigate:https://app.grammarly.com"),
    JarvisCommand("ouvrir_remove_bg", "navigation", "Ouvrir Remove.bg (supprimer arriere-plan)", [
        "ouvre remove bg", "supprime l'arriere plan", "remove background",
        "detourage image",
    ], "browser", "navigate:https://www.remove.bg"),
    JarvisCommand("ouvrir_tinypng", "navigation", "Ouvrir TinyPNG (compression images)", [
        "ouvre tinypng", "compresse une image", "tiny png",
        "optimise les images",
    ], "browser", "navigate:https://tinypng.com"),
    JarvisCommand("ouvrir_draw_io", "navigation", "Ouvrir draw.io (diagrammes)", [
        "ouvre draw io", "drawio", "diagramme en ligne",
        "lance draw io",
    ], "browser", "navigate:https://app.diagrams.net"),
    JarvisCommand("ouvrir_notion_calendar", "navigation", "Ouvrir Notion Calendar", [
        "ouvre notion calendar", "calendrier notion", "notion agenda",
        "lance notion calendar",
    ], "browser", "navigate:https://calendar.notion.so"),
    JarvisCommand("ouvrir_todoist", "navigation", "Ouvrir Todoist (gestion de taches)", [
        "ouvre todoist", "va sur todoist", "mes taches todoist",
        "todo list en ligne",
    ], "browser", "navigate:https://todoist.com/app"),

    # ══════════════════════════════════════════════════════════════════════
    # FINANCE & ACTUALITÉS
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_google_finance", "navigation", "Ouvrir Google Finance", [
        "ouvre google finance", "google finance", "cours de bourse",
        "actions google",
    ], "browser", "navigate:https://www.google.com/finance"),
    JarvisCommand("ouvrir_yahoo_finance", "navigation", "Ouvrir Yahoo Finance", [
        "ouvre yahoo finance", "yahoo finance", "yahoo bourse",
        "finance yahoo",
    ], "browser", "navigate:https://finance.yahoo.com"),
    JarvisCommand("ouvrir_coindesk", "navigation", "Ouvrir CoinDesk (news crypto)", [
        "ouvre coindesk", "news crypto", "coindesk",
        "actualites crypto",
    ], "browser", "navigate:https://www.coindesk.com"),
    JarvisCommand("ouvrir_meteo", "navigation", "Ouvrir la meteo", [
        "ouvre la meteo", "quel temps fait il", "meteo",
        "previsions meteo", "meteo du jour",
    ], "browser", "navigate:https://www.google.com/search?q=meteo"),

    # ══════════════════════════════════════════════════════════════════════
    # RECHERCHE SPÉCIALISÉE — Nouvelles
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("chercher_google_colab", "navigation", "Rechercher un notebook Colab", [
        "cherche un notebook {requete}", "colab {requete}",
        "notebook sur {requete}",
    ], "browser", "navigate:https://www.google.com/search?q={requete}+site:colab.research.google.com", ["requete"]),
    JarvisCommand("chercher_perplexity", "navigation", "Rechercher sur Perplexity AI", [
        "cherche sur perplexity {requete}", "perplexity {requete}",
        "demande a perplexity {requete}",
    ], "browser", "navigate:https://www.perplexity.ai/search?q={requete}", ["requete"]),
    JarvisCommand("chercher_google_maps", "navigation", "Rechercher sur Google Maps", [
        "cherche sur maps {requete}", "maps {requete}",
        "trouve {requete} sur la carte", "ou est {requete}",
    ], "browser", "navigate:https://www.google.com/maps/search/{requete}", ["requete"]),
]
