"""Language data for spec 0094 that is *not* a normalization convention.

Unit multipliers, era offsets, locales, and currency markers live in
``knowledge/venture_intelligence/conventions.json`` (one source of truth). This
module holds only month names and function-word lists used for identification and
date parsing. The Kazakh and Uzbek month names and the Filipino month names are
unverified and should be reviewed by a native speaker (``gap`` recorded).
"""

from __future__ import annotations

from typing import Dict, Tuple

MONTHS_TH: Tuple[str, ...] = ("มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
                              "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม")
MONTHS_ID: Tuple[Tuple[str, ...], ...] = (
    ("januari",), ("februari", "pebruari"), ("maret", "mac"), ("april",), ("mei",), ("juni", "jun"),
    ("juli", "julai"), ("agustus", "ogos"), ("september",), ("oktober",), ("november",),
    ("desember", "disember"))
MONTHS_FIL: Tuple[str, ...] = ("enero", "pebrero", "marso", "abril", "mayo", "hunyo", "hulyo",
                               "agosto", "setyembre", "oktubre", "nobyembre", "disyembre")
MONTHS_RU: Tuple[str, ...] = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля",
                              "августа", "сентября", "октября", "ноября", "декабря")
MONTHS_KK: Tuple[str, ...] = ("қаңтар", "ақпан", "наурыз", "сәуір", "мамыр", "маусым", "шілде",
                              "тамыз", "қыркүйек", "қазан", "қараша", "желтоқсан")
MONTHS_UZ: Tuple[str, ...] = ("yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul",
                              "avgust", "sentabr", "oktabr", "noyabr", "dekabr")
MONTHS_EN: Tuple[Tuple[str, ...], ...] = (
    ("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"), ("may",),
    ("june", "jun"), ("july", "jul"), ("august", "aug"), ("september", "sep", "sept"),
    ("october", "oct"), ("november", "nov"), ("december", "dec"))

UNVERIFIED_LEXICONS = ("kk months", "uz months", "fil months", "id/ms month variants")

# Function words for Latin-script identification. Deliberately short and common.
FUNCTION_WORDS: Dict[str, Tuple[str, ...]] = {
    "en": ("the", "of", "and", "to", "in", "is", "for", "that", "with", "on", "as", "by", "from",
           "was", "were", "has", "have", "this", "are", "at", "an", "its"),
    "id/ms": ("yang", "dan", "di", "ke", "dengan", "untuk", "ini", "itu", "adalah", "dari", "pada",
              "akan", "tidak", "dalam", "oleh", "telah", "sebesar", "perseroan", "syarikat"),
    "fil": ("ang", "ng", "sa", "mga", "na", "ay", "para", "at", "ito", "kay", "ay", "naman",
            "po", "kumpanya", "noong", "nang"),
    "vi": ("và", "của", "là", "có", "cho", "một", "những", "được", "trong", "công", "ty", "với",
           "không", "các", "này", "đã", "năm", "tháng", "ngày"),
}
# Cyrillic language-specific letters (evidence only; never conclusive for short text).
KK_LETTERS = "әіғқңұһ"
UZ_CYRL_LETTERS = "ўқғҳ"
TG_LETTERS = "ӣҷҳӯ"
RU_FUNCTION_WORDS = ("и", "в", "не", "на", "что", "это", "для", "с", "по", "от", "к", "из", "был",
                     "была", "было", "были", "компания", "года", "году", "млн", "руб")

# Vietnamese-only precomposed letters block and base letters.
VI_BASE = "ăâđêôơưĂÂĐÊÔƠƯ"
VI_BLOCK_START, VI_BLOCK_END = 0x1EA0, 0x1EF9

# Simplified/Traditional pairs where the two forms differ (simplified, traditional).
SIMP_TRAD: Tuple[Tuple[str, str], ...] = tuple(zip(
    "国们这为开发业务资产银经济对电动术会计联网创实现与过进还内东车长门间问题机构价数据报风险贷币额万亿种员权总营费税财买卖单级",
    "國們這為開發業務資產銀經濟對電動術會計聯網創實現與過進還內東車長門間問題機構價數據報風險貸幣額萬億種員權總營費稅財買賣單級"))
