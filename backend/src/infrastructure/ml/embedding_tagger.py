# infrastructure/ml/embedding_tagger.py
"""
EmbeddingTagger — zero-shot тегер на основі cosine similarity.

[ОНОВЛЕНО] Gap-based tag selection замість flat threshold.

Проблема flat threshold (0.40):
  Multilingual-e5 на текстах про NATO/politics/diplomacy/war дає scores:
    war=0.71, politics=0.68, diplomacy=0.65, society=0.58, economy=0.52,
    humanitarian=0.48, crime=0.43, energy=0.41, technology=0.40
  Всі 9 тегів вище 0.40 → assigned. Але стаття про одне-два з них.

Рішення: два механізми разом:

1. MIN_ABSOLUTE_THRESHOLD (0.45):
   Жорсткий floor — теги нижче цього ніколи не присвоюються.
   Прибирає явний шум (technology для статті про NATO).

2. Gap-based selection (MAX_TAGS_PER_ARTICLE + gap):
   Після фільтрації за floor — беремо top-K і шукаємо "розрив".
   Якщо між тегом N і тегом N+1 різниця >= GAP_THRESHOLD (0.08) → стоп.
   Це відокремлює "справжні" теги від "схожих за моделлю".

   Приклад (стаття про NATO без HU контексту):
     Scores після floor:
       diplomacy=0.72, politics=0.68, war=0.61, society=0.52, economy=0.49
     Gaps:
       diplomacy→politics: 0.04 (маленький, обидва)
       politics→war:       0.07 (маленький, всі три)
       war→society:        0.09 ← >= GAP_THRESHOLD → стоп!
     Результат: ["diplomacy", "politics", "war"] ✓ (не всі 5)

3. MAX_TAGS_PER_ARTICLE (4):
   Hard cap — ніколи більше 4 тегів незалежно від gaps.
   "Все важливе" = "нічого важливого".

Конфігурація:
  MIN_ABSOLUTE_THRESHOLD = 0.45  # floor
  GAP_THRESHOLD          = 0.08  # розрив між сусідніми тегами → стоп
  MAX_TAGS_PER_ARTICLE   = 4     # hard cap
  MIN_TAGS_SCORE_FOR_ONE = 0.55  # якщо тільки 1 тег — він має бути впевненим

Теги і їх семантичні описи:
  Описи навмисно РІЗНІ щоб мінімізувати cross-tag overlap.
  Важливо: НЕ дублювати слова між тегами — модель тоді краще розрізняє.
"""
from __future__ import annotations

import logging

import numpy as np

from src.infrastructure.ml.embedder import Embedder

logger = logging.getLogger(__name__)


# ─── Словник тегів ────────────────────────────────────────────────────────────
# ВАЖЛИВО: описи навмисно не перекриваються між собою.
# "war" не містить "politics", "diplomacy" не містить "military".
# Це ключово для gap-based selection — якщо описи однакові,
# модель дає однакові scores і gap не виникає.

TAG_DESCRIPTIONS: dict[str, str] = {
    "war": (
        # Фокус: бойові дії, зброя, фізичне насильство, лінія фронту
        # EN — тактика, зброя, оперативні терміни
        "armed combat frontline battlefield troops soldiers weapons missiles drones artillery shelling"
        " infantry armored column tank assault offensive defensive maneuver ceasefire"
        " air strike cruise missile HIMARS cluster munition mine sniper casualty POW"
        " occupation siege encirclement retreat advance reinforcement mobilization"
        " military operation special operation naval attack kamikaze drone FPV"
        # UA — ЗСУ, фронт, зброя, події
        " бойові дії фронт зброя снаряди ракети дрони обстріл ЗСУ окупація атака"
        " наступ відступ оборона штурм танк бронетехніка артилерія засідка"
        " мобілізація ротація втрати полонені евакуація з зони бойових дій"
        " повітряна тривога збройні сили України оперативне командування"
        " безпілотник FPV коригувальник підрозділ бригада батальйон рота взвод"
        # HU
        " háborús harci cselekmények fegyverek rakéták katonák tűzszünet"
        " légicsapás páncélos előrenyomulás visszavonulás mozgósítás"
        " drón tüzérség veszteségek hadifogoly haditengerészet"
        # SK
        " vojenské operácie zbrane rakety vojaci paľba drón letecký úder"
        " pancierové vozidlá mobilizácia front útok ústup obrana"
        " delostrelecké ostreľovanie bojová línia ozbrojené sily"
        # RO
        " operațiuni militare arme rachete soldați artilerie bombardament"
        " drone atac aerian ofensivă defensivă tancuri mobilizare front"
        " victime prizonieri de război forțe armate"
    ),

    "politics": (
        # Фокус: внутрішня політика, вибори, парламент, влада
        # EN
        "elections parliament government coalition opposition party vote scandal resignation"
        " prime minister president cabinet minister legislation reform decree"
        " constitution referendum snap election polling approval rating ruling party"
        " impeachment censure motion no-confidence vote political crisis"
        " spokesperson press conference statement mandate term of office"
        # UA
        " вибори парламент коаліція опозиція скандал відставка законопроект"
        " Верховна рада президент Зеленський уряд кабінет міністрів"
        " нардеп депутат фракція законодавство реформа референдум"
        " партія слуга народу ОПЗЖ ЄС указ декрет пресслужба"
        " рейтинг довіри довибори проміжні вибори кандидат"
        # HU
        " választások parlament kormánykoalíció ellenzék botrány lemondás"
        " miniszterelnök Orbán Fidesz Momentum DK MSZP Jobbik törvény"
        " alkotmány rendelet parlamenti szavazás bizalmi szavazás mandátum"
        " pártkongresszus elnökség politikai válság sajtóértekezlet"
        # SK
        " voľby parlament koalícia opozícia škandál demisia"
        " predseda vlády Fico Pellegrini Šimečka SMER PS SaS KDH"
        " zákon nariadenie hlasovanie vládna kríza stranícky"
        " prezident parlamentná väčšina menšinová vláda"
        # RO
        " alegeri parlament coaliție opoziție scandal demisie"
        " premier Ciolacu PSD PNL USR AUR Iohannis lege decret"
        " vot de neîncredere criză politică partid campanie electorală"
        " ministru cabinet parlamentar reformă constituție"
    ),

    "diplomacy": (
        # Фокус: міжнародні відносини, переговори, союзи
        # EN
        "diplomatic relations negotiations treaty alliance summit bilateral talks"
        " NATO EU UN ambassador foreign minister international agreement"
        " communiqué sanctions expulsion persona non grata embassy consulate"
        " G7 G20 OSCE IAEA Council of Europe foreign policy"
        " multilateral forum security pact memorandum of understanding"
        " mediation arbitration normalization rapprochement diplomatic incident"
        " envoy special representative peace talks ceasefire negotiation"
        # UA
        " дипломатія переговори договір союз саміт посол"
        " МЗС міністр закордонних справ нота протест санкції"
        " посольство консульство акредитація дипломатичний скандал"
        " НАТО ЄС ООН ОБСЄ Рада Європи партнерство"
        " угода меморандум мирні переговори зовнішня політика"
        # HU
        " diplomácia tárgyalások szerződés szövetség nagykövet"
        " külügyminiszter NATO EU ENSZ szankciók egyezmény"
        " kétoldalú csúcstalálkozó diplomáciai botrány követség"
        " konzulátus béketárgyalások megállapodás külpolitika"
        # SK
        " diplomatické rokovania zmluva spojenectvo veľvyslanec"
        " minister zahraničných vecí NATO EÚ OSN sankcie dohoda"
        " bilaterálne vzťahy diplomatický škandál ambasáda konzulát"
        " mierové rokovania zahraničná politika summit"
        # RO
        " diplomație negocieri tratat alianță ambasador"
        " ministrul afacerilor externe NATO UE ONU sancțiuni acord"
        " bilateral summit incident diplomatic ambasadă consulat"
        " politică externă negocieri de pace memorandum"
    ),

    "economy": (
        # Фокус: макроекономіка, ринки, фінанси — НЕ геополітика
        # EN
        "GDP inflation recession market stock exchange trade deficit budget"
        " investment bank currency interest rate fiscal monetary"
        " IMF World Bank ECB central bank quantitative easing rate hike"
        " economic growth contraction unemployment jobless claims"
        " export import tariff supply chain bond yield credit rating"
        " privatization nationalization subsidy austerity debt restructuring"
        " consumer price index purchasing power wage growth"
        # UA
        " економіка ВВП інфляція ринок бюджет торгівля інвестиції"
        " гривня НБУ Національний банк ставка відсоток дефіцит профіцит"
        " МВФ Світовий банк кредит транш зовнішній борг реструктуризація"
        " безробіття зарплата мінімальна зарплата ринок праці"
        " приватизація держкомпанія субсидія тарифи ЖКГ"
        " фондовий ринок ПФТС УБ інвестиційний клімат"
        # HU
        " gazdaság infláció piac befektetés adó költségvetés"
        " forint MNB Magyar Nemzeti Bank kamatemelés GDP növekedés"
        " munkanélküliség bérszínvonal deviza árfolyam export import"
        " privatizáció állami vállalat szubvenció hitel IMF"
        # SK
        " ekonomika inflácia trh investície rozpočet daň"
        " euro NBS Národná banka Slovenska HDP rast mzdy"
        " nezamestnanosť export import obchodný deficit privatizácia"
        " úver dotácia štátna firma fiškálna menová politika"
        # RO
        " economie inflație piață investiții buget impozit"
        " leu BNR Banca Națională PIB creștere economică salarii"
        " șomaj export import deficit privatizare subvenție"
        " FMI credit restructurare datorie externă"
    ),

    "energy": (
        # Фокус: енергоносії, інфраструктура, кризи постачання
        # EN
        "gas oil electricity nuclear power plant pipeline energy crisis supply"
        " blackout renewable solar wind heating fuel"
        " LNG liquefied natural gas energy security energy mix"
        " power grid transmission outage brownout rolling blackout"
        " OPEC Gazprom Naftogaz Ukrenergo energy tariff utility"
        " coal thermal hydro geothermal battery storage capacity"
        " energy transition decarbonization carbon emissions"
        # UA
        " газ нафта електроенергія АЕС блекаут відновлювальна паливо"
        " Нафтогаз Укренерго ДТЕК Енергоатом Запорізька АЕС"
        " газопровід нафтопровід енергетична безпека імпорт газу"
        " відключення світла дефіцит потужностей тариф постачання"
        " сонячна вітрова гідроелектростанція ГЕС ТЕЦ"
        " газосховище резерви заправка бензин дизель"
        # HU
        " gáz olaj villanyáram atomenergia energiakrízis megújuló"
        " MVM MOL Paks atomerőmű gázvezeték energiabiztonság"
        " energiatakarékosság áramszünet díjszabás napenergia szélenergia"
        " orosz gáz LNG energia-import tarifa rezsi"
        # SK
        " plyn ropa elektrina atómová energia výpadok prúdu"
        " SPP SEPS Slovenský plynárenský priemysel jadrová elektráreň"
        " plynovod energetická bezpečnosť tarify obnoviteľné zdroje"
        " výpadok elektriny zásoby plynu solárna veterná energia"
        # RO
        " gaze petrol electricitate nuclear energie întrerupere"
        " Romgaz Hidroelectrica Nuclearelectrica Transelectrica"
        " conducte gaze securitate energetică tarife energie"
        " panouri solare eoliene cărbune termocentrale blackout"
    ),

    "society": (
        # Фокус: люди, соціальні рухи, демографія — НЕ війна
        # EN
        "protest demonstration civil society human rights minority"
        " population migration refugees demographics culture education healthcare"
        " gender equality LGBTQ+ abortion rights freedom of press"
        " civic activism NGO think tank social movement"
        " aging population birth rate emigration brain drain"
        " religious community church mosque synagogue"
        " hate speech discrimination racism antisemitism"
        " university students youth strike labor union workers"
        # UA
        " протест права людини меншини міграція демографія освіта"
        " охорона здоров'я медицина лікарня церква релігія культура"
        " НГО громадянське суспільство волонтери активісти"
        " народжуваність смертність еміграція заробітчани діаспора"
        " пресса свобода слова цензура незалежні ЗМІ журналіст"
        " студенти університет школа освітня реформа"
        # HU
        " tüntetés emberi jogok kisebbség migráció demográfia oktatás"
        " egészségügy egyház civil szervezet sajtószabadság"
        " bevándorlás elvándorlás születési ráta öregedés"
        " hátrányos megkülönböztetés rasszizmus antiszemiták"
        " szakszervezet sztrájk munkajog diákok egyetem"
        # SK
        " protest ľudské práva menšiny migrácia demografia vzdelávanie"
        " zdravotníctvo cirkev médiá sloboda tlače občianska spoločnosť"
        " prisťahovalectvo vysťahovalectvo pôrodnosť starnutie"
        " diskriminácia rasizmus antisemitizmus odborový zväz štrajk"
        # RO
        " protest drepturile omului minorități migrație demografie educație"
        " sănătate biserică ONG libertatea presei societate civilă"
        " imigrație emigrație natalitate îmbătrânire populație"
        " discriminare rasism antisemitism sindicat grevă tineri"
    ),

    "humanitarian": (
        # Фокус: допомога, евакуація, жертви — відмінно від "war" (фізичні дії)
        # EN
        "humanitarian aid evacuation relief civilians victims displaced persons"
        " reconstruction volunteers charity emergency rescue"
        " UNHCR ICRC Red Cross World Food Programme"
        " internally displaced IDP refugee camp asylum seeker"
        " food aid medical supplies shelter non-combatant protection"
        " mine clearance demining post-war recovery trauma"
        " corridor safe passage ceasefire for aid"
        " orphan missing persons war crimes documentation"
        # UA
        " гуманітарна допомога евакуація жертви цивільні відбудова волонтери"
        " ВПО внутрішньо переміщені особи біженці прихисток"
        " гуманітарний коридор постраждалі мирне населення"
        " Червоний Хрест МКЧХ ООН допомога продовольство"
        " розмінування розчищення відновлення зруйновані будинки"
        " психологічна допомога травма жертви злочину"
        # HU
        " humanitárius segély evakuáció áldozatok civilek újjáépítés"
        " menekülttábor belső menekültek menedékkérők UNHCR ICRC"
        " élelmiszersegély menedékjog háborús bűncselekmény"
        " önkéntesek alapítvány jótékonysági szervezet"
        # SK
        " humanitárna pomoc evakuácia obete civilisti obnova dobrovoľníci"
        " utečenci vnútorne vysídlení UNHCR ICRC potravinová pomoc"
        " humanitárny koridor vojnové zločiny trauma pomoc pre deti"
        # RO
        " ajutor umanitar evacuare victime civili reconstrucție voluntari"
        " refugiați persoane strămutate UNHCR ICRC Crucea Roșie"
        " coridor umanitar crime de război traumă reconstrucție"
    ),

    "technology": (
        # Фокус: IT, AI, кіберпростір — максимально відмінно від решти
        # EN
        "artificial intelligence machine learning software startup cybersecurity"
        " digital innovation blockchain algorithm data cloud computing"
        " large language model LLM generative AI deepfake neural network"
        " semiconductor chip GPU quantum computing robotics automation"
        " data center fiber optic 5G satellite internet Starlink"
        " open source API SaaS platform venture capital unicorn IPO"
        " disinformation cyber attack ransomware phishing malware"
        " digital transformation e-government digital ID e-health"
        # UA
        " штучний інтелект кібербезпека стартап блокчейн цифровізація"
        " Дія e-Rezident держреєстри цифровий уряд кіберзахист"
        " ІТ-галузь IT-компанія розробник програміст аутсорс"
        " кіберзлочин хакер DDOS атака фішинг дезінформація"
        # HU
        " mesterséges intelligencia kiberbiztonság startup digitális innováció"
        " algoritmus adatközpont felhőszolgáltatás kibertámadás"
        " digitalizáció e-közigazgatás okosváros technológiai vállalat"
        # SK
        " umelá inteligencia kybernetická bezpečnosť startup digitálna"
        " algoritmus dátové centrum cloud kybernetický útok"
        " digitalizácia e-government softvér technologická firma"
        # RO
        " inteligență artificială securitate cibernetică startup digital"
        " algoritm centru de date cloud atac cibernetic"
        " digitalizare e-guvernare software companie tehnologică"
    ),

    "crime": (
        # Фокус: злочини, правосуддя, корупція — НЕ геополітика
        # EN
        "crime corruption arrest trial court prosecutor police investigation"
        " fraud money laundering bribery conviction sentence"
        " organized crime drug trafficking human trafficking smuggling"
        " anticorruption NABU SAPO NACP Europol Interpol"
        " indictment warrant extradition witness protection"
        " embezzlement asset seizure confiscation whistleblower"
        " war crimes tribunal ICC international criminal court"
        " domestic violence femicide stalking cybercrime"
        # UA
        " злочин корупція арешт суд прокурор поліція шахрайство хабар"
        " НАБУ НАЗК САП ДБР ВАКС антикорупційний"
        " відмивання грошей обшук підозра обвинувачення вирок"
        " контрабанда наркотики торгівля людьми організована злочинність"
        " розслідування журналістське розслідування BIHUS"
        " конфіскація активи декларація майно"
        # HU
        " bűnözés korrupció letartóztatás bíróság ügyész rendőrség"
        " pénzmosás csalás vesztegetés ítélet büntetés"
        " szervezett bűnözés kábítószer-kereskedelem csempészet"
        " OLAF korrupcióellenes vagyon elkobzás nyomozás"
        # SK
        " zločin korupcia zatknutie súd prokurátor polícia podvod"
        " pranie špinavých peňazí úplatok odsúdenie trest"
        " organizovaný zločin pašovanie drogy korupčná kauza"
        " NAKA vyšetrovanie konfiškácia majetku"
        # RO
        " infracțiune corupție arest tribunal procuror poliție fraudă"
        " spălare de bani mită condamnare sentință"
        " crimă organizată trafic de droguri contrabandă"
        " DNA DIICOT ANI dosar penal confiscare bunuri"
    ),
}
# ─── Конфігурація gap-based selection ────────────────────────────────────────

# Жорсткий floor — теги нижче НІКОЛИ не присвоюються
MIN_ABSOLUTE_THRESHOLD: float = 0.45

# Розрив між сусідніми тегами → стоп (більший = суворіший)
GAP_THRESHOLD: float = 0.08

# Hard cap — максимум тегів незалежно від gaps
MAX_TAGS_PER_ARTICLE: int = 4

# Якщо після gap-selection залишився 1 тег — він має бути впевненим
# Захист від "майже нічого не підійшло але 1 tag чуть вище floor"
MIN_SCORE_SINGLE_TAG: float = 0.55


class EmbeddingTagger:
    """
    Zero-shot тегер з gap-based selection.

    Singleton через Embedder.instance() — модель завантажується один раз.

    Приклад:
        tagger = EmbeddingTagger()

        # Стаття про NATO без HU контексту:
        tags = tagger.tag("Akár kilép Trump a NATO-ból...")
        # → ["diplomacy", "politics"]  (не всі 9 тегів)

        # Стаття про ракетний удар:
        tags = tagger.tag("Ракетний удар по Харкову...")
        # → ["war", "humanitarian"]
    """

    def __init__(
        self,
        embedder: Embedder | None = None,
        min_absolute_threshold: float = MIN_ABSOLUTE_THRESHOLD,
        gap_threshold: float = GAP_THRESHOLD,
        max_tags: int = MAX_TAGS_PER_ARTICLE,
        min_score_single_tag: float = MIN_SCORE_SINGLE_TAG,
    ) -> None:
        self._embedder = embedder or Embedder.instance()
        self._min_threshold = min_absolute_threshold
        self._gap_threshold = gap_threshold
        self._max_tags = max_tags
        self._min_score_single_tag = min_score_single_tag

        self._tag_vectors: dict[str, np.ndarray] = self._build_tag_vectors()
        logger.info(
            "EmbeddingTagger initialized: %d tags, floor=%.2f gap=%.2f max=%d",
            len(self._tag_vectors), min_absolute_threshold, gap_threshold, max_tags,
        )

    def _build_tag_vectors(self) -> dict[str, np.ndarray]:
        """
        Кодуємо описи тегів як query.
        Робиться ОДИН РАЗ при старті.
        """
        tags = list(TAG_DESCRIPTIONS.keys())
        descriptions = list(TAG_DESCRIPTIONS.values())
        vectors = self._embedder.encode_batch(descriptions, is_query=True)
        return {tag: vectors[i] for i, tag in enumerate(tags)}

    def tag(self, text: str) -> list[str]:
        """
        Gap-based tag selection.

        Returns:
            Список тегів відсортований за score DESC.
            Зазвичай 1-3 теги. Максимум MAX_TAGS_PER_ARTICLE.
        """
        scored = self._score_all(text)
        if not scored:
            return []

        selected = self._gap_select(scored)
        return [tag for tag, _ in selected]

    def tag_with_scores(self, text: str) -> dict[str, float]:
        """
        Всі scores для діагностики (без gap-selection, без floor).
        Корисно щоб зрозуміти чому тег не потрапив.
        """
        if not text or not text.strip():
            return {}

        article_vec = self._embedder.encode_passage(text)
        scores = {
            tag: float(self._embedder.cosine_similarity(article_vec, vec))
            for tag, vec in self._tag_vectors.items()
        }
        return dict(sorted(scores.items(), key=lambda x: x[1], reverse=True))

    def _score_all(self, text: str) -> list[tuple[str, float]]:
        """
        Рахуємо similarity для всіх тегів, фільтруємо за floor.
        Повертає [(tag, score)] відсортовані DESC.
        """
        if not text or not text.strip():
            return []

        article_vec = self._embedder.encode_passage(text)

        scored = []
        for tag_name, tag_vec in self._tag_vectors.items():
            sim = float(self._embedder.cosine_similarity(article_vec, tag_vec))
            if sim >= self._min_threshold:
                scored.append((tag_name, sim))

        scored.sort(key=lambda x: x[1], reverse=True)

        if scored:
            logger.debug(
                "EmbeddingTagger scores (above floor=%.2f): %s",
                self._min_threshold,
                [(t, f"{s:.3f}") for t, s in scored],
            )

        return scored

    def _gap_select(self, scored: list[tuple[str, float]]) -> list[tuple[str, float]]:
        """
        Gap-based selection алгоритм:

        1. Беремо перший тег завжди (найвищий score).
        2. Перевіряємо gap до наступного:
           gap = scored[i].score - scored[i+1].score
           якщо gap >= GAP_THRESHOLD → стоп, далі не беремо.
        3. Hard cap MAX_TAGS_PER_ARTICLE.
        4. Якщо залишився 1 тег — перевіряємо MIN_SCORE_SINGLE_TAG.

        Чому gap а не абсолютний поріг:
          Абсолютний поріг залежить від тексту і моделі.
          Gap стабільніший — він показує відносну різницю між тегами.
        """
        if not scored:
            return []

        selected = [scored[0]]  # перший завжди

        for i in range(len(scored) - 1):
            if i + 1 >= self._max_tags:
                break

            current_score = scored[i][1]
            next_score = scored[i + 1][1]
            gap = current_score - next_score

            if gap >= self._gap_threshold:
                # Великий розрив → далі менш релевантні теги
                logger.debug(
                    "EmbeddingTagger gap=%.3f >= %.3f at position %d → stop",
                    gap, self._gap_threshold, i,
                )
                break

            selected.append(scored[i + 1])

        # Захист від одинокого слабкого тегу
        if len(selected) == 1 and selected[0][1] < self._min_score_single_tag:
            logger.debug(
                "EmbeddingTagger: single tag %s score=%.3f < min_single=%.3f → drop",
                selected[0][0], selected[0][1], self._min_score_single_tag,
            )
            return []

        logger.debug(
            "EmbeddingTagger selected: %s",
            [(t, f"{s:.3f}") for t, s in selected],
        )
        return selected