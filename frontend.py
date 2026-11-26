"""Streamlit entry point for EcoBuilder."""

from decimal import Decimal
from pathlib import Path

import streamlit as st

from advisor import AdvisorUnavailable, extract_requests
from backend import (
    Comparison,
    Product,
    authenticate,
    compare_product,
    database_path,
    initialize,
    products,
    resolve_product,
    save_product,
    set_product_active,
    specifications,
)


st.set_page_config(page_title="EcoBuilder", page_icon="🌿", layout="wide")


@st.cache_resource
def prepare_catalog(path: Path) -> None:
    initialize(path)


def emissions_label(value: Decimal) -> str:
    return format(value, "f")


def show_catalog(path: Path) -> None:
    catalog = products(path)
    if not catalog:
        st.info("The catalog has no active products.")
        return
    st.dataframe(
        [
            {
                "Product": product.name,
                "Retailer": product.retailer,
                "Material": product.category,
                "Specification": product.description,
                "A1–A3 (kg CO₂e per unit)": float(product.emissions),
                "Unit": product.unit,
                "Source": product.source,
            }
            for product in catalog
        ],
        hide_index=True,
        width="stretch",
    )


def show_comparison(comparison: Comparison) -> None:
    baseline = comparison.product
    ranked = comparison.ranked
    st.text(f"{baseline.name} · {baseline.retailer}")
    st.caption(baseline.description)
    unit = f"kg CO₂e/{baseline.unit}"
    if len(ranked) == 1:
        st.info(
            f"{emissions_label(baseline.emissions)} {unit}. "
            "The catalog has no comparable alternative for this product."
        )
    else:
        minimum = ranked[0].emissions
        leaders = [product for product in ranked if product.emissions == minimum]
        label = "Tied for lowest emissions" if len(leaders) > 1 else "Lowest emissions"
        names = ", ".join(f"{product.name} ({product.retailer})" for product in leaders)
        st.success(f"{label} · {emissions_label(minimum)} {unit}")
        st.text(names)
        if minimum < baseline.emissions:
            savings = emissions_label(baseline.emissions - minimum)
            st.text(f"{savings} {unit} lower than {baseline.name}.")
    st.dataframe(
        [
            {
                "Product": product.name,
                "Retailer": product.retailer,
                f"A1–A3 ({unit})": float(product.emissions),
                "Source": product.source,
                "Requested": product.id == baseline.id,
            }
            for product in ranked
        ],
        hide_index=True,
        width="stretch",
    )


def answer_request(path: Path, history: list[dict]) -> tuple[str, list[Comparison]]:
    try:
        requests = extract_requests(
            [{
                "role": turn["role"],
                "content": "\n".join(filter(None, (turn["content"], turn.get("context")))),
            }
            for turn in history[-8:]]
        )
    except AdvisorUnavailable as error:
        return str(error), []

    if not requests:
        return "Which product would you like to compare? Try BuildMix M25 or choose a name from the catalog.", []

    catalog = products(path)
    comparisons = []
    messages = []
    handled_ids = set()
    for request in requests:
        if not request.name.strip():
            continue
        product, choices = resolve_product(
            catalog, request.name, request.retailer or "", request.specification or "",
        )
        if product is not None:
            if product.id not in handled_ids:
                comparisons.append(compare_product(product, catalog))
                handled_ids.add(product.id)
        elif choices:
            options = ", ".join(
                f"{item.name} ({item.retailer}, {item.description})" for item in choices
            )
            messages.append(f'Which product did you mean by “{request.name}”? {options}.')
        else:
            messages.append(
                f'“{request.name}” could not be found in the active catalog. '
                "Check the name or choose a product from the catalog."
            )

    if not messages and not comparisons:
        messages.append("Enter a product name from the catalog to start a comparison.")
    return "\n\n".join(messages), comparisons


def client_dashboard(path: Path) -> None:
    st.title("Client Dashboard")
    st.caption("Compare cradle-to-gate (A1–A3) emissions. Seeded factors are illustrative demo data.")
    with st.expander("Browse the retailer catalog"):
        show_catalog(path)

    st.subheader("Product emissions chat")
    history = st.session_state.setdefault("chat_history", [])
    if not history:
        st.write("Enter a product name to compare it with matching alternatives. Try “Compare BuildMix M25.”")
    for turn in history:
        with st.chat_message(turn["role"]):
            if turn["content"]:
                st.text(turn["content"])
            for comparison in turn.get("comparisons", []):
                show_comparison(comparison)

    prompt = st.chat_input("Which construction products would you like to compare?", max_chars=1000)
    if prompt and prompt.strip():
        history.append({"role": "user", "content": prompt.strip()})
        with st.chat_message("user"):
            st.text(prompt.strip())
        with st.chat_message("assistant"):
            with st.spinner("Looking up products…"):
                content, comparisons = answer_request(path, history)
            if content:
                st.text(content)
            for comparison in comparisons:
                show_comparison(comparison)
        # Include baseline names in the next API turn even when the rendered answer is a table.
        lookup_context = ", ".join(
            f"{item.product.name} ({item.product.retailer})" for item in comparisons
        )
        history.append({
            "role": "assistant",
            "content": content,
            "comparisons": comparisons,
            "context": lookup_context,
        })


def retailer_login(path: Path) -> None:
    with st.form("retailer_login", clear_on_submit=True):
        username = st.text_input("Username", max_chars=80)
        password = st.text_input("Password", type="password", max_chars=256)
        submitted = st.form_submit_button("Sign in")

    if submitted:
        account = authenticate(path, username, password)
        if account is None:
            st.error("The username or password could not be verified.")
        else:
            st.session_state.retailer_account = account
            st.rerun()


def listing_form(path: Path, retailer_id: int, existing: Product | None) -> None:
    specs = {row["id"]: row for row in specifications(path)}
    spec_ids = list(specs)
    suffix = str(existing.id) if existing else "new"
    specification_id = st.selectbox(
        "Material specification",
        spec_ids,
        index=spec_ids.index(existing.specification_id) if existing else None,
        key=f"specification_{suffix}",
        format_func=lambda key: f'{specs[key]["category"]} · {specs[key]["description"]}',
    )
    with st.form(f"listing_{suffix}", clear_on_submit=existing is None):
        name = st.text_input("Product name", value=existing.name if existing else "", max_chars=120)
        unit = specs[specification_id]["unit"] if specification_id else "catalog unit"
        emissions = st.text_input(
            f"A1–A3 emissions (kg CO₂e per {unit})",
            value=emissions_label(existing.emissions) if existing else "",
            max_chars=32,
        )
        source = st.text_input(
            "Emissions source label",
            value=existing.source if existing else "",
            placeholder="For example, retailer demo estimate or EPD reference",
            max_chars=200,
        )
        submitted = st.form_submit_button("Save listing")
    if not submitted:
        return

    try:
        if specification_id is None:
            raise ValueError("Choose a material specification.")
        save_product(
            path,
            retailer_id,
            name=name,
            specification_id=specification_id,
            emissions=emissions,
            source=source,
            product_id=existing.id if existing else None,
        )
    except (ValueError, LookupError) as error:
        st.error(str(error))
    else:
        st.session_state.retailer_feedback = "Listing saved."
        st.rerun()


def retailer_dashboard(path: Path) -> None:
    st.title("Retailer Dashboard")
    account = st.session_state.get("retailer_account")
    if account is None:
        retailer_login(path)
        return

    retailer_id, name = account
    st.write(f"Signed in as {name}")
    if st.button("Sign out"):
        del st.session_state.retailer_account
        st.session_state.pop("retailer_feedback", None)
        st.rerun()
    if feedback := st.session_state.pop("retailer_feedback", None):
        st.success(feedback)

    owned = {product.id: product for product in products(path, retailer_id)}
    selection = st.selectbox(
        "Listing",
        [None, *owned],
        key=f"listing_selection_{retailer_id}",
        format_func=lambda key: "Add a product" if key is None else (
            f"{owned[key].name} · {owned[key].description}"
            + ("" if owned[key].active else " (inactive)")
        ),
    )
    existing = owned.get(selection)
    listing_form(path, retailer_id, existing)
    if existing:
        action = "Deactivate listing" if existing.active else "Reactivate listing"
        if st.button(action, key=f"toggle_{existing.id}"):
            try:
                set_product_active(path, retailer_id, existing.id, not existing.active)
            except LookupError as error:
                st.error(str(error))
            else:
                st.session_state.retailer_feedback = "Listing deactivated." if existing.active else "Listing reactivated."
                st.rerun()


def home_page() -> None:
    st.title("EcoBuilder")
    st.write("Compare construction products by embodied carbon.")
    client, retailer = st.columns(2)
    with client:
        st.subheader("Client Dashboard")
        st.write("Look up products and compare their emissions.")
        st.button("Open Client Dashboard", on_click=go_to, args=("Client",), width="stretch")
    with retailer:
        st.subheader("Retailer Dashboard")
        st.write("Manage your product listings and emissions data.")
        st.button("Open Retailer Dashboard", on_click=go_to, args=("Retailer",), width="stretch")


def go_to(page: str) -> None:
    st.session_state.page = page


path = database_path()
prepare_catalog(path)
if "page" not in st.session_state:
    st.session_state.page = "Home"

with st.sidebar:
    st.title("Navigation")
    for page in ("Home", "Client", "Retailer"):
        st.button(page, on_click=go_to, args=(page,), width="stretch")

if st.session_state.page == "Client":
    client_dashboard(path)
elif st.session_state.page == "Retailer":
    retailer_dashboard(path)
else:
    home_page()
