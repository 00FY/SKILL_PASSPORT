"""
PDF report of a signed skill passport, for recruiters to file or share.

Built with PyMuPDF's HTML layout (already a dependency). The report shows only what the signed passport
contains, plus its signature and a QR code of it; callers must check the signature before rendering.
Every value from the passport is escaped: names, skills and warnings can come from a candidate's resume.
"""
import io
from datetime import datetime
from html import escape
from typing import Any, Iterable, List, Optional

import pymupdf

from ..schemas import PassportDocument

PAGE = pymupdf.paper_rect("a4")
MARGIN = 40
VERDICT_LABEL = {
    "VERIFIED": "Verified by code",
    "PARTIALLY_SUPPORTED": "Partly supported",
    "CLAIMED_ONLY": "No evidence",
    "CONTRADICTED": "Contradicted",
}
VERDICT_COLOR = {
    "VERIFIED": "#047857",
    "PARTIALLY_SUPPORTED": "#b45309",
    "CLAIMED_ONLY": "#52525b",
    "CONTRADICTED": "#b91c1c",
}
AUTHORSHIP_TEXT = {
    "confirmed": "Authorship confirmed",
    "inconclusive": "Authorship check inconclusive",
    "not_explained": "Could not explain own code",
}
CERT_STATUS = {
    "verified": "Issuer verified",
    "issuer_verified": "Issuer verified",
    "pending": "Pending manual check",
    "unverified": "Not verified",
    "issuer_mismatch": "Issued to someone else",
}
MAX_TRACES = 40

CSS = """
* { font-family: sans-serif; }
body { font-size: 9.5px; color: #18181b; }
h1 { font-size: 20px; margin: 0; }
h2 { font-size: 12px; margin: 14px 0 5px 0; color: #3730a3; border-bottom: 1px solid #c7d2fe; padding-bottom: 2px; }
.muted { color: #71717a; }
.small { font-size: 8px; }
.demo { color: #92400e; background-color: #fef3c7; padding: 2px 4px; font-weight: bold; }
table { width: 100%; border-collapse: collapse; }
th { text-align: left; font-size: 8.5px; color: #52525b; border-bottom: 1px solid #a1a1aa; padding: 3px 4px; }
td { padding: 3px 4px; border-bottom: 1px solid #e4e4e7; vertical-align: top; }
.num { text-align: right; }
.big { font-size: 18px; font-weight: bold; }
.box { border: 1px solid #d4d4d8; padding: 6px; }
.mono { font-family: monospace; font-size: 7.5px; }
"""


def _e(value: Any) -> str:
    return escape("" if value is None else str(value))


def _date(iso: Optional[str]) -> str:
    try:
        return datetime.fromisoformat((iso or "").replace("Z", "+00:00")).strftime("%d %b %Y, %H:%M UTC")
    except ValueError:
        return _e(iso)


def _qr_png(text: str) -> Optional[bytes]:
    try:
        import qrcode
    except ImportError:
        return None
    img = qrcode.make(text, box_size=4, border=1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _rows(items: Iterable[str]) -> str:
    return "".join(items)


def _summary(p: PassportDocument) -> str:
    verified = sum(1 for s in p.skills if s.verdict.value == "VERIFIED")
    cells = [
        ("Balanced score", f"{p.overall_score}/100"),
        ("Role match", f"{p.role_match_pct}%"),
        ("Claims verified by code", f"{verified} of {len(p.skills)}"),
        ("Code written by candidate", f"{p.candidate_authorship_pct:.1f}%"),
    ]
    head = "".join(f"<td class='box' style='width:25%'><div class='muted small'>{_e(k)}</div><div class='big'>{_e(v)}</div></td>"
                   for k, v in cells)
    html = f"<table><tr>{head}</tr></table>"
    ps = p.pillar_scores
    if ps:
        weights = ps.weights_used or {}
        pillars = [("Code profile", ps.code_score, "code"), ("Resume", ps.resume_score, "resume"),
                   ("Certificates", ps.cert_score, "certs"), ("Skill assessments", ps.quiz_score, "quiz")]
        rows = _rows(
            f"<tr><td>{name}</td><td class='num'>{'-' if score is None else f'{score}/100'}</td>"
            f"<td class='num'>{'not used' if not weights.get(key) else f'{round(weights[key] * 100)}%'}</td></tr>"
            for name, score, key in pillars
        )
        html += ("<h2>How the balanced score is built</h2><table><tr><th>Pillar</th><th class='num'>Score</th>"
                 f"<th class='num'>Weight</th></tr>{rows}</table>")
    return html


def _skills(p: PassportDocument) -> str:
    rows = []
    for s in p.skills:
        verdict = s.verdict.value
        evidence = s.signals[0] if s.signals else (s.reasoning or "")
        check = s.authorship_check
        extra = ""
        if check and check.status in AUTHORSHIP_TEXT:
            extra = (f"<br/><b>{_e(AUTHORSHIP_TEXT[check.status])}</b>: {check.correct}/{check.total} "
                     f"({'+' if check.points_effect >= 0 else ''}{check.points_effect} pts)")
        rows.append(
            f"<tr><td><b>{_e(s.name)}</b><br/><span class='muted small'>{_e(s.category)} · {_e(s.level)}</span></td>"
            f"<td style='color:{VERDICT_COLOR.get(verdict, '#18181b')}'><b>{_e(VERDICT_LABEL.get(verdict, verdict))}</b></td>"
            f"<td class='num'>{s.final_points}</td><td class='num'>{_e(s.test_grade)}</td>"
            f"<td>{_e(evidence)}{extra}</td></tr>"
        )
    return ("<h2>Claims and evidence</h2><table><tr><th>Skill</th><th>Verdict</th><th class='num'>Points</th>"
            f"<th class='num'>Grade</th><th>Evidence</th></tr>{_rows(rows)}</table>"
            "<p class='muted small'>Points = evidence level (0-10) x grade weight (A 10 … E 2) + consistency bonus, "
            "max 100; contradicted claims get a fixed score.</p>")


def _problems(p: PassportDocument) -> str:
    if not p.refusal_panel:
        return ""
    rows = _rows(
        f"<tr><td><b>{_e(r.claim)}</b></td><td>{_e(r.reason)}"
        f"{'<br/><span class=muted>' + _e(r.evidence_found) + '</span>' if r.evidence_found else ''}</td>"
        f"<td>{_e(r.suggested_remedy or '')}</td></tr>"
        for r in p.refusal_panel
    )
    return f"<h2>Problems found</h2><table><tr><th>Claim</th><th>Why</th><th>How to fix</th></tr>{rows}</table>"


def _certificates(p: PassportDocument) -> str:
    if not p.certificates:
        return ""
    rows = _rows(
        f"<tr><td><b>{_e(c.certificate_name)}</b><br/><span class='muted'>{_e(c.issuer)}</span></td>"
        f"<td>{_e(CERT_STATUS.get(c.issuer_status, c.issuer_status))}"
        f"{'<br/><span class=muted>' + _e(c.mismatch_reason) + '</span>' if c.mismatch_reason else ''}</td>"
        f"<td>{_e((c.issuer_record or {}).get('recipient_name') or c.candidate_name or '')}</td>"
        f"<td class='mono'>{_e(c.verify_url or '')}</td></tr>"
        for c in p.certificates
    )
    return ("<h2>Certificates</h2><table><tr><th>Certificate</th><th>Status</th><th>Issued to</th>"
            f"<th>Issuer link</th></tr>{rows}</table>")


def _alerts(p: PassportDocument) -> str:
    parts = []
    if p.security_alerts:
        rows = _rows(f"<tr><td>{_e(a.severity)}</td><td>{_e(a.raw_payload_snippet)}</td><td>{_e(a.action_taken)}</td></tr>"
                     for a in p.security_alerts)
        parts.append("<h2>Security alerts in the resume</h2><table><tr><th>Severity</th><th>Found</th>"
                     f"<th>Action</th></tr>{rows}</table>")
    if p.warnings:
        parts.append("<h2>Notes from the analysis</h2><ul>" + _rows(f"<li>{_e(w)}</li>" for w in p.warnings) + "</ul>")
    return "".join(parts)


def _plan(p: PassportDocument) -> str:
    if not p.learning_plan:
        return ""
    rows = _rows(f"<tr><td>{_e(i.action)}</td><td>{_e(i.skill)}</td><td>{_e(i.potential_impact)}</td></tr>"
                 for i in p.learning_plan)
    return ("<h2>Suggested next steps for the candidate</h2><table><tr><th>Action</th><th>Skill</th>"
            f"<th>Impact</th></tr>{rows}</table>")


def _audit(p: PassportDocument) -> str:
    traces = (p.audit_log.traces if p.audit_log else [])[-MAX_TRACES:]
    if not traces:
        return ""
    rows = _rows(f"<tr><td>{_e(t.target)}</td><td class='mono'>{_e(t.rule_applied)}</td><td>{_e(t.verdict_reached)}</td></tr>"
                 for t in traces)
    return ("<h2>Rules applied (audit trail)</h2><table><tr><th>Target</th><th>Rule</th><th>Result</th></tr>"
            f"{rows}</table>")


def _verification(p: PassportDocument, has_qr: bool) -> str:
    qr = "<img src='qr.png' width='84' height='84'/>" if has_qr else ""
    return (
        "<h2>Verification</h2><table><tr>"
        f"<td style='width:90px'>{qr}</td><td>"
        f"<div>Issued {_date(p.issued_at)}{' · passport ' + _e(p.passport_id) if p.passport_id else ''}</div>"
        f"<div class='mono'>{_e(p.tamper_proof_hash)}</div>"
        "<div class='muted small'>This report was generated from a passport whose signature was valid at the time. "
        "To check a copy of the passport JSON, send it to /api/verify-signature on the issuing server: any change to "
        "a score, verdict or name makes the signature fail. The QR code holds the passport id and signature.</div>"
        "</td></tr></table>"
    )


def build_html(p: PassportDocument, has_qr: bool) -> str:
    repos = ", ".join(_e(u) for u in (p.repo_urls or ([p.repo_url] if p.repo_url else [])))
    demo = "<span class='demo'>DEMO DATA: sample evidence, not a real candidate</span><br/>" \
        if p.evidence_source == "demo" else ""
    header = (
        f"{demo}<h1>{_e(p.candidate_name)}</h1>"
        f"<div class='muted'>{_e(p.applied_role)} · Skill Passport report</div>"
        + (f"<div class='small muted'>GitHub: {_e(p.github_username)}</div>" if p.github_username else "")
        + (f"<div class='small muted'>Repositories analysed: {repos}</div>" if repos else "")
        + f"<div class='small muted'>{p.total_commits} commits · {p.active_months} active month(s)</div>"
    )
    return (
        f"<body>{header}{_summary(p)}{_skills(p)}{_problems(p)}{_certificates(p)}{_alerts(p)}{_plan(p)}"
        f"{_verification(p, has_qr)}{_audit(p)}</body>"
    )


def render_pdf(p: PassportDocument) -> bytes:
    qr = _qr_png(f"SKILL-PASSPORT|{p.passport_id or ''}|{p.tamper_proof_hash}")
    archive = pymupdf.Archive()
    if qr:
        archive.add(qr, "qr.png")
    story = pymupdf.Story(html=build_html(p, bool(qr)), user_css=CSS, archive=archive)

    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    where = PAGE + (MARGIN, MARGIN, -MARGIN, -MARGIN - 14)
    more = True
    while more:
        device = writer.begin_page(PAGE)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()

    # Footer on every page: who, which passport, page x of y
    doc = pymupdf.open("pdf", buf.getvalue())
    footer = f"Skill Passport · {p.candidate_name} · signature {p.tamper_proof_hash[-16:]}"
    for i, page in enumerate(doc, start=1):
        y = PAGE.height - MARGIN + 6
        page.insert_text((MARGIN, y), footer[:110], fontsize=7, color=(0.45, 0.45, 0.48))
        page.insert_text((PAGE.width - MARGIN - 50, y), f"Page {i} of {doc.page_count}", fontsize=7,
                         color=(0.45, 0.45, 0.48))
    doc.set_metadata({"title": f"Skill Passport: {p.candidate_name}", "creator": "Skill Passport",
                      "subject": "Evidence-based skill report"})
    return doc.tobytes(garbage=3, deflate=True)
