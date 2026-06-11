# infrastructure/ml/embedding_tagger.py
"""
EmbeddingTagger — zero-shot тегер на основі cosine similarity.

Gap-based tag selection замість flat threshold (детальний опис підходу
дивись в історії змін модуля — без змін щодо алгоритму).

Конфігурація:
  MIN_ABSOLUTE_THRESHOLD = 0.45  # floor
  GAP_THRESHOLD          = 0.08  # розрив між сусідніми тегами → стоп
  MAX_TAGS_PER_ARTICLE   = 4     # hard cap
  MIN_SCORE_SINGLE_TAG   = 0.55  # якщо тільки 1 тег — він має бути впевненим

Мови описів тегів: EN, UA, HU, SK, RO, PL.
  Додано польську (PL), бо корпус новин включає видання з Польщі
  (прикордонно-міграційна тематика, біженці, відносини з Україною тощо).

Теги і їх семантичні описи:
  Описи навмисно РІЗНІ щоб мінімізувати cross-tag overlap.
  Важливо: НЕ дублювати слова між тегами — модель тоді краще розрізняє.

Канонічні (UA) теги, що повертає tag(), беруться з
src.infrastructure.tagging.tag_vocabulary.EMBEDDING_TAG_LABELS —
єдиного джерела правди, спільного з CategoryTagger / CompositeTagger.
"""
from __future__ import annotations

import logging

import numpy as np

from src.infrastructure.ml.embedder import Embedder
from src.infrastructure.tagging.tag_vocabulary import EMBEDDING_TAG_LABELS, ALLOWED_TAGS

logger = logging.getLogger(__name__)


# ─── Словник тегів ────────────────────────────────────────────────────────────
# ВАЖЛИВО: описи навмисно не перекриваються між собою.
# "war" не містить "politics", "diplomacy" не містить "military".
# Це ключово для gap-based selection — якщо описи однакові,
# модель дає однакові scores і gap не виникає.

TAG_DESCRIPTIONS: dict[str, str] = {
    "war": (
        # Фокус: бойові дії, зброя, фізичне насильство, лінія фронту
        # EN
        "armed combat frontline battlefield troops soldiers weapons missiles drones artillery shelling"
        " infantry armored column tank assault offensive defensive maneuver ceasefire"
        " air strike cruise missile HIMARS cluster munition mine sniper casualty POW"
        " occupation siege encirclement retreat advance reinforcement mobilization"
        " military operation special operation naval attack kamikaze drone FPV"
        # UA
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
        # PL
        " działania zbrojne front broń pociski rakiety drony ostrzał artyleryjski"
        " żołnierze piechota kolumna pancerna czołg natarcie ofensywa obrona"
        " nalot rakieta manewrowa miny snajper jeniec wojenny okupacja"
        " oblężenie okrążenie odwrót natarcie mobilizacja"
        " operacja wojskowa atak morski dron kamikaze bezzałogowiec"
    ),

    "politics": (
        # Фокус: Внутрішня політика, вибори, уряд, ПРОРОСІЙСЬКИЙ вплив, зв'язки з РФ
        # EN
        "elections parliament government domestic policy coalition opposition party crisis"
        " pro-russian influence ties with russia anti-ukrainian sentiment ruling party"
        " prime minister president legislation decree constitution snap election"
        # UA
        " вибори парламент коаліція опозиція уряд національна політика політична криза"
        " проросійські сили антиукраїнський вплив рф зв'язки з росією законодавство"
        " Верховна рада президент Зеленський кабінет міністрів нардеп фракція"
        # HU
        " választások parlament belpolitika kormánykoalíció ellenzék politikai válság"
        " orosz befolyás ukránellenes pártkongresszus lemondás törvény"
        # SK
        " voľby parlament domáca politika koalícia opozícia ruský vplyv vládna kríza"
        " zákon nariadenie hlasovanie menšinová vláda"
        # RO
        " alegeri parlament politică internă coaliție influență rusă criză politică"
        # PL
        " wybory parlament polityka krajowa opozycja rosyjskie wpływy antyukraiński"
        " Sejm Senat dymisja wotum nieufności"
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
        # PL
        " stosunki dyplomatyczne negocjacje traktat sojusz szczyt rozmowy dwustronne"
        " NATO UE ONZ ambasador minister spraw zagranicznych porozumienie międzynarodowe"
        " sankcje persona non grata ambasada konsulat"
        " G7 G20 OBWE polityka zagraniczna"
        " forum wielostronne pakt bezpieczeństwa memorandum"
        " mediacja normalizacja incydent dyplomatyczny"
        " wysłannik specjalny rozmowy pokojowe rozejm"
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
        " приватизація держкомпанія тарифи ЖКГ"
        " фондовий ринок ПФТС УБ інвестиційний клімат"
        # HU
        " gazdaság infláció piac befektetés adó költségvetés"
        " forint MNB Magyar Nemzeti Bank kamatemelés GDP növekedés"
        " munkanélküliség bérszínvonal deviza árfolyam export import"
        " privatizáció állami vállalat hitel IMF"
        # SK
        " ekonomika inflácia trh investície rozpočet daň"
        " euro NBS Národná banka Slovenska HDP rast mzdy"
        " nezamestnanosť export import obchodný deficit privatizácia"
        " úver štátna firma fiškálna menová politika"
        # RO
        " economie inflație piață investiții buget impozit"
        " leu BNR Banca Națională PIB creștere economică salarii"
        " șomaj export import deficit privatizare"
        " FMI credit restructurare datorie externă"
        # PL
        " gospodarka PKB inflacja rynek giełda deficit handlowy budżet"
        " inwestycje bank centralny złoty stopa procentowa polityka fiskalna"
        " NBP Narodowy Bank Polski podwyżka stóp procentowych"
        " wzrost gospodarczy recesja bezrobocie zasiłek dla bezrobotnych"
        " eksport import cło łańcuch dostaw rentowność obligacji rating kredytowy"
        " prywatyzacja nacjonalizacja dług restrukturyzacja"
        " wskaźnik cen konsumpcyjnych siła nabywcza wzrost płac"
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
        # PL
        " gaz ropa energia elektryczna elektrownia jądrowa gazociąg kryzys energetyczny"
        " blackout odnawialne źródła energii energia słoneczna wiatrowa ogrzewanie paliwo"
        " LNG bezpieczeństwo energetyczne miks energetyczny"
        " sieć przesyłowa awaria zasilania przerwy w dostawie prądu"
        " PGNiG PGE Orlen taryfa energetyczna"
        " węgiel elektrownia cieplna elektrownia wodna magazyn energii"
        " transformacja energetyczna dekarbonizacja emisje CO2"
    ),

    "society": (
        # Фокус: Соціальна політика, пенсії, допомога українським біженцям, виплати
        # EN
        "social policy welfare pensions healthcare education refugee support assistance"
        " demographic crisis ukrainian refugees diaspora civil society minority"
        " protest demonstration human rights civic activism NGO"
        # UA
        " соціальна політика соціальні виплати пенсії медицина освіта допомога українцям"
        " біженці з україни субсидії громадянське суспільство демографія міграція"
        " протест права людини меншини народжуваність переселенці"
        # HU
        " szociálpolitika nyugdíj egészségügy oktatás ukrán menekültek támogatása"
        " szociális ellátás demográfia civil szervezet tüntetés emberi jogok"
        # SK
        " sociálna politika dôchodok zdravotníctvo podpora utečencov z ukrajiny"
        " protest ľudské práva menšiny vzdelávanie"
        # RO
        " politică socială pensie sănătate sprijin pentru refugiați ucraineni"
        " protest drepturile omului minorități"
        # PL
        " polityka społeczna emerytura ochrona zdrowia uchodźcy z ukrainy wsparcie socjalne"
        " protest demonstracja społeczeństwo obywatelskie prawa człowieka"
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
        " ВПО внутрішньо переміщені особи прихисток"
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
        # PL
        " pomoc humanitarna ewakuacja ofiary cywile odbudowa wolontariusze"
        " uchodźcy osoby wewnętrznie przesiedlone obóz dla uchodźców azyl"
        " pomoc żywnościowa zaopatrzenie medyczne schronienie ochrona ludności cywilnej"
        " rozminowanie odbudowa po wojnie trauma"
        " korytarz humanitarny bezpieczny przejazd zawieszenie broni dla pomocy"
        " sieroty osoby zaginione zbrodnie wojenne dokumentacja"
        " UNHCR Czerwony Krzyż ONZ Światowy Program Żywnościowy"
    ),

    "technology": (
        # Фокус ВИКЛЮЧНО на: Кібербезпека, злами, хакери, розробка ПЗ (ніяких AI чи стартапів)
        # EN
        "cybersecurity hacker cyberattack ddos ransomware phishing malware virus"
        " data breach software development programmer it company digital defense information security"
        # UA
        " кібербезпека хакер злам взлом кібератака витік даних вірус троян"
        " розробка програмного забезпечення програміст розробник it-компанія кіберзахист"
        # HU
        " kiberbiztonság kibertámadás adatlopás hacker szoftverfejlesztés vírus"
        # SK
        " kybernetická bezpečnosť kybernetický útok haker softvér vývojár"
        # RO
        " securitate cibernetică atac cibernetic hacker software dezvoltator"
        # PL
        " cyberbezpieczeństwo cyberatak haker wyciek danych oprogramowanie wirus programista"
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
        # PL
        " przestępstwo korupcja zatrzymanie sąd prokurator policja oszustwo łapówka"
        " pranie pieniędzy przekupstwo wyrok skazanie"
        " przestępczość zorganizowana przemyt narkotyków handel ludźmi szmugiel"
        " antykorupcyjny CBA Europol Interpol"
        " akt oskarżenia nakaz aresztowania ekstradycja ochrona świadków"
        " defraudacja konfiskata mienia sygnalista"
        " trybunał zbrodni wojennych MTK"
        " przemoc domowa"
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
        # → ["зовнішня політика", "національна політика"]

        # Стаття про ракетний удар:
        tags = tagger.tag("Ракетний удар по Харкову...")
        # → ["військова техніка", "гуманітарна"]
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

        # Fail-fast: усі внутрішні ключі TAG_DESCRIPTIONS мають мати мапінг
        # на канонічний UA-тег, інакше gap-selection може "тихо" загубити тег.
        _missing = set(TAG_DESCRIPTIONS) - set(EMBEDDING_TAG_LABELS)
        if _missing:
            raise ValueError(
                f"EmbeddingTagger: для ключів {_missing} немає мапінгу в "
                f"tag_vocabulary.EMBEDDING_TAG_LABELS."
            )
        _bad_labels = set(EMBEDDING_TAG_LABELS.values()) - ALLOWED_TAGS
        if _bad_labels:
            raise ValueError(
                f"EmbeddingTagger: мітки {_bad_labels} відсутні в "
                f"tag_vocabulary.ALLOWED_TAGS."
            )

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
            Відсортований список КАНОНІЧНИХ (українських) тегів —
            значення з tag_vocabulary.ALLOWED_TAGS.
            Зазвичай 1-3 теги. Максимум MAX_TAGS_PER_ARTICLE.
        """
        scored = self._score_all(text)
        if not scored:
            return []

        selected = self._gap_select(scored)

        # Переклад внутрішніх ключів (war/politics/...) у канонічні UA-теги.
        result: set[str] = set()
        for internal_tag, _score in selected:
            label = EMBEDDING_TAG_LABELS.get(internal_tag)
            if label is None:
                # Не повинно статись через перевірку в __init__,
                # але про всяк випадок — не пропускаємо "сирий" ключ.
                logger.warning(
                    "EmbeddingTagger: немає мапінгу для внутрішнього тегу %r — пропущено",
                    internal_tag,
                )
                continue
            result.add(label)

        return sorted(result)

    def tag_with_scores(self, text: str) -> dict[str, float]:
        """
        Всі scores для діагностики (без gap-selection, без floor).
        Повертає ВНУТРІШНІ ключі (war/politics/...), а не канонічні теги —
        зручно для дебагу алгоритму вибору.
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