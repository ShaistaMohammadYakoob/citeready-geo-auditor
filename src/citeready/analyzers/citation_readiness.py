"""Deterministic, evidence-backed checks for AI citation readiness."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import uuid4

from ..models import (
    AuditCategory,
    CitationReadinessAnalysis,
    CitationReadinessPageAnalysis,
    Confidence,
    ContentBlock,
    CrawledPage,
    DirectAnswerAssessment,
    DiscoverabilityFinding,
    Evidence,
    FaqAssessment,
    Heading,
    Severity,
)


LONG_PARAGRAPH_WORDS = 120
LONG_SECTION_WORDS = 400
STRUCTURE_PAGE_WORDS = 500
OPENING_WORD_LIMIT = 200
GENERIC_HEADINGS = {"overview", "learn more", "more", "features", "solutions", "click here"}
QUESTION_PREFIX = re.compile(r"^(who|what|when|where|why|how|can|do|does|is|are|will|should)\b", re.I)
EXPLANATORY_PATTERN = re.compile(
    r"\b(is|are|provides|provide|offers|offer|helps|help|enables|enable|delivers|deliver)\b",
    re.I,
)
SOURCE_SIGNAL_PATTERN = re.compile(
    r"\b(source|citation|cite|reference|according to|study|report)\b|https?://|www\.",
    re.I,
)
PERCENTAGE_PATTERN = re.compile(r"\b\d{1,3}(?:\.\d+)?%")
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
SUPERLATIVE_PATTERN = re.compile(r"\b(best|fastest|number one|award-winning)\b", re.I)
WORD_PATTERN = re.compile(r"\b[\w'-]+\b")
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
STOP_WORDS = {
    "about",
    "after",
    "and",
    "are",
    "for",
    "from",
    "into",
    "our",
    "that",
    "the",
    "this",
    "with",
    "your",
}


@dataclass(slots=True)
class ContentSection:
    """Internal representation of text grouped below one heading."""

    heading: ContentBlock | None
    blocks: list[ContentBlock]


class CitationReadinessAnalyzer:
    """Assess whether crawled content is easy to retrieve, summarize, and cite."""

    def analyze(self, pages: list[CrawledPage]) -> CitationReadinessAnalysis:
        """Return unscored, deterministic citation-readiness findings for each page."""

        page_results: list[CitationReadinessPageAnalysis] = []
        findings: list[DiscoverabilityFinding] = []
        for page in pages:
            blocks = _page_blocks(page)
            direct_answer = self._direct_answer_assessment(page, blocks)
            faq = self._faq_assessment(page, blocks)
            page_results.append(
                CitationReadinessPageAnalysis(
                    page_url=page.url,
                    heading_hierarchy=page.headings,
                    direct_answer=direct_answer,
                    faq=faq,
                    freshness_signals=page.freshness_signals,
                )
            )
            findings.extend(self._long_paragraph_findings(page, blocks))
            findings.extend(self._heading_findings(page))
            if not direct_answer.is_strong:
                findings.append(self._weak_opening_finding(page, direct_answer))
            findings.extend(self._faq_findings(page, faq))
            list_table_finding = self._list_table_finding(page, blocks)
            if list_table_finding:
                findings.append(list_table_finding)
            unsupported_finding = self._unsupported_claims_finding(page, blocks)
            if unsupported_finding:
                findings.append(unsupported_finding)
            findings.extend(self._chunkability_findings(page, blocks))

        return CitationReadinessAnalysis(pages=page_results, findings=findings)

    def _long_paragraph_findings(
        self,
        page: CrawledPage,
        blocks: list[ContentBlock],
    ) -> list[DiscoverabilityFinding]:
        findings: list[DiscoverabilityFinding] = []
        for block in blocks:
            if block.kind != "paragraph":
                continue
            paragraph_words = _word_count(block.text)
            if paragraph_words <= LONG_PARAGRAPH_WORDS:
                continue
            findings.append(
                _finding(
                    title="Paragraph is difficult to extract as a concise passage",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    affected_url=page.url,
                    evidence=[
                        Evidence(
                            page_url=page.url,
                            exact_text=block.text[:200],
                            source_type="HTML paragraph",
                            context=f"Paragraph word count: {paragraph_words}.",
                        )
                    ],
                    why_it_matters=(
                        "Long paragraphs combine multiple ideas, making them harder for retrieval systems "
                        "to isolate and quote as a self-contained answer."
                    ),
                    recommendation=(
                        "Split this paragraph into shorter passages and use a heading, bullets, or a table "
                        "where the content contains distinct ideas."
                    ),
                    impact=3,
                    effort=2,
                )
            )
        return findings

    def _heading_findings(self, page: CrawledPage) -> list[DiscoverabilityFinding]:
        findings: list[DiscoverabilityFinding] = []
        h1_headings = [heading for heading in page.headings if heading.level == 1]
        hierarchy = _heading_hierarchy(page)
        if not h1_headings:
            findings.append(
                _finding(
                    title="Page is missing an H1 heading",
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    affected_url=page.url,
                    evidence=[
                        Evidence(
                            page_url=page.url,
                            exact_text="No H1 element was found in the parsed heading hierarchy.",
                            source_type="heading hierarchy",
                            context=hierarchy,
                        )
                    ],
                    why_it_matters=(
                        "An H1 gives crawlers and answer systems a primary statement of the page topic."
                    ),
                    recommendation="Add one descriptive H1 that states the page's main topic or answer.",
                    copy_paste_fix=None,
                    impact=4,
                    effort=1,
                )
            )
        elif len(h1_headings) > 1:
            findings.append(
                _finding(
                    title="Page has multiple H1 headings",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    affected_url=page.url,
                    evidence=[
                        Evidence(
                            page_url=page.url,
                            exact_text="; ".join(f"H1: {heading.text}" for heading in h1_headings),
                            source_type="heading hierarchy",
                            context=hierarchy,
                        )
                    ],
                    why_it_matters=(
                        "Multiple top-level headings can make the primary page topic less clear to "
                        "retrieval and summarization systems."
                    ),
                    recommendation="Keep one page-level H1 and change additional top-level headings to H2 or lower.",
                    copy_paste_fix=None,
                    impact=3,
                    effort=1,
                )
            )

        jumps = _heading_level_jumps(page)
        if jumps:
            findings.append(
                _finding(
                    title="Heading hierarchy skips levels",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    affected_url=page.url,
                    evidence=[
                        Evidence(
                            page_url=page.url,
                            exact_text=f"H{previous.level} “{previous.text}” is followed by H{current.level} “{current.text}”.",
                            source_type="heading hierarchy",
                            context=hierarchy,
                        )
                        for previous, current in jumps
                    ],
                    why_it_matters=(
                        "Skipped levels weaken the structural relationship between sections and can make "
                        "content boundaries harder to interpret."
                    ),
                    recommendation="Use consecutive levels when nesting sections, such as H2 followed by H3.",
                    copy_paste_fix=None,
                    impact=3,
                    effort=2,
                )
            )

        generic = [heading for heading in page.headings if _is_generic_heading(heading.text)]
        if generic:
            findings.append(
                _finding(
                    title="Page uses generic headings",
                    severity=Severity.LOW,
                    confidence=Confidence.HIGH,
                    affected_url=page.url,
                    evidence=[
                        Evidence(
                            page_url=page.url,
                            exact_text=f"H{heading.level}: {heading.text}",
                            source_type="heading hierarchy",
                            context=hierarchy,
                        )
                        for heading in generic
                    ],
                    why_it_matters=(
                        "Generic headings do not explain what follows, reducing the usefulness of extracted "
                        "sections when content is retrieved out of context."
                    ),
                    recommendation="Replace generic labels with headings that name the specific topic or customer question.",
                    copy_paste_fix=None,
                    impact=2,
                    effort=1,
                )
            )
        return findings

    def _direct_answer_assessment(
        self,
        page: CrawledPage,
        blocks: list[ContentBlock],
    ) -> DirectAnswerAssessment:
        opening_text = _opening_text(page, blocks)
        opening_words = _words(opening_text)[:OPENING_WORD_LIMIT]
        excerpt = _word_limited_excerpt(opening_text, OPENING_WORD_LIMIT)
        topic_terms = _topic_terms(page)
        opening_terms = {word.lower() for word in opening_words}
        overlap = sorted(topic_terms & opening_terms)
        explanatory = bool(EXPLANATORY_PATTERN.search(excerpt))

        if len(opening_words) < 30:
            return DirectAnswerAssessment(
                is_strong=False,
                opening_excerpt=excerpt,
                reason=(
                    f"The opening contains only {len(opening_words)} words, which is too little text to "
                    "establish a clear page-level answer."
                ),
            )
        if not topic_terms:
            return DirectAnswerAssessment(
                is_strong=False,
                opening_excerpt=excerpt,
                reason="No meaningful topic terms could be derived from the page title or H1.",
            )
        required_overlap = 1 if len(topic_terms) == 1 else 2
        if len(overlap) < required_overlap:
            return DirectAnswerAssessment(
                is_strong=False,
                opening_excerpt=excerpt,
                reason=(
                    "The opening does not repeat enough meaningful title or H1 topic terms "
                    f"(matched: {', '.join(overlap) or 'none'})."
                ),
            )
        if not explanatory:
            return DirectAnswerAssessment(
                is_strong=False,
                opening_excerpt=excerpt,
                reason=(
                    "The opening includes page-topic terms but lacks a simple explanatory verb such as "
                    "is, provides, offers, or helps."
                ),
            )
        return DirectAnswerAssessment(
            is_strong=True,
            opening_excerpt=excerpt,
            reason=(
                "The opening contains meaningful title or H1 topic terms "
                f"({', '.join(overlap)}) and an explanatory statement pattern."
            ),
        )

    @staticmethod
    def _weak_opening_finding(
        page: CrawledPage,
        assessment: DirectAnswerAssessment,
    ) -> DiscoverabilityFinding:
        return _finding(
            title="Opening does not clearly state what the page is about",
            severity=Severity.MEDIUM,
            confidence=Confidence.MEDIUM,
            affected_url=page.url,
            evidence=[
                Evidence(
                    page_url=page.url,
                    exact_text=assessment.opening_excerpt or "No opening content was extracted.",
                    source_type="opening 200 words",
                    context=assessment.reason,
                )
            ],
            why_it_matters=(
                "A direct opening gives retrieval systems a concise, self-contained explanation to summarize "
                "or cite before they process deeper page content."
            ),
            recommendation=(
                "Open with one or two sentences that name the offering, audience, and primary outcome using "
                "the same terms as the page title or H1."
            ),
            copy_paste_fix=None,
            impact=4,
            effort=2,
        )

    def _faq_assessment(self, page: CrawledPage, blocks: list[ContentBlock]) -> FaqAssessment:
        faq_schema_evidence = _faq_schema_evidence(page.json_ld)
        visible_faq_headings = [
            block.text
            for block in blocks
            if block.kind == "heading" and _is_faq_heading(block.text)
        ]
        question_headings = [
            block.text
            for block in blocks
            if block.kind == "heading" and _is_question_heading(block.text)
        ]
        unanswered = _unanswered_question_headings(blocks)
        return FaqAssessment(
            has_faq_schema=bool(faq_schema_evidence),
            faq_schema_evidence=faq_schema_evidence,
            visible_faq_headings=visible_faq_headings,
            question_headings=question_headings,
            unanswered_question_headings=unanswered,
        )

    @staticmethod
    def _faq_findings(page: CrawledPage, faq: FaqAssessment) -> list[DiscoverabilityFinding]:
        if not faq.unanswered_question_headings:
            return []
        return [
            _finding(
                title="Question headings do not have visible answers",
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
                affected_url=page.url,
                evidence=[
                    Evidence(
                        page_url=page.url,
                        exact_text=question,
                        source_type="question-style heading",
                        context="No paragraph, list item, or table content appears before the next heading.",
                    )
                    for question in faq.unanswered_question_headings
                ],
                why_it_matters=(
                    "Question-style headings are more useful to answer systems when the visible HTML includes "
                    "a concise answer directly below each question."
                ),
                recommendation="Add a clear answer below each question heading in server-rendered page content.",
                copy_paste_fix=None,
                impact=3,
                effort=2,
            )
        ]

    @staticmethod
    def _list_table_finding(
        page: CrawledPage,
        blocks: list[ContentBlock],
    ) -> DiscoverabilityFinding | None:
        page_words = _word_count(page.text_content)
        list_count = sum(block.kind == "list_item" for block in blocks)
        table_count = sum(block.kind == "table" for block in blocks)
        if page_words <= STRUCTURE_PAGE_WORDS or list_count or table_count:
            return None
        return _finding(
            title="Long page has no lists or tables",
            severity=Severity.LOW,
            confidence=Confidence.HIGH,
            affected_url=page.url,
            evidence=[
                Evidence(
                    page_url=page.url,
                    exact_text=(
                        f"Page word count: {page_words}; detected list items: {list_count}; "
                        f"detected tables: {table_count}."
                    ),
                    source_type="page structure",
                )
            ],
            why_it_matters=(
                "Lists and tables can make long content easier to scan, extract, compare, and cite without "
                "forcing a system to interpret dense prose."
            ),
            recommendation="Where appropriate, convert comparisons, steps, or grouped facts into a bullet list or table.",
            copy_paste_fix=None,
            impact=2,
            effort=2,
        )

    @staticmethod
    def _unsupported_claims_finding(
        page: CrawledPage,
        blocks: list[ContentBlock],
    ) -> DiscoverabilityFinding | None:
        evidence: list[Evidence] = []
        claim_kinds: set[str] = set()
        for block in blocks:
            if block.kind not in {"paragraph", "list_item", "table"} or _has_source_signal(block):
                continue
            matches = _claim_matches(block.text)
            for match, claim_kind in matches:
                claim_kinds.add(claim_kind)
                evidence.append(
                    Evidence(
                        page_url=page.url,
                        exact_text=_sentence_with_match(block.text, match.start()),
                        source_type="confidence-based claim heuristic",
                        context="No nearby source, citation, reference, or URL signal was detected in this content block.",
                    )
                )
        if not evidence:
            return None
        confidence = Confidence.LOW if claim_kinds == {"year"} else Confidence.MEDIUM
        return _finding(
            title="Potentially unsupported claims (confidence-based)",
            severity=Severity.MEDIUM,
            confidence=confidence,
            affected_url=page.url,
            evidence=evidence,
            why_it_matters=(
                "Citable claims are easier to trust when a nearby source, citation, reference, or URL gives "
                "readers a path to supporting material. This check does not state that any claim is false."
            ),
            recommendation="Add a nearby source, citation, reference, or link for factual, statistical, or comparative claims.",
            copy_paste_fix=None,
            impact=3,
            effort=3,
        )

    @staticmethod
    def _chunkability_findings(
        page: CrawledPage,
        blocks: list[ContentBlock],
    ) -> list[DiscoverabilityFinding]:
        findings: list[DiscoverabilityFinding] = []
        for section in _sections(blocks):
            section_text = " ".join(block.text for block in section.blocks)
            section_words = _word_count(section_text)
            if section_words <= LONG_SECTION_WORDS:
                continue
            split_block, split_words = _split_location(section.blocks, section_words)
            heading_text = section.heading.text if section.heading else "introductory content"
            heading_suggestion = (
                f"{heading_text} details" if section.heading else "Key details"
            )
            findings.append(
                _finding(
                    title="Section is too long to be easily chunked",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    affected_url=page.url,
                    evidence=[
                        Evidence(
                            page_url=page.url,
                            exact_text=split_block.text[:200],
                            source_type="heading section",
                            context=(
                                f"Section “{heading_text}” contains {section_words} words. Suggested split "
                                f"after this block, about {split_words} words into the section."
                            ),
                        )
                    ],
                    why_it_matters=(
                        "Very long sections mix multiple ideas and are less likely to be retrieved as a focused, "
                        "self-contained passage."
                    ),
                    recommendation=(
                        f"Split the “{heading_text}” section after the paragraph beginning “{split_block.text[:80]}”. "
                        f"Insert an H3 such as “{heading_suggestion}” before the remaining content, then use a "
                        "bullet list or FAQ for distinct steps or questions."
                    ),
                    copy_paste_fix=None,
                    impact=3,
                    effort=2,
                )
            )
        return findings


def _finding(
    *,
    title: str,
    severity: Severity,
    confidence: Confidence,
    affected_url: str,
    evidence: list[Evidence],
    why_it_matters: str,
    recommendation: str,
    impact: int,
    effort: int,
    copy_paste_fix: str | None = None,
) -> DiscoverabilityFinding:
    """Build a citation finding using the existing shared Pydantic contract."""

    return DiscoverabilityFinding(
        id=f"citation-{uuid4().hex}",
        category=AuditCategory.CITATION_READINESS,
        title=title,
        severity=severity,
        confidence=confidence,
        affected_url=affected_url,
        evidence=evidence,
        why_it_matters=why_it_matters,
        recommendation=recommendation,
        copy_paste_fix=copy_paste_fix,
        impact=impact,
        effort=effort,
    )


def _page_blocks(page: CrawledPage) -> list[ContentBlock]:
    if page.content_blocks:
        return page.content_blocks
    return [ContentBlock(kind="paragraph", text=page.text_content)] if page.text_content else []


def _words(text: str) -> list[str]:
    return WORD_PATTERN.findall(text)


def _word_count(text: str) -> int:
    return len(_words(text))


def _word_limited_excerpt(text: str, limit: int) -> str:
    matches = list(WORD_PATTERN.finditer(text))
    if not matches:
        return ""
    if len(matches) <= limit:
        return text.strip()
    return text[: matches[limit - 1].end()].strip()


def _heading_hierarchy(page: CrawledPage) -> str:
    return " → ".join(f"H{heading.level}: {heading.text}" for heading in page.headings) or "No headings found."


def _heading_level_jumps(page: CrawledPage) -> list[tuple[Heading, Heading]]:
    jumps: list[tuple[Heading, Heading]] = []
    for previous, current in zip(page.headings, page.headings[1:]):
        if current.level > previous.level + 1:
            jumps.append((previous, current))
    return jumps


def _is_generic_heading(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", text).lower()).strip()
    return normalized in GENERIC_HEADINGS


def _opening_text(page: CrawledPage, blocks: list[ContentBlock]) -> str:
    opening_blocks = [
        block.text for block in blocks if block.kind in {"paragraph", "list_item", "table"}
    ]
    return " ".join(opening_blocks) or page.text_content


def _topic_terms(page: CrawledPage) -> set[str]:
    labels = [page.title or "", *(heading.text for heading in page.headings if heading.level == 1)]
    return {
        token.lower()
        for label in labels
        for token in _words(label)
        if len(token) >= 3 and token.lower() not in STOP_WORDS
    }


def _faq_schema_evidence(value: object) -> list[str]:
    evidence: list[str] = []
    if isinstance(value, dict):
        schema_type = value.get("@type")
        types = schema_type if isinstance(schema_type, list) else [schema_type]
        if any(str(item).lower() == "faqpage" for item in types if item):
            evidence.append(f"@type: {schema_type}")
        for nested_value in value.values():
            evidence.extend(_faq_schema_evidence(nested_value))
    elif isinstance(value, list):
        for nested_value in value:
            evidence.extend(_faq_schema_evidence(nested_value))
    return evidence


def _is_faq_heading(text: str) -> bool:
    normalized = text.lower()
    return "faq" in normalized or "frequently asked" in normalized


def _is_question_heading(text: str) -> bool:
    return text.strip().endswith("?") or QUESTION_PREFIX.match(text.strip()) is not None


def _unanswered_question_headings(blocks: list[ContentBlock]) -> list[str]:
    unanswered: list[str] = []
    for index, block in enumerate(blocks):
        if block.kind != "heading" or not _is_question_heading(block.text):
            continue
        has_answer = False
        for following in blocks[index + 1 :]:
            if following.kind == "heading":
                break
            if following.kind in {"paragraph", "list_item", "table"} and following.text:
                has_answer = True
                break
        if not has_answer:
            unanswered.append(block.text)
    return unanswered


def _has_source_signal(block: ContentBlock) -> bool:
    return bool(block.links) or SOURCE_SIGNAL_PATTERN.search(block.text) is not None


def _claim_matches(text: str) -> list[tuple[re.Match[str], str]]:
    matches: list[tuple[re.Match[str], str]] = []
    matches.extend((match, "percentage") for match in PERCENTAGE_PATTERN.finditer(text))
    matches.extend((match, "year") for match in YEAR_PATTERN.finditer(text))
    matches.extend((match, "superlative") for match in SUPERLATIVE_PATTERN.finditer(text))
    return sorted(matches, key=lambda item: item[0].start())


def _sentence_with_match(text: str, position: int) -> str:
    offset = 0
    for sentence in SENTENCE_BOUNDARY.split(text):
        sentence_end = offset + len(sentence)
        if offset <= position <= sentence_end:
            return sentence.strip()
        offset = sentence_end + 1
    return text.strip()


def _sections(blocks: list[ContentBlock]) -> list[ContentSection]:
    sections: list[ContentSection] = []
    current_heading: ContentBlock | None = None
    current_blocks: list[ContentBlock] = []
    for block in blocks:
        if block.kind == "heading":
            if current_blocks:
                sections.append(ContentSection(heading=current_heading, blocks=current_blocks))
            current_heading = block
            current_blocks = []
        else:
            current_blocks.append(block)
    if current_blocks:
        sections.append(ContentSection(heading=current_heading, blocks=current_blocks))
    return sections


def _split_location(blocks: list[ContentBlock], section_words: int) -> tuple[ContentBlock, int]:
    target = min(200, max(1, section_words // 2))
    cumulative_words = 0
    for block in blocks:
        cumulative_words += _word_count(block.text)
        if cumulative_words >= target:
            return block, cumulative_words
    return blocks[-1], cumulative_words
