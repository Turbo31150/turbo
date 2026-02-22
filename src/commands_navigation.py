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
]
