from __future__ import annotations

import json
import re
import unicodedata
from io import BytesIO
from html import unescape
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen
from typing import Iterable

import pandas as pd
import streamlit as st

from processing import export_workbook, run_pipeline


st.set_page_config(
    page_title="Packaging Instruction Enrichment & Decision Maker",
    layout="wide",
)


REVIEW_STATUS_OPTIONS = [
    "Neriešené",
    "Rieši sa",
    "Čaká na IT",
    "Schválené",
    "Hotovo",
]

FINAL_ACTION_OPTIONS = [
    "Ponechať balenie",
    "Odstrániť balenie",
    "Upraviť parameter",
    "Odovzdať na IT",
    "Manuálna analýza",
]

DISPLAY_CASE_COLUMNS = [
    "case_id",
    "priority",
    "Kód produktu",
    "Název produktu",
    "instruction_category",
    "report_count",
    "recommended_action",
    "confidence",
    "status",
]

REVIEW_EXPORT_COLUMNS = [
    "case_id",
    "Kód produktu",
    "Název produktu",
    "instruction_category",
    "report_count",
    "recommended_action",
    "suggested_parameter_to_check",
    "confidence",
    "review_status",
    "final_action",
    "validator_note",
    "decision_reason",
    "validator_checklist",
]


def read_excel_upload(uploaded_file) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()
    return pd.read_excel(uploaded_file, dtype=object, engine="openpyxl")


def default_select_all(options: Iterable) -> list:
    return list(options)


def init_session_state() -> None:
    st.session_state.setdefault("review_data", {})
    st.session_state.setdefault("selected_case_id", None)
    st.session_state.setdefault("review_widget_case_id", None)
    st.session_state.setdefault("review_status_widget", REVIEW_STATUS_OPTIONS[0])
    st.session_state.setdefault("final_action_widget", FINAL_ACTION_OPTIONS[0])
    st.session_state.setdefault("validator_note_widget", "")


ALZA_BASE_URL = "https://www.alza.sk"
ALZA_SEARCH_URL = f"{ALZA_BASE_URL}/search.htm?exps={{query}}"
ALZA_TIMEOUT_SECONDS = 20

PACKAGING_KEYWORDS = [
    "obal",
    "baleni",
    "balenie",
    "krabic",
    "krabica",
    "box",
    "foli",
    "vypln",
    "poskoz",
    "rozbit",
    "prask",
    "zdeform",
    "chybajuc",
    "chybajuci",
    "prislusenst",
]

QUALITY_KEYWORDS = [
    "nefung",
    "vada",
    "porucha",
    "reklam",
    "zavad",
    "poskoden",
    "pokaz",
    "nevyhov",
]


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_for_matching(value: str | None) -> str:
    if not value:
        return ""
    text = _strip_accents(str(value)).lower()
    text = re.sub(r"[^a-z0-9%]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _http_get(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Accept-Language": "sk-SK,sk;q=0.9,cs;q=0.8,en;q=0.7",
        },
    )
    with urlopen(request, timeout=ALZA_TIMEOUT_SECONDS) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _strip_html_tags(html_text: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html_text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_json_ld_objects(html_text: str) -> list[dict]:
    objects: list[dict] = []
    for match in re.finditer(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html_text, flags=re.I | re.S):
        raw = match.group(1).strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            objects.append(parsed)
        elif isinstance(parsed, list):
            objects.extend(item for item in parsed if isinstance(item, dict))
    return objects


def _find_product_dict(objects: list[dict]) -> dict | None:
    def _walk(value):
        if isinstance(value, dict):
            if _normalize_for_matching(str(value.get("@type", ""))) == "product":
                return value
            for nested_value in value.values():
                found = _walk(nested_value)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = _walk(item)
                if found is not None:
                    return found
        return None

    for obj in objects:
        found = _walk(obj)
        if found is not None:
            return found
    return None


def _best_text_snippets(text: str, keywords: list[str], limit: int = 3) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    snippets: list[str] = []
    normalized_keywords = [_normalize_for_matching(keyword) for keyword in keywords]
    for sentence in sentences:
        normalized_sentence = _normalize_for_matching(sentence)
        if not normalized_sentence:
            continue
        if any(keyword in normalized_sentence for keyword in normalized_keywords):
            compact = re.sub(r"\s+", " ", sentence).strip()
            if compact and compact not in snippets:
                snippets.append(compact)
        if len(snippets) >= limit:
            break
    return snippets


def _extract_claim_percentages(text: str) -> dict[str, float | None]:
    normalized = _normalize_for_matching(text)
    patterns = {
        "complaints_pct": [
            r"(\d{1,2}(?:[.,]\d+)?)\s*%\s*(?:reklamaci|reklamacie|reklamacii|reklamac)",
            r"reklamaci[^\d]{0,40}(\d{1,2}(?:[.,]\d+)?)\s*%",
        ],
        "withdrawals_pct": [
            r"(\d{1,2}(?:[.,]\d+)?)\s*%\s*(?:odstoupeni|odstupeni|odstupenie|vrateni)",
            r"(?:odstoupeni|odstupeni|odstupenie)[^\d]{0,40}(\d{1,2}(?:[.,]\d+)?)\s*%",
        ],
    }
    result: dict[str, float | None] = {"complaints_pct": None, "withdrawals_pct": None}
    for key, regexes in patterns.items():
        for regex in regexes:
            match = re.search(regex, normalized, flags=re.I)
            if match:
                try:
                    result[key] = float(match.group(1).replace(",", "."))
                except ValueError:
                    result[key] = None
                break
    return result


def _score_packaging_signal(text: str) -> tuple[str, list[str]]:
    normalized = _normalize_for_matching(text)
    packaging_hits = [keyword for keyword in PACKAGING_KEYWORDS if keyword in normalized]
    quality_hits = [keyword for keyword in QUALITY_KEYWORDS if keyword in normalized]
    evidence: list[str] = []
    if packaging_hits:
        evidence.append("Packaging-related keywords: " + ", ".join(sorted(set(packaging_hits))))
    if quality_hits:
        evidence.append("Quality-related keywords: " + ", ".join(sorted(set(quality_hits))))

    if packaging_hits and len(packaging_hits) >= len(quality_hits):
        return "Likely packaging-related issue", evidence
    if quality_hits and len(quality_hits) > len(packaging_hits):
        return "Likely product-quality / other issue", evidence
    if packaging_hits:
        return "Possible packaging issue", evidence
    if quality_hits:
        return "Possible product-quality issue", evidence
    return "Insufficient review evidence", evidence


def _product_report_summary(result) -> pd.DataFrame:
    df = result.cases_enriched.copy()
    if df.empty or "Kód produktu" not in df.columns:
        return pd.DataFrame(columns=["Kód produktu", "Názov produktu", "report_count", "case_count"])

    group_cols = [column for column in ["Kód produktu", "Názov produktu"] if column in df.columns]
    summary = (
        df.groupby(group_cols, dropna=False)
        .agg(
            report_count=("report_count", "sum"),
            case_count=("case_id", "count"),
        )
        .reset_index()
        .sort_values(by=["report_count", "case_count"], ascending=[False, False], kind="mergesort")
    )
    return summary.reset_index(drop=True)


@st.cache_data(show_spinner=False, ttl=6 * 60 * 60)
def fetch_alza_review_analysis(product_name: str, product_code: str | None = None) -> dict:
    query = product_name.strip() or (product_code or "").strip()
    search_url = ALZA_SEARCH_URL.format(query=quote_plus(query))

    try:
        search_html = _http_get(search_url)
    except Exception as exc:
        return {
            "status": "error",
            "product_query": query,
            "search_url": search_url,
            "error": f"Search request failed: {exc}",
        }

    candidate_urls: list[str] = []
    for href in re.findall(r'href="([^"]+)"', search_html, flags=re.I):
        href = href.strip()
        if not href or href.startswith("#"):
            continue
        if "search.htm" in href.lower():
            continue
        if not re.search(r"/\d+\.htm(?:\?|$)", href):
            continue
        candidate_urls.append(urljoin(ALZA_BASE_URL, href))

    product_url = candidate_urls[0] if candidate_urls else None
    if product_url is None:
        return {
            "status": "not_found",
            "product_query": query,
            "search_url": search_url,
            "error": "No product link found on the Alza search page.",
        }

    try:
        product_html = _http_get(product_url)
    except Exception as exc:
        return {
            "status": "error",
            "product_query": query,
            "search_url": search_url,
            "product_url": product_url,
            "error": f"Product page request failed: {exc}",
        }

    json_ld_objects = _extract_json_ld_objects(product_html)
    product_ld = _find_product_dict(json_ld_objects)

    title_match = re.search(r"<title>(.*?)</title>", product_html, flags=re.I | re.S)
    page_title = unescape(title_match.group(1)).strip() if title_match else None
    if page_title:
        page_title = re.sub(r"\s+\|\s+Alza.*$", "", page_title).strip()

    aggregate = product_ld.get("aggregateRating", {}) if product_ld else {}
    rating_value = aggregate.get("ratingValue")
    review_count = aggregate.get("reviewCount")
    try:
        rating_value = float(str(rating_value).replace(",", ".")) if rating_value is not None else None
    except ValueError:
        rating_value = None
    try:
        review_count = int(float(str(review_count).replace(",", "."))) if review_count is not None else None
    except ValueError:
        review_count = None

    visible_text = _strip_html_tags(product_html)
    snippets = _best_text_snippets(visible_text, PACKAGING_KEYWORDS + QUALITY_KEYWORDS, limit=5)
    percentages = _extract_claim_percentages(visible_text)
    verdict, evidence = _score_packaging_signal(visible_text)

    return {
        "status": "ok",
        "product_query": query,
        "search_url": search_url,
        "product_url": product_url,
        "page_title": page_title,
        "rating_value": rating_value,
        "review_count": review_count,
        "complaints_pct": percentages["complaints_pct"],
        "withdrawals_pct": percentages["withdrawals_pct"],
        "verdict": verdict,
        "evidence": evidence,
        "snippets": snippets,
    }


def get_top_product_for_review(result) -> pd.Series | None:
    summary = _product_report_summary(result)
    if summary.empty:
        return None

    top_row = summary.iloc[0]
    product_code = top_row.get("Kód produktu")
    product_name = top_row.get("Názov produktu")
    cases = result.cases_enriched
    filtered = cases[cases["Kód produktu"].astype(str) == str(product_code)] if "Kód produktu" in cases.columns else cases.head(0)
    selected_case = filtered.sort_values(by=["report_count"], ascending=[False], kind="mergesort").head(1)
    if selected_case.empty:
        return pd.Series(
            {
                "Kód produktu": product_code,
                "Názov produktu": product_name,
                "product_report_count": top_row.get("report_count"),
                "product_case_count": top_row.get("case_count"),
            }
        )

    case_row = selected_case.iloc[0].copy()
    case_row["product_report_count"] = top_row.get("report_count")
    case_row["product_case_count"] = top_row.get("case_count")
    return case_row


def get_uploaded_result() -> tuple[pd.DataFrame, pd.DataFrame, object | None]:
    reports_file = st.session_state.get("reports_file_upload")
    products_file = st.session_state.get("products_file_upload")
    if reports_file is None or products_file is None:
        return pd.DataFrame(), pd.DataFrame(), None

    reports_raw = read_excel_upload(reports_file)
    products_raw = read_excel_upload(products_file)
    result = run_pipeline(
        reports_raw,
        products_raw,
        top_n=int(st.session_state.get("top_n_input", 100)),
        exclude_stitok=bool(st.session_state.get("exclude_stitok_input", True)),
        instruction_categories=None,
        min_report_count=int(st.session_state.get("min_report_count_input", 0)),
        product_match_status=["Produkt nájdený"],
        has_risk_flag=None,
        trigger_detected=None,
    )
    return reports_raw, products_raw, result


def ensure_review_defaults(case_id: str, row: pd.Series) -> dict[str, str]:
    review_data = st.session_state.review_data
    if case_id in review_data:
        return review_data[case_id]

    recommended_action = str(row.get("recommended_action", "") or "")
    default_review_status = "Neriešené"
    if recommended_action == "Odovzdať na IT":
        default_review_status = "Čaká na IT"
    elif recommended_action == "Ponechať balenie":
        default_review_status = "Schválené"
    elif recommended_action in {"Preveriť odstránenie balenia", "Odstrániť balenie"}:
        default_review_status = "Rieši sa"

    default_final_action = recommended_action if recommended_action in FINAL_ACTION_OPTIONS else "Manuálna analýza"
    review_data[case_id] = {
        "review_status": default_review_status,
        "final_action": default_final_action,
        "validator_note": "",
    }
    return review_data[case_id]


def sync_review_widgets(case_id: str, row: pd.Series) -> None:
    if st.session_state.review_widget_case_id == case_id:
        return
    review_values = ensure_review_defaults(case_id, row)
    st.session_state.review_widget_case_id = case_id
    st.session_state.review_status_widget = review_values["review_status"]
    st.session_state.final_action_widget = review_values["final_action"]
    st.session_state.validator_note_widget = review_values["validator_note"]


def save_current_review(case_id: str) -> None:
    st.session_state.review_data[case_id] = {
        "review_status": st.session_state.review_status_widget,
        "final_action": st.session_state.final_action_widget,
        "validator_note": st.session_state.validator_note_widget.strip(),
    }


def build_reviewed_cases(result) -> pd.DataFrame:
    rows = []
    for _, row in result.cases_enriched.iterrows():
        case_id = row.get("case_id")
        review_values = ensure_review_defaults(str(case_id), row)
        rows.append(
            {
                "case_id": case_id,
                "Kód produktu": row.get("Kód produktu"),
                "Název produktu": row.get("Název produktu"),
                "instruction_category": row.get("instruction_category"),
                "report_count": row.get("report_count"),
                "recommended_action": row.get("recommended_action"),
                "suggested_parameter_to_check": row.get("suggested_parameter_to_check"),
                "confidence": row.get("confidence"),
                "review_status": review_values["review_status"],
                "final_action": review_values["final_action"],
                "validator_note": review_values["validator_note"],
                "decision_reason": row.get("decision_reason"),
                "validator_checklist": row.get("validator_checklist"),
            }
        )
    return pd.DataFrame(rows)


def reviewed_cases_bytes(reviewed_cases: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        reviewed_cases.to_excel(writer, sheet_name="reviewed_cases", index=False)
    return buffer.getvalue()


def render_dashboard(result) -> None:
    st.subheader("Key metrics")
    metric_order = [
        ("total_reports", "Total reports"),
        ("total_cases", "Total cases"),
        ("matched_products_count", "Matched products"),
        ("invalid_reports_count", "Invalid reports"),
        ("total_ai_input_rows", "AI input rows"),
    ]
    metric_values = result.summary[result.summary["metric"].isin([item[0] for item in metric_order])].set_index("metric")["value"].to_dict()
    metric_cols = st.columns(len(metric_order))
    for idx, (metric_key, metric_label) in enumerate(metric_order):
        with metric_cols[idx]:
            st.metric(metric_label, int(metric_values.get(metric_key, 0)))

    action_counts = (
        result.cases_enriched.groupby("recommended_action", dropna=False)
        .size()
        .reset_index(name="case_count")
        .sort_values(by=["case_count", "recommended_action"], ascending=[False, True], kind="mergesort")
    )
    st.subheader("Counts by recommended_action")
    if not action_counts.empty:
        action_card_rows = [action_counts.iloc[i:i + 4] for i in range(0, len(action_counts), 4)]
        for chunk in action_card_rows:
            cols = st.columns(len(chunk))
            for col, (_, row) in zip(cols, chunk.iterrows()):
                with col:
                    st.metric(str(row["recommended_action"]), int(row["case_count"]))
    st.dataframe(action_counts, use_container_width=True, hide_index=True)
    if not action_counts.empty:
        chart_data = action_counts.set_index("recommended_action")[["case_count"]]
        st.bar_chart(chart_data)

    matrix = (
        result.cases_enriched.groupby(["instruction_category", "recommended_action"], dropna=False)
        .size()
        .reset_index(name="case_count")
        .sort_values(by=["instruction_category", "case_count", "recommended_action"], ascending=[True, False, True], kind="mergesort")
    )
    st.subheader("Counts by instruction_category and recommended_action")
    st.dataframe(matrix, use_container_width=True, hide_index=True)


def render_customer_online_review(result) -> None:
    st.subheader("Customer online review")
    st.caption("This tab starts with the product that has the most reports and tries to match it with the current Alza product page.")

    summary = _product_report_summary(result)
    if summary.empty:
        st.info("No products available for review yet.")
        return

    top_options = [
        f"{row['Názov produktu']} [{row['Kód produktu']}] - reports: {int(row['report_count'])}, cases: {int(row['case_count'])}"
        for _, row in summary.head(20).iterrows()
    ]
    selected_label = st.selectbox(
        "Product to review",
        options=top_options,
        index=0,
        help="The first item is the product with the highest total report count.",
    )
    selected_index = top_options.index(selected_label)
    selected_summary = summary.iloc[selected_index]

    selected_code = selected_summary.get("Kód produktu")
    selected_name = selected_summary.get("Názov produktu")
    selected_code_text = None if pd.isna(selected_code) else str(selected_code)
    selected_name_text = "" if pd.isna(selected_name) else str(selected_name)
    analysis = fetch_alza_review_analysis(
        selected_name_text,
        selected_code_text,
    )

    info_cols = st.columns(4)
    with info_cols[0]:
        st.metric("Report count", int(selected_summary.get("report_count") or 0))
    with info_cols[1]:
        st.metric("Case count", int(selected_summary.get("case_count") or 0))
    with info_cols[2]:
        st.metric("Alza rating", "-" if analysis.get("rating_value") is None else f"{analysis.get('rating_value'):.1f}/5")
    with info_cols[3]:
        st.metric("Review count", "-" if analysis.get("review_count") is None else int(analysis.get("review_count")))

    st.markdown("**Product**")
    product_details = pd.DataFrame(
        [
            {
                "Kód produktu": selected_code,
                "Názov produktu": selected_name,
                "Search query": analysis.get("product_query"),
                "Search URL": analysis.get("search_url"),
                "Product URL": analysis.get("product_url"),
                "Page title": analysis.get("page_title"),
            }
        ]
    )
    st.dataframe(product_details, use_container_width=True, hide_index=True)

    if analysis.get("status") != "ok":
        st.warning(analysis.get("error", "Online review lookup failed."))
        return

    verdict = analysis.get("verdict", "Insufficient review evidence")
    if verdict == "Likely packaging-related issue":
        st.error(verdict)
    elif verdict == "Possible packaging issue":
        st.warning(verdict)
    elif verdict == "Likely product-quality / other issue":
        st.info(verdict)
    else:
        st.info(verdict)

    review_metrics = st.columns(2)
    with review_metrics[0]:
        complaints_pct = analysis.get("complaints_pct")
        st.metric("% complaints / claims", "-" if complaints_pct is None else f"{complaints_pct:.1f}%")
    with review_metrics[1]:
        withdrawals_pct = analysis.get("withdrawals_pct")
        st.metric("% withdrawals / returns", "-" if withdrawals_pct is None else f"{withdrawals_pct:.1f}%")

    if analysis.get("evidence"):
        st.markdown("**Evidence**")
        for line in analysis["evidence"]:
            st.write(f"- {line}")

    snippets = analysis.get("snippets") or []
    st.markdown("**Review snippets**")
    if snippets:
        for snippet in snippets[:5]:
            st.write(f"- {snippet}")
    else:
        st.write("No review snippets were found in the page text.")

    st.markdown("**Interpretation**")
    if "packaging" in verdict.lower():
        st.success("The current page text suggests packaging could be part of the issue, but this is heuristic and should be confirmed manually.")
    elif "quality" in verdict.lower():
        st.info("The current page text points more toward product quality or a non-packaging issue.")
    else:
        st.info("There is not enough review evidence on the page text to make a reliable call.")


def render_case_detail(case_row: pd.Series) -> None:
    st.subheader("Case detail")

    sections = [
        (
            "Product",
            ["case_id", "Kód produktu", "Název produktu", "Segment1", "Segment2", "Segment3"],
        ),
        (
            "Reported instruction",
            ["Přeložené instrukce", "report_count", "unique_users_count", "first_reported_at", "last_reported_at"],
        ),
        (
            "System reason",
            ["main_trigger_parameter", "trigger_parameter_value", "trigger_detected", "active_risk_parameters", "has_risk_flag"],
        ),
        (
            "Recommended decision",
            ["recommended_action", "suggested_parameter_to_check", "confidence", "decision_reason"],
        ),
    ]

    for title, columns in sections:
        present_columns = [column for column in columns if column in case_row.index]
        st.markdown(f"**{title}**")
        if present_columns:
            data = {column: [case_row.get(column)] for column in present_columns}
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    st.markdown("**Validator checklist**")
    checklist = str(case_row.get("validator_checklist", "") or "")
    checklist_items = [item.strip() for item in checklist.split(";") if item.strip()]
    if checklist_items:
        for item in checklist_items:
            st.write(f"- {item}")
    else:
        st.write("No checklist available.")


def render_decision_review(result) -> None:
    review_df = result.cases_enriched.copy()

    filter_row_1 = st.columns(4)
    with filter_row_1[0]:
        recommended_action_filter = st.multiselect(
            "Recommended action",
            options=sorted(review_df["recommended_action"].dropna().astype(str).unique().tolist()),
            default=sorted(review_df["recommended_action"].dropna().astype(str).unique().tolist()),
        )
    with filter_row_1[1]:
        instruction_category_filter = st.multiselect(
            "Instruction category",
            options=sorted(review_df["instruction_category"].dropna().astype(str).unique().tolist()),
            default=sorted(review_df["instruction_category"].dropna().astype(str).unique().tolist()),
        )
    with filter_row_1[2]:
        priority_filter = st.multiselect(
            "Priority",
            options=sorted(review_df["priority"].dropna().astype(str).unique().tolist()),
            default=sorted(review_df["priority"].dropna().astype(str).unique().tolist()),
        )
    with filter_row_1[3]:
        confidence_filter = st.multiselect(
            "Confidence",
            options=sorted(review_df["confidence"].dropna().astype(str).unique().tolist()),
            default=sorted(review_df["confidence"].dropna().astype(str).unique().tolist()),
        )

    filter_row_2 = st.columns(4)
    with filter_row_2[0]:
        product_match_status_filter = st.multiselect(
            "Product match status",
            options=sorted(review_df["product_match_status"].dropna().astype(str).unique().tolist()),
            default=sorted(review_df["product_match_status"].dropna().astype(str).unique().tolist()),
        )
    with filter_row_2[1]:
        trigger_detected_filter = st.multiselect(
            "Trigger detected",
            options=sorted(review_df["trigger_detected"].dropna().astype(str).unique().tolist()),
            default=sorted(review_df["trigger_detected"].dropna().astype(str).unique().tolist()),
        )
    with filter_row_2[2]:
        has_risk_flag_filter = st.multiselect(
            "Has risk flag",
            options=sorted(review_df["has_risk_flag"].dropna().astype(str).unique().tolist()),
            default=sorted(review_df["has_risk_flag"].dropna().astype(str).unique().tolist()),
        )
    with filter_row_2[3]:
        minimum_report_count = st.number_input("Minimum report_count", min_value=0, value=0, step=1)

    filtered = review_df.copy()
    for column, values in [
        ("recommended_action", recommended_action_filter),
        ("instruction_category", instruction_category_filter),
        ("priority", priority_filter),
        ("confidence", confidence_filter),
        ("product_match_status", product_match_status_filter),
        ("trigger_detected", trigger_detected_filter),
        ("has_risk_flag", has_risk_flag_filter),
    ]:
        if values:
            filtered = filtered[filtered[column].astype(str).isin(values)]

    if minimum_report_count:
        filtered = filtered[filtered["report_count"] >= minimum_report_count]

    display_columns = [column for column in DISPLAY_CASE_COLUMNS if column in filtered.columns]
    st.subheader("Case list")
    st.dataframe(filtered.loc[:, display_columns], use_container_width=True, hide_index=True)

    case_options = filtered["case_id"].dropna().astype(str).tolist()
    if not case_options:
        st.info("No cases match the current filters.")
        return

    selected_case_id = st.selectbox("Select case_id", options=case_options, index=0)
    selected_row = review_df.loc[review_df["case_id"].astype(str) == selected_case_id].iloc[0]
    sync_review_widgets(selected_case_id, selected_row)

    detail_col_1, detail_col_2 = st.columns([2, 1])
    with detail_col_1:
        render_case_detail(selected_row)
    with detail_col_2:
        st.subheader("Review fields")
        st.selectbox("Review status", options=REVIEW_STATUS_OPTIONS, key="review_status_widget")
        st.selectbox("Final action", options=FINAL_ACTION_OPTIONS, key="final_action_widget")
        st.text_area("Validator note", key="validator_note_widget", height=180)
        if st.button("Save review"):
            save_current_review(selected_case_id)
            st.success("Review saved for this case.")
        else:
            save_current_review(selected_case_id)


def render_upload_processing(result) -> None:
    st.subheader("Upload & Processing")
    upload_cols = st.columns(3)
    with upload_cols[0]:
        st.file_uploader("Chybné instrukcie Excel", type=["xlsx"], key="reports_file_upload")
    with upload_cols[1]:
        st.file_uploader("Produkty a vlastnosti Excel", type=["xlsx"], key="products_file_upload")
    with upload_cols[2]:
        st.file_uploader(
            "Baliace pravidlá Excel (optional)",
            type=["xlsx"],
            key="packing_rules_file_upload",
            help="Optional in this MVP. The pipeline does not depend on it.",
        )

    settings_cols = st.columns(3)
    with settings_cols[0]:
        st.number_input("TOP N", min_value=1, value=100, step=1, key="top_n_input")
    with settings_cols[1]:
        st.checkbox("Exclude Štítok", value=True, key="exclude_stitok_input")
    with settings_cols[2]:
        st.number_input("Minimum report_count", min_value=0, value=0, step=1, key="min_report_count_input")

    reports_file = st.session_state.get("reports_file_upload")
    products_file = st.session_state.get("products_file_upload")
    if reports_file is None or products_file is None:
        st.info("Upload Chybné instrukcie and Produkty a vlastnosti to run the pipeline.")
    elif result is not None:
        if result.warnings:
            st.subheader("Warnings")
            for warning in result.warnings:
                st.warning(warning)
        st.success("Processing complete. Open the Dashboard and Decision Review tabs.")


def main() -> None:
    init_session_state()
    st.title("Packaging Instruction Enrichment & Decision Maker")
    st.caption("Turn packaging-instruction reviews into a clearer decision workflow for non-technical users.")

    reports_raw, products_raw, result = get_uploaded_result()

    tabs = st.tabs(["Upload & Processing", "Dashboard", "Decision Review", "Customer online review", "Download"])

    with tabs[0]:
        render_upload_processing(result)

    with tabs[1]:
        if result is None:
            st.info("Upload both required files in the first tab to see the dashboard.")
        else:
            render_dashboard(result)

    with tabs[2]:
        if result is None:
            st.info("Upload both required files in the first tab to review cases.")
        else:
            render_decision_review(result)

    with tabs[3]:
        if result is None:
            st.info("Upload both required files in the first tab to look up online reviews.")
        else:
            render_customer_online_review(result)

    with tabs[4]:
        if result is None:
            st.info("Upload both required files to enable downloads.")
        else:
            st.subheader("Processed workbook")
            workbook_bytes = export_workbook(result)
            st.download_button(
                "Download processed Excel workbook",
                data=workbook_bytes,
                file_name="Chybne_instrukce_processed.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            reviewed_cases = build_reviewed_cases(result)
            if not reviewed_cases.empty:
                st.subheader("Reviewed cases")
                reviewed_bytes = reviewed_cases_bytes(reviewed_cases)
                st.download_button(
                    "Download reviewed cases",
                    data=reviewed_bytes,
                    file_name="reviewed_cases.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                st.dataframe(reviewed_cases, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
