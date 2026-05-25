# infrastructure/scoring/bm25_scoring_service.py
"""
BM25ScoringService — перший шар scoring (pre-filter).

Юзкейс: прикордонна зона UA/HU/SK/RO.
  Мови корпусу: HU + SK + RO + EN (UA видалено).
  Тематики: тільки те що визначає міграційну, прикордонну,
  внутрішню і зовнішню політику країн регіону + армія + економіка.

НЕ входить у корпус:
  - спорт, культура, виставки, розваги
  - кримінальна хроніка без політичного контексту
  - місцеві новини без регіонального/міжнародного виміру

Теми (9 категорій):
  0. war_conflict          — армія, фронт, зброя, мобілізація
  1. politics_government   — вибори, уряд, президент, парламент, корупція
  2. foreign_policy_nato   — НАТО, ЄС, двосторонні відносини, саміти
  3. border_migration      — кордон, міграція, біженці, транзит, пропускний пункт
  4. economy_sanctions     — ВВП, санкції, торгівля, енергетика, бюджет
  5. security_intelligence — спецслужби, гібридна війна, шпигунство, тероризм
  6. minority_rights       — права меншин, мовний закон, автономія (HU↔UA/SK/RO контекст)
  7. humanitarian_warcrimes— воєнні злочини, біженці з UA, гуманітарна допомога
  8. cross_border_crime    — контрабанда, наркотики, зброя, ОЗГ, митниця

Бібліотека: rank_bm25 (pip install rank-bm25)
  Якщо недоступна — fallback на SimpleKeywordScoring.
"""
from __future__ import annotations

import logging
import re

import numpy as np

from src.application.ports.scoring_service import IScoringService
from src.domain.ingestion.value_objects import ParsedContent

logger = logging.getLogger(__name__)

# ─── Негативні ключові слова (відфільтровують нерелевантний контент) ──────────
# УВАГА: не додавати слова, які можуть з'являтися в корупційних/кримінально-
# політичних статтях (fraud, bribery тощо) — вони потраплять під penalty.
_NEGATIVE_KEYWORDS: list[str] = [
    # ── Спорт (матчі, турніри, результати) ──────────────────────────────────
    # EN
    "football", "soccer", "basketball", "tennis", "f1", "formula 1",
    "championship", "tournament", "olympics", "match", "athlete", "hockey",
    # HU
    "labdarúgás", "futball", "foci", "bajnokság", "mérkőzés", "olimpia",
    "sportoló", "jégkorong", "kézilabda", "vízilabda",
    # SK
    "futbal", "hokej", "zápas", "majstrovstvá", "turnaj", "olympiáda",
    "tenis", "športovec",
    # RO
    "fotbal", "meci", "campionat", "turneu", "jocurile olimpice",
    "sportiv", "baschet", "tenis",

    # ── Культура / Розваги (кіно, музика, виставки, шоу-бізнес) ─────────────
    # EN
    "concert", "cinema", "theater", "exhibition", "movie",
    "music", "art", "museum", "celebrity", "hollywood",
    # HU — "fesztivál" видалено: конфліктує з політичними фестивалями
    "koncert", "kiállítás", "színház", "mozi", "zene",
    "művészet", "múzeum", "film", "színész", "rendező",
    # SK — "festival" видалено з негативних: "festival demokracie" є релевантним
    "divadlo", "kino", "výstava", "umenie",
    "hudba", "múzeum", "herec",
    # RO
    "festivalul", "concert", "cinema", "teatru", "expoziție",
    "muzică", "artă", "muzeu", "actor", "spectacol",

    # ── Кримінал / ДТП без політики (побутові події) ─────────────────────────
    # Виключено: "fraud" / "podvod" / "fraudă" — занадто часто з'являються
    # в корупційних статтях (cat 1, cat 5) і спричиняють хибний penalty.
    # EN
    "robbery", "theft", "murder", "burglary", "homicide", "stabbing",
    "domestic violence", "car crash",
    # HU
    "rablás", "lopás", "gyilkosság", "betörés", "késelés",
    "baleset", "karambol", "bántalmazás", "halálos baleset",
    # SK
    "lúpež", "krádež", "vražda", "vlámanie", "napadnutie",
    "bodnutie", "nehoda", "havária", "dopravná nehoda",
    # RO
    "jaf", "furt", "crimă", "spargere", "omor", "înjunghiere",
    "accident rutier", "violență domestică",

    # ── Реклама / Прес-релізи / Комерція ────────────────────────────────────
    # EN
    "sponsored", "advertisement", "promo", "discount", "sale", "marketing",
    # HU
    "hirdetés", "reklám", "szponzorált", "akció", "kedvezmény", "promóció",
    # SK
    "reklama", "sponzorované", "zľava", "promócia", "inzercia",
    # RO
    "sponsorizat", "reclamă", "reducere", "promoție", "publicitate",

    # ── Геополітика поза регіоном (Велика Британія) ─────────────────────────
    # EN
    "britain", "british", "united kingdom", "keir starmer", "labour party",
    "reform uk", "nigel farage", "westminster", "rishi sunak",
    "tories", "conservative party",
    # HU
    "nagy-britannia", "brit", "egyesült királyság", "londoni",
    # SK
    "veľká británia", "britský", "spojené kráľovstvo",
    # RO
    "marea britanie", "britanic", "regatul unit",
]

# ── Буст-слова: якщо є — підняти score ───────────────────────────────────────
_BOOST_KEYWORDS: list[str] = [
    "ukraine", "ukrajna", "slovensko", "románia", "ungaria",
    "zelenskyy", "zelenski", "putin", "orban", "fico",
    "nato", "eu", "sanctions", "szankció", "sankcie", "sancțiuni",
    "românia", "mapn", "armata româniei",
    "vrtuľník", "vrtuľníky", "ministerstvo vnútra", "rezort vnútra", "mv sr",
    "apărării", "militari",
    "tulcea", "ismail", "ro-alert", "drone",
    "magyar", "péter", "anita", "varsó", "lengyelország",
    "röszke", "röszkei", "embercsempészés",
    "ficovi", "putinom",
    "kábítószer", "kábítószergyanús", "cigaretta", "csempészáru", "lefoglaltak",
    "delta program", "nyírbátor", "szabolcs", "kerítő", "drogdíler",
    "šimečka", "demokrati", "varšava",
    "vyhostenie", "vyhostili", "vyhostený",
    "sulyok", "novák", "kegyelmi", "vizsgálóbizottság", "sándor-palota",
    "safe", "programul safe", "înzestrare", "anti-dronă",
    "industria de apărare", "miliarde euro",
    
    
]

_NEGATIVE_PENALTY = 0.20   # зменшено: 0.35 було надто агресивним
_BOOST_BONUS      = 0.10   # додаємо, але не вище 1.0

# ─── Корпус тем ───────────────────────────────────────────────────────────────
_TOPIC_CORPUS_RAW: list[list[str]] = [

    # ── 0. war_conflict ───────────────────────────────────────────────────────
    # Армія, фронт, зброя, мобілізація — регіональний контекст (HU/SK/RO/EN).
    # Тут лише регіон UA/HU/SK/RO + базова військова лексика.
    # Глобальна геополітика (Африка, Азія) — не входить.
    [
        # EN
        "war", "conflict", "military", "army", "troops", "weapon", "missile",
        "strike", "attack", "drone", "artillery", "front line", "frontline",
        "offensive", "counteroffensive", "defense", "combat", "casualties",
        "mobilization", "conscription", "armored", "tank", "shelling",
        "occupation", "invasion", "ceasefire", "peacekeeping", "nato forces",
        "military aid", "arms supply", "ammunition", "air defense",
        "prisoner of war", "pow", "minefield", "fortification",
        "special operations", "military exercise", "interoperability",
        "shahed", "himars", "patriot system", "f-16", "leopard tank",
        "territorial defense", "volunteer battalion", "mercenary", "wagner group",
        "war fatigue", "frozen conflict", "demilitarized zone",

        # HU
        "háború", "konfliktus", "katoná", "hadsereg", "csapat", "fegyver",
        "rakéta", "támadás", "drón", "tüzérség", "frontvonat", "offenzíva",
        "védelm", "harci", "veszteség", "mozgósítás", "sorozás", "páncélos",
        "tank", "ágyúzás", "megszállás", "invázió", "tűzszünet", "békefenntartás",
        "katonai segély", "lőszer", "légvédelm", "hadifogoly",
        "honvédség", "kecskemét", "magyar honvédség", "hadgyakorlat",
        "nemzetközi együttműködés", "interoperabilitás",
        "területvédelem", "önkéntes zászlóalj", "zsoldos",
        "tűzszünet megsértése", "fegyverszállítás", "hadiállapot",
        "védelmi kiadások", "hadkötelezettség", "katonai kivonulás", "fegyverszünet",

        # SK
        "vojna", "konflikt", "vojenský", "armáda", "vojaci", "zbraň",
        "raketa", "útok", "dron", "delostrelectvo", "frontová línia",
        "ofenzíva", "obrana", "boj", "straty", "mobilizácia", "odvod",
        "obrnený", "tank", "ostreľovanie", "okupácia", "invázia",
        "prímerie", "mierové sily", "vojenská pomoc", "munícia",
        "protivzdušná obrana", "vojnový zajatec",
        "batéria", "cvičia", "cvičiť",
        "vrtuľník", "vrtuľníky", "letka", "modernizácia",
        "civilná ochrana", "európske fondy",

        # RO
        "război", "conflict", "militar", "armată", "trupe", "armă",
        "rachetă", "atac", "dronă", "artilerie", "linie de front",
        "ofensivă", "apărare", "luptă", "pierderi", "mobilizare",
        "recrutare", "blindat", "tanc", "bombardament", "ocupație",
        "invazie", "armistițiu", "menținerea păcii", "ajutor militar",
        "muniție", "apărare aeriană", "prizonier de război",
        "rezerviști", "rezervist", "exercițiu de mobilizare",
        "unitate militară", "poligon de tragere", "instruire militară",
        "apărare teritorială", "ministerul apărării naționale", "mapn",
        "pregătire pentru apărare", "apărare națională",
        "exercițiu militar", "soldați rezervă", "capacitate de apărare",
        "interoperabilitate", "forțe de rezervă", "armata româniei",
        "flancul estic", "statul major al apărării", "șef smap",
        "grup de luptă nato", "battle group", "artilerie caesar",
        "sisteme fără pilot", "comandă și control", "instruire întrunită",
        "instruire multinațională", "centru de instruire", "cincu", "getica",
        "dislocat", "dislocare", "capabilități militare", "foc real",
        "combaterea amenințărilor aeriene", "comandamentul corpului multinațional",
        "militari", "poligonul", "apărării", "forțelor", "aeriene",
        "aeronavă", "ruse", "atacuri", "drone", "aeronave",
        "radarele", "radar", "aeriană", "aerian", "alertare", "aliate",
        # ── Програма SAFE / модернізація / закупівлі ──────────────────────────────
        "programul safe", "program safe", "safe",
        "acțiunea pentru securitatea europei",
        "înzestrare", "înzestrarea armatei",
        "modernizare armată", "modernizarea armatei",
        "achiziții de apărare", "achiziții comune",
        "achiziții individuale",
        "industria națională de apărare", "industria de apărare",
        "capabilități de apărare aeriană",
        "sisteme moderne de apărare antiaeriană",
        "apărare antiaeriană",
        "tehnologii anti-dronă", "anti-dronă",
        "protejarea infrastructurii critice",
        "reziliența societății",
        "amenințări emergente",
        "context de securitate",
        "proiecte de înzestrare",
        "cooperare industrială", "cooperare tehnologică",
        "capacități defensive",
    ],

    # ── 1. politics_government ────────────────────────────────────────────────
    # Вибори, уряд, президент, парламент, корупція — внутрішня політика.
    # Військові теми (зброя, системи) перенесені до cat 0.
    [
        # EN
        "election", "vote", "ballot", "president", "prime minister",
        "parliament", "government", "minister", "party", "coalition",
        "opposition", "corruption", "scandal", "resignation", "reform",
        "legislation", "law", "decree", "veto", "referendum",
        "democracy", "authoritarianism", "rule of law", "judicial",
        "constitutional", "political crisis", "protest", "demonstration",
        "press freedom", "civil society",

        # HU
        "választás", "szavazat", "elnök", "miniszterelnök", "parlament",
        "kormány", "miniszter", "párt", "koalíció", "ellenzék",
        "korrupció", "botrány", "lemondás", "reform", "jogszabály",
        "törvény", "rendelet", "vétó", "népszavazás", "demokrácia",
        "tekintélyelvűség", "jogállamiság", "bírói", "alkotmányos",
        "politikai válság", "tüntetés", "sajtószabadság",
        "mandátum", "mandátumok", "százalék",
        "eredmény", "választási eredmény", "feldolgozottság",
        "lista", "országos lista",
        "győzelem", "kétharmad", "többség", "fidesz", "tisza párt", "mi hazánk",
        "kormánypárt", "mandátumeloszlás", "parlamenti többség",
        "kormányalakítás", "frakció",
        "szuverenista", "békepárti", "háborúpárti",
        "nemzeti konzultáció", "rezsicsökkentés",
        "miniszterelnökkel", "miniszterelnökre", "külügyminiszter",
        "tiszás", "politikus",
        "Tisza", "Tisza Párt", "kormányfő", "államfő",
        "átmeneti kormány", "új kormány", "Tisza-kormány",
        # ── Kegyelmi ügy / Novák-botrány ──────────────────────────────────────────
        "kegyelmi ügy", "kegyelmi döntés", "kegyelmi kérelem", "kegyelmet adott",
        "kegyelem megadása", "kegyelem megtagadása", "kegyelmi előterjesztés",
        "köztársasági elnök", "köztársasági elnöki", "elnöki kegyelem",
        "Sándor-palota", "sandor palota",
        "Novák Katalin", "novák katalin", "novak katalin",
        "Sulyok Tamás", "sulyok tamás",
        "Varga Judit", "varga judit",
        "igazságügyi miniszter", "igazságügyi minisztérium",
        "ellenjegyzés", "ellenjegyző",
        "parlamenti vizsgálóbizottság", "vizsgálóbizottság",
        "lemondás", "lemondott",
        "pedofil", "pedofília", "gyermekotthon", "bicskei gyermekotthon",
        "K. Endre", "kegyelmi botrány",
        "közzétette a dokumentumokat", "hivatalos iratok",
        "Alkotmányossági és Jogi Igazgatóság",
        "kabinetfőnök",
        "pápalátogatás", "pápai kegyelem",
        "közérdeklődés", "politikai botrány",

        # SK
        "voľby", "hlasovanie", "prezident", "predseda vlády", "parlament",
        "vláda", "minister", "strana", "koalícia", "opozícia",
        "korupcia", "škandál", "demisia", "reforma", "zákon",
        "dekrét", "veto", "referendum", "demokracia", "autoritarizmus",
        "právny štát", "súdny", "ústavný", "politická kríza",
        "protest", "sloboda tlače",
        "percent", "výsledky volieb", "spracovanosť", "kandidátska listina",
        "parlamentná väčšina", "koaličná dohoda",
        "smer", "progresívne slovensko", "hlas", "republika",
        "kresťanskodemokratické", "opozičný líder",
        "zostavovanie vlády", "poslanecký klub", "dôvera vláde",
        "matovič", "igor matovič", "hnutie slovensko", "oľano",
        "poslanec", "poslanci", "národná rada", "nrsr",
        "parlamentná schôdza", "zákonodarca",
        "sas", "sloboda a solidarita", "branislav gröhling", "veronika remišová",
        "za ľudí", "uznesenie", "prenasledovanie opozície",
        "kaliňák", "kaliňáka",
        "politik", "politici", "demokratického", "demokratický",
        "šimečka", "michal šimečka", "demokrati",
        "richard sulík",

        # RO
        "alegeri", "vot", "președinte", "prim-ministru", "parlament",
        "guvern", "ministru", "partid", "coaliție", "opoziție",
        "corupție", "scandal", "demisie", "reformă", "lege",
        "decret", "veto", "referendum", "democrație", "autoritarism",
        "statul de drept", "judiciar", "constituțional", "criză politică",
        "protest", "libertatea presei",
        "procent", "rezultate alegeri", "procesare voturi", "listă de candidați",
        "majoritate parlamentară", "acord de coaliție",
        "psd", "pnl", "usr", "aur",
        "formare guvern", "grup parlamentar", "moțiune de cenzură",
        "vot de încredere",
    ],

    # ── 2. foreign_policy_nato_eu ─────────────────────────────────────────────
    # НАТО, ЄС, двосторонні відносини, саміти, зовнішня політика
    [
        # EN
        "nato", "european union", "eu", "european council", "summit",
        "foreign policy", "diplomacy", "ambassador", "bilateral",
        "treaty", "agreement", "alliance", "accession", "membership",
        "sanctions", "g7", "g20", "un", "united nations",
        "security council", "transatlantic", "enlargement",
        "european commission", "eu funding", "cohesion fund",
        "strategic partnership", "defense cooperation",
        "article 5", "collective defense",
        "veto", "blocking", "hungary veto", "rule of law conditionality",
        "frozen eu funds", "china relations", "belt and road",
        "neutrality", "peace talks", "mediation", "orban", "fico",
        "eu article 7", "democratic backsliding",

        # HU
        "nato", "európai unió", "eu", "európai tanács", "csúcstalálkozó",
        "külpolitika", "diplomácia", "nagykövet", "kétoldalú",
        "szerződés", "megállapodás", "szövetség", "csatlakozás",
        "tagság", "szankciók", "ensz", "biztonsági tanács",
        "transzatlanti", "bővítés", "európai bizottság",
        "uniós finanszírozás", "stratégiai partnerség",
        "védelmi együttműködés", "kollektív védelem",
        "vétó", "uniós alapok befagyasztása", "jogállamisági feltételrendszer",
        "kínai kapcsolatok", "semlegesség", "béketárgyalások",
        "közvetítés", "keleti nyitás", "szuverenitásvédelem",
        "magyarország-oroszország kapcsolat",
        "nagykövetét", "nagykövetet", "nagykövete", "nagykövetség",
        "varsói", "varsóba", "lengyel", "hazarendeli", "diplomáciáért",
        "kapcsolat", "kapcsolatok", "találkozó",
        "hivatalos látogatás", "protokoll látogatás",
        "kétoldalú találkozó", "bilaterális találkozó",
        "uniós források", "uniós pénzek", "kohéziós alap", "helyreállítási alap",
        "visegrádi együttműködés", "V4", "visegrád", "brüsszeli egyeztetés",
        "tárgyalások az uniós forrásokról",

        # SK
        "nato", "európska únia", "eú", "európska rada", "samit",
        "zahraničná politika", "diplomacia", "veľvyslanec", "bilaterálny",
        "zmluva", "dohoda", "aliancia", "pristúpenie", "členstvo",
        "sankcie", "osn", "bezpečnostná rada", "transatlantický",
        "rozšírenie", "európska komisia", "fondy eú",
        "strategické partnerstvo", "obranná spolupráca",
        "veto", "zmrazené fondy eú", "neutralita", "mierové rokovania",
        "fico-orban", "slovensko-ruské vzťahy", "čínske investície",
        "fico", "robert fico", "putin", "vladimir putin", "moskva", "rusko",
        "kremeľ", "ruská federácia", "rokovanie", "stretnutie",
        "bilaterálna spolupráca", "ušakov", "jurij ušakov",
        "západné sankcie", "európske obmedzenia",
        "spojenci", "jednotný postoj",
        "poľského", "poľský", "poľsko", "sejm", "sejmu",
        "bratislave", "bratislava", "varšava",
        "číny", "čínskej", "čínou", "čínu", "pekingu", "si ťin-pchinga",
        "partnerstva", "spolupráca", "spoluprácu",
        "investičné", "investície", "obchodným", "partnerom",
        "inobat", "gotion", "volvo", "geely", "baterkáreň",
        "vyhostenie", "vyhostili", "vyhostený veľvyslanec",
        "diplomatický incident", "provokácia", "protest nóta",
        "predvolanie veľvyslanca", "persona non grata",
        "varšavský",

        # RO
        "nato", "uniunea europeană", "ue", "consiliul european", "summit",
        "politică externă", "diplomație", "ambasador", "bilateral",
        "tratat", "acord", "alianță", "aderare",
        "sancțiuni", "onu", "consiliul de securitate", "transatlantic",
        "extindere", "comisia europeană", "fonduri ue",
        "parteneriat strategic", "cooperare în apărare",
        "veto", "fonduri ue blocate", "neutralitate", "negocieri de pace",
        "relații cu rusia", "investiții chineze", "parcurs european",
        "cooperare cu aliații", "structuri aliate", "vizită oficială nato",
        "interoperabilitate", "rol strategic",
        "comandamentul nato", "amiral", "șef stat major",
        "sibiu nato", "apărare colectivă românia",
        "comitetul militar al nato", "flancul estic",
        # ── Finanțare UE pentru apărare ───────────────────────────────────────────
        "programul safe", "acțiunea pentru securitatea europei",
        "acord de finanțare", "acord de finanțare ue",
        "comisia europeană apărare",
        "finanțare apărare", "finanțare europeană apărare",
        "principal beneficiar", "beneficiar safe",
        "ratificarea acordului", "ratificare parlament",
        "cooperare industrială europeană",
        "cooperare tehnologică europeană",
        "state membre apărare",
    ],

    # ── 3. border_migration ───────────────────────────────────────────────────
    # Кордон, міграція, біженці, транзит, пропускний пункт — КЛЮЧОВА тема
    [
        # EN
        "border", "border crossing", "checkpoint", "migration", "migrant",
        "refugee", "asylum", "asylum seeker", "transit", "smuggling",
        "human trafficking", "irregular migration", "frontex",
        "border guard", "border control", "entry ban", "visa",
        "residence permit", "deportation", "expulsion",
        "internally displaced", "idp", "shelter", "reception center",
        "border fence", "push back", "border incident",
        "ukrainian refugees", "refugee camp",
        "draft evasion", "military desertion", "border evasion",
        "zakarpattia border", "uzhorod crossing", "chop border",
        "berehove crossing", "tibava crossing", "košice corridor",
        "men of military age", "travel ban ukraine",
        "border queue", "crossing time",

        # HU
        "határ", "határátkelő", "ellenőrzőpont", "migráció", "migráns",
        "menekült", "menedékjog", "menedékkérő", "tranzit", "csempészet",
        "emberkereskedelem", "illegális bevándorlás", "frontex",
        "határőr", "határellenőrzés", "belépési tilalom", "vízum",
        "tartózkodási engedély", "deportálás", "kiutasítás",
        "belső menekült", "szállás", "befogadóközpont",
        "határkerítés", "visszatoloncolás", "határincidens",
        "ukrán menekültek", "menekülttábor",
        "katonai szökevény", "mozgósítás elől menekülő",
        "záhony átkelő", "beregsurány átkelő",
        "katonaköteles férfiak", "ukrajna utazási tilalom",
        "határvárakozás", "átkelési idő", "illegális határátlépés",
        "határrendészet", "határrendészeti", "határrendészek",
        "határátkelőhelyen", "határsértőt", "határsértő",
        "illegális belépésben", "embercsempészés", "tiltott határátlépés",
        "kilépésre",

        # SK
        "hranica", "hraničný priechod", "kontrolný bod", "migrácia",
        "migrant", "utečenec", "azyl", "žiadateľ o azyl", "tranzit",
        "pašovanie", "obchodovanie s ľuďmi", "nelegálna migrácia",
        "frontex", "pohraničná stráž", "hraničná kontrola",
        "zákaz vstupu", "vízum", "povolenie na pobyt", "deportácia",
        "vysťahovanie", "vnútorne vysídlená osoba", "ubytovanie",
        "prijímacie centrum", "hraničný plot", "pushback",
        "hraničný incident", "ukrajinskí utečenci",
        "únik pred mobilizáciou", "vojenský dezertér",
        "užhorodský priechod", "vyšné nemecké priechod",
        "vojaci v úteku", "zákaz vycestovania ukrajina",
        "čakacia doba na hranici",

        # RO
        "frontieră", "punct de trecere", "punct de control", "migrație",
        "migrant", "refugiat", "azil", "solicitant de azil", "tranzit",
        "contrabandă", "trafic de persoane", "migrație ilegală",
        "frontex", "poliția de frontieră", "control la frontieră",
        "interdicție de intrare", "viză", "permis de ședere",
        "deportare", "expulzare", "persoană strămutată intern",
        "adăpost", "centru de primire", "gard la frontieră",
        "refuzare la frontieră", "incident la frontieră",
        "refugiați ucraineni",
        "evaziune de la mobilizare", "dezertor militar",
        "punctul siret", "punctul isaccea", "punctul porubne",
        "bărbați de vârstă militară", "interdicție de călătorie ucraina",
        "frontierei", "fluviale", "tulcea", "ismail",
    ],

    # ── 4. economy_energy_sanctions ───────────────────────────────────────────
    # ВВП, санкції, торгівля, енергетика, бюджет — економіка регіону.
    # Кожна мова в окремому блоці — не змішувати.
    [
        # EN
        "economy", "gdp", "inflation", "budget", "debt", "deficit",
        "investment", "trade", "export", "import", "market",
        "sanctions", "embargo", "tariff", "supply chain",
        "energy", "gas", "oil", "electricity", "nuclear power",
        "pipeline", "lng", "energy crisis", "energy security",
        "imf", "world bank", "eu funds", "reconstruction",
        "financial aid", "currency", "exchange rate", "recession",
        "unemployment", "wage", "subsidy",
        "via carpatia", "rail baltica", "three seas initiative",
        "food prices", "fuel price", "energy subsidy", "winter heating",
        "gas storage", "lng terminal", "nuclear expansion", "paks",
        "household energy", "energy poverty", "carbon tax",
        "cohesion policy", "structural funds", "recovery fund",

        # HU
        "gazdaság", "gdp", "infláció", "költségvetés", "adósság",
        "hiány", "befektetés", "kereskedelem", "export", "import",
        "piac", "szankciók", "embargó", "vám", "ellátási lánc",
        "energia", "gáz", "olaj", "villamos energia", "atomerőmű",
        "csővezeték", "lng", "energiaválság", "energiabiztonság",
        "imf", "világbank", "uniós alapok", "újjáépítés",
        "pénzügyi segély", "valuta", "árfolyam", "recesszió",
        "munkanélküliség", "bér", "támogatás",
        "Paks2", "atomenergia bővítés", "rezsicsökkentés",
        "gázárak", "üzemanyagárak", "energiaszegénység",
        "téli fűtés", "gáztározás", "helyreállítási alap",
        "kohéziós politika", "strukturális alapok", "Via Carpatia",
        "uniós forrás", "uniós támogatás", "kohéziós források",

        # SK
        "ekonomika", "hdp", "inflácia", "rozpočet", "dlh",
        "deficit", "investícia", "obchod", "export", "import",
        "trh", "sankcie", "embargo", "clo", "dodávateľský reťazec",
        "energia", "plyn", "ropa", "elektrina", "jadrová elektráreň",
        "plynovod", "lng", "energetická kríza", "energetická bezpečnosť",
        "mmf", "svetová banka", "fondy eú", "obnova",
        "finančná pomoc", "mena", "výmenný kurz", "recesia",
        "nezamestnanosť", "mzda", "dotácia",
        "jadrová energia", "ceny plynu", "ceny pohonných hmôt",
        "energetická chudoba", "zimné kúrenie", "zásobníky plynu",
        "fond obnovy", "kohézna politika",
        "gazprom", "spp", "slovenský plynárenský priemysel",
        "ropovod družba", "transnefť", "transpetrol",
        "dodávky plynu", "dodávky ropy", "dodávky energie",

        # RO
        "economie", "pib", "inflație", "buget", "datorie",
        "deficit", "investiție", "comerț", "export", "import",
        "piață", "sancțiuni", "embargo", "tarif", "lanț de aprovizionare",
        "energie", "gaze", "petrol", "electricitate", "centrală nucleară",
        "conductă", "lng", "criză energetică", "securitate energetică",
        "fmi", "banca mondială", "fonduri ue", "reconstrucție",
        "ajutor financiar", "monedă", "curs de schimb", "recesiune",
        "șomaj", "salariu", "subvenție",
        "energie nucleară", "prețuri gaze", "prețuri combustibil",
        "sărăcie energetică", "încălzire iarnă", "depozite gaz",
        "fond de redresare", "politică de coeziune", "Via Carpatia",
    ],

    # ── 5. security_intelligence_hybrid ──────────────────────────────────────
    # Спецслужби, гібридна війна, шпигунство, тероризм, кібер
    [
        # EN
        "intelligence", "secret service", "counterintelligence",
        "hybrid war", "hybrid warfare", "espionage", "spy",
        "sabotage", "terrorism", "terrorist",
        "cyberattack", "critical infrastructure", "information warfare",
        "propaganda", "disinformation", "influence operation",
        "fsb", "gru", "cia", "counterterrorism",
        "surveillance", "wiretapping", "covert operation",
        "false flag", "asymmetric warfare",
        "russian agent", "foreign agent law", "ngo crackdown",
        "media capture", "state capture", "oligarch", "kleptocracy",
        "money laundering", "illicit finance", "dark money",
        "pegasus spyware", "phone surveillance", "signal intercept",
        "election interference", "voter manipulation",

        # HU
        "hírszerzés", "titkosszolgálat", "kémelhárítás",
        "hibrid háború", "kémkedés", "kém", "szabotázs",
        "terrorizmus", "terrorista", "kibertámadás",
        "kritikus infrastruktúra", "információs hadviselés",
        "propaganda", "dezinformáció", "befolyásolási művelet",
        "elhárítás", "lehallgatás", "fedett művelet",
        "orosz ügynök", "külföldi ügynök törvény", "állami médiakapture",
        "oligarcha", "pénzmosás", "Pegasus kémprogram",
        "választási manipuláció", "médiabefolyásolás",
        "lőfegyver", "lőfegyverrel", "maroklőfegyvert", "fegyvereket",

        # SK
        "spravodajstvo", "tajná služba", "kontrarozviedka",
        "hybridná vojna", "špionáž", "špión", "sabotáž",
        "terorizmus", "terrorist", "kybernetický útok",
        "kritická infraštruktúra", "informačná vojna",
        "propaganda", "dezinformácia", "vplyvová operácia",
        "protiteroristický", "odpočúvanie", "tajná operácia",
        "ruský agent", "zákon o zahraničných agentoch", "médiakaptura",
        "oligarcha", "pranie peňazí", "Pegasus spyware",
        "volebná manipulácia", "hybridné útoky", "extrémizmus",
        "obliali krvou", "fyzický útok na politika",
        "provokatívny čin", "útok na opozíciu",
        "ruská provokácia", "hybridná provokácia",

        # RO
        "informații", "servicii secrete", "contrainformații",
        "război hibrid", "spionaj", "spion", "sabotaj",
        "terorism", "terorist", "atac cibernetic",
        "infrastructură critică", "război informațional",
        "propagandă", "dezinformare", "operațiune de influență",
        "contraterorism", "interceptare", "operațiune acoperită",
        "agent rus", "lege privind agenții străini", "captură media",
        "oligarh", "spălare de bani", "spyware Pegasus",
        "manipulare electorală",
    ],

    # ── 6. minority_rights_regional ───────────────────────────────────────────
    # Права меншин, мовний закон, автономія — специфіка HU↔UA/SK/RO
    [
        # EN
        "minority rights", "ethnic minority", "hungarian minority",
        "romanian minority", "slovak minority", "language law",
        "autonomy", "self-governance", "cultural rights",
        "mother tongue", "minority language", "discrimination",
        "dual citizenship", "passport", "diaspora",
        "transylvania", "transcarpathia", "zakarpattia",
        "southern slovakia", "székely",
        "minority school", "minority education",
        "language law ukraine", "ukrainian language policy",
        "kmksz", "umdsz", "hungarian passport zakarpattia",
        "minority veto", "territorial autonomy", "szeklerland",
        "covasna harghita mures", "vojvodina", "ruthenian minority",
        "subcarpathian ruthenians", "berehove", "uzhhorod",
        "mukachevo hungarian", "minority quota", "minority mp",

        # HU
        "kisebbségi jogok", "etnikai kisebbség", "magyar kisebbség",
        "román kisebbség", "szlovák kisebbség", "nyelvtörvény",
        "autonómia", "önkormányzat", "kulturális jogok",
        "anyanyelv", "kisebbségi nyelv", "diszkrimináció",
        "kettős állampolgárság", "útlevél", "diaszpóra",
        "erdély", "kárpátalja", "felvidék", "székelyek",
        "kisebbségi iskola", "kisebbségi oktatás",
        "ukrajna nyelvtörvénye", "KMKSZ", "UMDSZ",
        "kárpátaljai magyarok", "beregszász", "ungvár", "munkács",
        "magyar útlevél kárpátalján", "területi autonómia",
        "székelyföldi autonómia", "Covasna", "Hargita", "Maros megye",
        "kisebbségi kvóta", "kisebbségi képviselő", "Ruszin kisebbség",

        # SK
        "práva menšín", "etnická menšina", "maďarská menšina",
        "rumunská menšina", "jazykový zákon", "autonómia",
        "samospráva", "kultúrne práva", "materinský jazyk",
        "menšinový jazyk", "diskriminácia", "dvojité občianstvo",
        "pas", "diaspora", "transylvánia", "zakarpatsko",
        "južné slovensko", "menšinová škola", "menšinové vzdelávanie",
        "jazykový zákon ukrajiny", "maďarská menšina na slovensku",
        "SMK", "Most-Híd", "maďarský pas na slovensku",
        "južné slovensko maďari", "dvojjazyčné tabule",

        # RO
        "drepturile minorităților", "minoritate etnică",
        "minoritate maghiară", "minoritate slovacă", "lege lingvistică",
        "autonomie", "autoguvernare", "drepturi culturale",
        "limbă maternă", "limbă minoritară", "discriminare",
        "dublă cetățenie", "pașaport", "diaspora",
        "transilvania", "transcarpatia", "secui",
        "școală pentru minorități", "educație pentru minorități",
        "legea lingvistică ucraina", "UDMR", "pașaport maghiar românia",
        "ardeal", "secuime", "autonomie teritorială",
        "maghiari din transilvania", "bilingvism",
    ],

    # ── 7. humanitarian_warcrimes_aid ─────────────────────────────────────────
    # Воєнні злочини, біженці з UA, гуманітарна допомога, МКС
    [
        # EN
        "war crimes", "crimes against humanity", "genocide",
        "icc", "international criminal court", "tribunal",
        "deportation", "torture", "massacre", "civilian casualties",
        "humanitarian aid", "humanitarian corridor", "evacuation",
        "displaced persons", "shelter", "food aid", "medical aid",
        "reconstruction aid", "donor conference",
        "unhcr", "icrc", "red cross", "ngo", "relief organization",
        "accountability", "justice", "atrocity", "human rights violation",
        "child deportation", "stolen children", "filtration camp",
        "russian asset seizure", "frozen assets", "reparations",
        "reconstruction fund", "marshall plan ukraine",
        "sexual violence war", "rape as weapon",
        "mine clearance", "demining", "ecocide",
        "hospital bombing", "school bombing", "cultural heritage destruction",

        # HU
        "háborús bűnök", "emberiesség elleni bűnök", "népirtás",
        "nbn", "nemzetközi büntetőbíróság", "törvényszék",
        "deportálás", "kínzás", "mészárlás", "civil áldozatok",
        "humanitárius segély", "humanitárius folyosó", "evakuáció",
        "kitelepített személyek", "menedék", "élelmiszersegély",
        "orvosi segítség", "újjáépítési segély",
        "unhcr", "vöröskereszt", "civil szervezet", "elszámoltathatóság",
        "gyerekdeportálás", "elrabolt gyerekek", "orosz vagyon lefoglalása",
        "jóvátétel", "ukrán újjáépítési alap", "aknamentesítés",
        "ökocídium", "kórházbombázás",

        # SK
        "vojnové zločiny", "zločiny proti ľudskosti", "genocída",
        "mts", "medzinárodný trestný súd", "tribunál",
        "deportácia", "mučenie", "masaker", "civilné obete",
        "humanitárna pomoc", "humanitárny koridor", "evakuácia",
        "vysídlené osoby", "útočisko", "potravinová pomoc",
        "zdravotnícka pomoc", "pomoc pri obnove",
        "unhcr", "červený kríž", "mimovládna organizácia", "zodpovednosť",
        "deportácia detí", "ukradnuté deti", "zaistenie ruských aktív",
        "reparácie", "fond obnovy ukrajiny", "odminovanie",
        "vojnový zločinec", "agresívna vojna",

        # RO
        "crime de război", "crime împotriva umanității", "genocid",
        "cpi", "curtea penală internațională", "tribunal",
        "deportare", "tortură", "masacru", "victime civile",
        "ajutor umanitar", "coridor umanitar", "evacuare",
        "persoane strămutate", "adăpost", "ajutor alimentar",
        "ajutor medical", "ajutor pentru reconstrucție",
        "unhcr", "crucea roșie", "ong", "responsabilitate", "justiție",
        "deportarea copiilor", "copii furați", "confiscarea activelor rusești",
        "reparații", "fond de reconstrucție ucraina", "deminare", "ecocid",
    ],

    # ── 8. cross_border_crime_smuggling ──────────────────────────────────────
    # Транскордонна злочинність, контрабанда (сигарети, наркотики, зброя),
    # митниця, ОЗГ.
    # Ця категорія є винятком з логіки негативних слів: "krádež", "vražda"
    # тут нерелевантні, але "pašovanie", "drogy", "csempészet" — в ядрі.
    # neg_hits-поріг для цієї категорії обробляється окремо в score().
    [
        # EN
        "smuggling", "contraband", "trafficking", "organized crime",
        "illicit goods", "drug seizure", "customs", "cartel", "narcotics",
        "counterfeit", "illicit tobacco", "border patrol bust", "illegal goods",
        "confiscated", "seized",

        # HU
        "csempészet", "csempészáru", "embercsempész", "kábítószer",
        "cigarettacsempészet", "kábítószer-kereskedelem", "bűnszervezet",
        "bűnbanda", "vámosok", "vámhivatal", "lefoglaltak", "illegális áru",
        "kábítószergyanús", "drogfogás", "zárjegy nélküli", "razzia",
        "díler", "drogdíler", "crack", "heroin", "metamfetamin",
        "kerítés", "kerítő", "prostitúció", "emberkereskedelem",
        "nők kizsákmányolása", "DELTA Program", "delta program",
        "Nyírbátor", "nyírbátori", "Szabolcs", "szabolcsi",
        "őrizetbe", "letartóztatták", "gyanúsított", "nyomozók",
        "rendőrkapitányság", "rendőrfőkapitányság",

        # SK
        "pašovanie", "kontraband", "pašerák", "drogy", "cigarety",
        "organizovaný zločin", "zhabaný", "colníci", "colný úrad",
        "nelegálny tovar", "pašované", "kokaín", "marihuana", "zadržali",

        # RO
        "contrabandă", "trafic", "traficant", "droguri", "țigări de contrabandă",
        "crimă organizată", "bunuri ilicite", "captură", "vameși", "vamă",
        "mărfuri de contrabandă", "confiscat", "stupefiante", "grupare infracțională",
    ],
]

_BM25_MAX_SCORE = 8.0

# Індекс категорії cross_border_crime — для пом'якшення neg_hits-порогу
_CAT_CROSS_BORDER_CRIME = 8


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    tokens = re.split(r"[\s\W]+", text)
    return [t for t in tokens if len(t) > 2]


class BM25ScoringService(IScoringService):
    """
    IScoringService через BM25 без geo-фільтрації.

    Корпус: 9 тем × 4 мови (HU/SK/RO/EN).
    Без UA — система орієнтована на регіональні медіа HU/SK/RO
    та англомовні джерела про регіон.

    ParsedContent.language НЕ використовується —
    корпус сам покриває всі 4 мови.
    """

    def __init__(self, max_score: float = _BM25_MAX_SCORE) -> None:
        self._max_score = max_score
        self._bm25 = self._build_bm25()

    def _build_bm25(self):
        try:
            from rank_bm25 import BM25Okapi
            self._backend = "rank_bm25"
            return BM25Okapi(_TOPIC_CORPUS_RAW)
        except ImportError:
            self._backend = "simple"
            return None

    async def score(self, content: ParsedContent) -> float:
        text = content.full_text()
        if not text:
            return 0.0

        if self._backend == "simple":
            raw_score = self._simple_score(text)
        else:
            raw_score = self._bm25_score(text)

        text_lower = text.lower()

        # ── Визначаємо найкращу категорію ────────────────────────────────────
        best_cat = self._best_category(text_lower)

        # ── Антислова ─────────────────────────────────────────────────────────
        neg_hits = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in text_lower)

        # Для cat 8 (cross_border_crime) поріг вищий: кримінальна лексика
        # є частиною теми, тому не відхиляємо при 2 хітах.
        neg_reject_threshold = 4 if best_cat == _CAT_CROSS_BORDER_CRIME else 2

        if neg_hits >= neg_reject_threshold:
            logger.info(
                "BM25: negative keyword reject (hits=%d, threshold=%d, cat=%d)",
                neg_hits, neg_reject_threshold, best_cat,
            )
            return 0.0

        if neg_hits == 1:
            raw_score = max(0.0, raw_score - _NEGATIVE_PENALTY)

        # ── Буст-слова ────────────────────────────────────────────────────────
        boost_hits = sum(1 for kw in _BOOST_KEYWORDS if kw in text_lower)
        if boost_hits > 0:
            raw_score = min(1.0, raw_score + _BOOST_BONUS * min(boost_hits, 3))

        logger.info(
            "BM25: score=%.3f neg_hits=%d boost_hits=%d best_cat=%d",
            raw_score, neg_hits, boost_hits, best_cat,
        )
        return raw_score

    def _best_category(self, text_lower: str) -> int:
        """Повертає індекс категорії з найвищим BM25-score для тексту."""
        if self._backend == "rank_bm25":
            tokens = _tokenize(text_lower)
            if not tokens:
                return 0
            scores = self._bm25.get_scores(tokens)
            return int(np.argmax(scores))
        # fallback: проста перевірка
        best, best_idx = 0, 0
        for i, keywords in enumerate(_TOPIC_CORPUS_RAW):
            hits = sum(1 for kw in keywords if kw in text_lower)
            if hits > best:
                best, best_idx = hits, i
        return best_idx

    def _bm25_score(self, text: str) -> float:
        tokens = _tokenize(text)
        if not tokens:
            return 0.0

        scores = self._bm25.get_scores(tokens)
        raw = float(np.max(scores))
        normalized = min(raw / self._max_score, 1.0)

        logger.debug(
            "BM25: raw_max=%.3f normalized=%.3f best_topic=%d tokens=%d",
            raw, normalized, int(np.argmax(scores)), len(tokens),
        )
        return normalized

    def _simple_score(self, text: str) -> float:
        """Fallback без rank_bm25 — простий підрахунок тем."""
        text_lower = text.lower()
        matched = 0
        for keywords in _TOPIC_CORPUS_RAW:
            pattern = re.compile(
                r"(?:" + "|".join(re.escape(kw) for kw in keywords) + r")"
            )
            if pattern.search(text_lower):
                matched += 1
        # Нормалізація сумісна з BM25: хоча б 2 теми = score ~0.5
        return min(matched / max(len(_TOPIC_CORPUS_RAW) / 2, 1), 1.0)

    def calibrate_max_score(self, sample_texts: list[str]) -> float:
        """
        Утиліта для калібрування _BM25_MAX_SCORE.
        Запусти на кількох еталонних статтях щоб знайти реальний max.
        Автоматично оновлює self._max_score.
        """
        if self._backend != "rank_bm25":
            return self._max_score

        max_raw = 0.0
        for text in sample_texts:
            tokens = _tokenize(text)
            if not tokens:
                continue
            scores = self._bm25.get_scores(tokens)
            max_raw = max(max_raw, float(np.max(scores)))

        logger.info("Calibrated BM25 max score: %.2f (was %.2f)", max_raw, self._max_score)
        self._max_score = max_raw  # виправлено: тепер застосовується
        return max_raw