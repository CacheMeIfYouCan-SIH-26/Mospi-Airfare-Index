import re
from typing import Optional

from src.engineering.schemas import UnbundledFare


_BASE_FARE_RE = re.compile(
    r"base(?:\s*&?\'?s?|\s*(?:fare|ticket|rate))?\s*[:=\-\s]*\s*(?:Rs\.?|INR|₹)?\s*([0-9,]+(?:\.\d+)?)",
    re.IGNORECASE,
)
_TAX_RE = re.compile(
    r"(?:tax(?:es)?|tax\s*&\s*(?:airport\s*)?(?:udf|user\s*development\s*fee)|airport\s*(?:udf|fee)|udf)\s*[:=\-\s]*\s*(?:Rs\.?|INR|₹)?\s*([0-9,]+(?:\.\d+)?)",
    re.IGNORECASE,
)
_CONVENIENCE_RE = re.compile(
    r"(?:convenience(?:\s*fee)?|management\s*fee|convenience\s*/\s*management\s*fee)\s*[:=\-\s]*\s*(?:Rs\.?|INR|₹)?\s*([0-9,]+(?:\.\d+)?)",
    re.IGNORECASE,
)
_TOTAL_RE = re.compile(
    r"(?:total(?:\s*quote)?|final(?:\s*(?:price|fare|total))?)\s*[:=\-\s]*\s*(?:Rs\.?|INR|₹)?\s*([0-9,]+(?:\.\d+)?)",
    re.IGNORECASE,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(snippet: str) -> str:
    return _HTML_TAG_RE.sub(" ", snippet)


def _to_float(raw: str) -> float:
    return float(raw.replace(",", "").replace("Rs.", "").replace("INR", "").strip())


def _extract(compiled_re: "re.Pattern", text: str) -> Optional[float]:
    match = compiled_re.search(text)
    if match:
        return _to_float(match.group(1))
    return None


def unbundle_fare(fare_string: str, total_quote: Optional[float] = None) -> UnbundledFare:
    """Parses a raw fare string / HTML snippet into granular fare components.

    Extracts base fare, tax & airport UDF, and convenience/management fee using
    regular expressions. If explicit tax extraction fails and a `total_quote` is
    provided (either as an argument or found in the string), a proportional
    fallback is applied: base_fare = total_quote * 0.82 and tax_udf = total_quote * 0.18.
    """
    text = _strip_html(fare_string)

    base_fare = _extract(_BASE_FARE_RE, text)
    tax_udf = _extract(_TAX_RE, text)
    convenience_fee = _extract(_CONVENIENCE_RE, text)

    if total_quote is None:
        total_raw = _extract(_TOTAL_RE, text)
        total_quote = total_quote or total_raw

    if tax_udf is None and total_quote is not None:
        base_fare = total_quote * 0.82
        tax_udf = total_quote * 0.18

    if total_quote is None:
        total_quote = (base_fare or 0.0) + (tax_udf or 0.0) + (convenience_fee or 0.0)

    return UnbundledFare(
        base_fare=round(base_fare or 0.0, 2),
        tax_udf=round(tax_udf, 2) if tax_udf is not None else None,
        convenience_fee=round(convenience_fee, 2) if convenience_fee is not None else None,
        total_quote=round(total_quote, 2),
    )


if __name__ == "__main__":

    def check(label: str, actual: UnbundledFare, base: float, tax: float, convenience: float) -> None:
        assert actual.base_fare == round(base, 2), f"{label}: base_fare={actual.base_fare} != {base}"
        assert actual.tax_udf == round(tax, 2), f"{label}: tax_udf={actual.tax_udf} != {tax}"
        assert actual.convenience_fee == round(convenience, 2), (
            f"{label}: convenience_fee={actual.convenience_fee} != {convenience}"
        )
        print(f"[PASS] {label}")

    check("camel label", unbundle_fare("Base: 5186, Tax: 933.48, Convenience: 300"),
          5186.0, 933.48, 300.0)
    check("no spaces", unbundle_fare("Base:5186, Tax:933.48, Convenience:300"),
          5186.0, 933.48, 300.0)
    check("long names", unbundle_fare("Base Fare: 5186, Tax & Airport User Development Fee: 933.48, "
          "Convenience / Management Fee: 300"),
          5186.0, 933.48, 300.0)
    check("with currency", unbundle_fare("Base: Rs.5186, Tax: INR 933.48, Convenience: ₹ 300"),
          5186.0, 933.48, 300.0)
    check("html snippet", unbundle_fare("<div class='fare'><span>Base: 5186, Tax: 933.48, Convenience: 300</span></div>"),
          5186.0, 933.48, 300.0)
    check("comma thousands", unbundle_fare("Base: 5,186.00, Tax: 933.48, Convenience: 300"),
          5186.0, 933.48, 300.0)

    fallback = unbundle_fare("Base: 5186, Convenience: 300", total_quote=7492.1)
    assert fallback.base_fare == round(7492.1 * 0.82, 2), f"fallback base_fare={fallback.base_fare}"
    assert fallback.tax_udf == round(7492.1 * 0.18, 2), f"fallback tax_udf={fallback.tax_udf}"
    print("[PASS] fallback proportional split")

    inferred_total = unbundle_fare("Base Fare 5186 | Tax 933.48 | Convenience 300")
    assert inferred_total.total_quote == round(5186 + 933.48 + 300, 2), f"inferred total={inferred_total.total_quote}"
    print("[PASS] total_quote inferred from components")

    print("\nAll fare unbundler unit tests passed.")