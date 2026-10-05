"""Clean up raw text extracted from adilet.zan.kz legal-act PDFs before
indexing, per the government knowledge-base normalization requirement:

- Strip site boilerplate notices (Примечание ИЗПИ/РЦПИ, Вниманию
  пользователей, Сноска...) out of the text used for embeddings, but
  keep them instead of discarding - they're often the only place the
  amending-law numbers and revision date are stated.
- Normalize date and document-number formatting so near-duplicate
  mentions ("24 апреля 2004 года" vs "24.04.2004") don't fragment
  retrieval.
- Extract, per document: the latest legal status (действует /
  утратил силу / etc.), the revision date, and the amending law
  numbers (№ 256-VIII, № 306-VIII, ...).
"""

import re

_MONTHS = {
	"января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
	"июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

# Site boilerplate lines/sentences to strip out of the indexed text.
_NOTICE_PATTERNS = [
	re.compile(r"Примечание (?:ИЗПИ|РЦПИ)!.*?(?=\n|$)"),
	re.compile(r"Вниманию пользователей!.*?(?=\n|$)"),
	re.compile(r"Для удобства пользования ИЗПИ создано СОДЕРЖАНИЕ.*?(?=\n|$)"),
	re.compile(r"Введение в действие см\. ст\. \d+\.?"),
	re.compile(r"Сноска\.[^\n]*"),
]

_LAW_NUMBER_RE = re.compile(r"№\s*\d+(?:-[IVXLC]+)?")
_LONG_DATE_RE = re.compile(r"(\d{1,2})\s+([а-я]+)\s+(\d{4})\s*года?", re.IGNORECASE)
_SHORT_DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")

# "статья/статьи/статью/статье/статей ..." (any case ending) / "ст.5" /
# "ст. 5" -> "ст. 5" / "ст. 5-8", so different mentions of the same
# article don't look like different tokens.
_ARTICLE_RE = re.compile(r"\b(?:стать[а-я]{0,3}|статей)\b\.?\s*(\d+(?:\s*-\s*\d+)?)", re.IGNORECASE)
_ARTICLE_ABBR_RE = re.compile(r"\bст\.\s*(\d+(?:\s*-\s*\d+)?)", re.IGNORECASE)

_STATUS_PATTERNS = [
	(re.compile(r"Утратил силу|Утративший силу", re.IGNORECASE), "Утратил силу"),
	(re.compile(r"Действующ(?:ий|ая|ее)", re.IGNORECASE), "Действует"),
]


def _normalize_dates(text: str) -> str:
	def long_to_iso(m):
		day, month_name, year = m.groups()
		month = _MONTHS.get(month_name.lower())
		if not month:
			return m.group(0)
		return "%04d-%02d-%02d" % (int(year), month, int(day))

	def short_to_iso(m):
		day, month, year = m.groups()
		return "%04d-%02d-%02d" % (int(year), int(month), int(day))

	text = _LONG_DATE_RE.sub(long_to_iso, text)
	text = _SHORT_DATE_RE.sub(short_to_iso, text)
	return text


def _normalize_article_refs(text: str) -> str:
	text = _ARTICLE_RE.sub(lambda m: "ст. %s" % re.sub(r"\s*-\s*", "-", m.group(1)), text)
	text = _ARTICLE_ABBR_RE.sub(lambda m: "ст. %s" % re.sub(r"\s*-\s*", "-", m.group(1)), text)
	return text


def _extract_notices(text: str) -> tuple[str, list[str]]:
	notices: list[str] = []
	for pattern in _NOTICE_PATTERNS:
		for match in pattern.finditer(text):
			notice = match.group(0).strip()
			if notice:
				notices.append(notice)
		text = pattern.sub("", text)
	return text, notices


def _extract_status(text: str) -> str | None:
	for pattern, label in _STATUS_PATTERNS:
		if pattern.search(text):
			return label
	return None


def _extract_latest_date(text: str) -> str | None:
	dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
	return max(dates) if dates else None


def clean_legal_text(raw_text: str) -> dict:
	"""Returns {text, site_notices, legal_status, revision_date, amending_laws}.

	`text` is what should actually be chunked and embedded; the rest are
	metadata to store on the RAG Document record.
	"""
	notice_source, notices = _extract_notices(raw_text)
	amending_laws = sorted(set(_LAW_NUMBER_RE.findall(notice_source + "\n" + raw_text)))

	cleaned = _normalize_dates(notice_source)
	cleaned = _normalize_article_refs(cleaned)
	cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

	notices_text = "\n".join(_normalize_dates(n) for n in notices)

	return {
		"text": cleaned,
		"site_notices": notices_text,
		"legal_status": _extract_status(notices_text + "\n" + raw_text),
		"revision_date": _extract_latest_date(_normalize_dates(notices_text)),
		"amending_laws": "\n".join(amending_laws),
	}
