"""SQLite catalog, retailer accounts, and emissions comparisons."""

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from difflib import get_close_matches
from getpass import getpass
from hashlib import pbkdf2_hmac
from hmac import compare_digest
import os
from pathlib import Path
from secrets import token_bytes
import sqlite3


DEFAULT_DB = Path(__file__).with_name("ecobuilder.sqlite3")
DEMO_SOURCE = "EcoBuilder demo data (illustrative)"
PASSWORD_ROUNDS = 600_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS retailers (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    password_salt BLOB,
    password_hash BLOB
);
CREATE TABLE IF NOT EXISTS specifications (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    unit TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    retailer_id INTEGER NOT NULL REFERENCES retailers(id),
    specification_id TEXT NOT NULL REFERENCES specifications(id),
    name TEXT NOT NULL,
    name_key TEXT NOT NULL,
    emissions TEXT NOT NULL,
    source TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    UNIQUE (retailer_id, name_key, specification_id)
);
CREATE INDEX IF NOT EXISTS products_specification ON products(specification_id, active);
"""

RETAILERS = (
    ("greenfield", "Greenfield Materials"),
    ("cornerstone", "Cornerstone Building Supply"),
)

# Each pair illustrates products within the same intended-use and specification group.
SEED = (
    ("cement-opc43", "Cement", "OPC 43 grade for general concrete", "kg",
     ("BuildBase OPC 43", "0.82"), ("EcoBind OPC 43", "0.71")),
    ("concrete-m25", "Ready-mix concrete", "M25 ready-mix for structural concrete", "m³",
     ("BuildMix M25", "312"), ("EcoMix M25", "238")),
    ("rebar-fe500d-12", "Rebar", "Fe500D, 12 mm, for reinforced concrete", "kg",
     ("BuildBar Fe500D 12 mm", "1.83"), ("ReLoop Fe500D 12 mm", "1.20")),
    ("block-100", "Masonry blocks", "Solid concrete block, 400 × 200 × 100 mm, non-load-bearing partition", "block",
     ("BuildBlock 100", "2.46"), ("EcoBlock 100", "1.91")),
    ("sand-zone-ii", "Sand", "Zone II fine aggregate for concrete", "kg",
     ("BuildSand Zone II", "0.007"), ("EcoSand Zone II", "0.005")),
    ("aggregate-20", "Coarse aggregate", "Nominal 20 mm graded crushed aggregate for concrete", "kg",
     ("BuildStone 20 mm", "0.011"), ("EcoStone 20 mm", "0.008")),
    ("timber-c24", "Structural timber", "C24 kiln-dried sawn softwood for framing", "m³",
     ("BuildFrame C24", "131"), ("EcoFrame C24", "102")),
    ("roof-050", "Roofing", "0.50 mm profiled coated steel roof sheet, matching profile and coating", "m²",
     ("BuildRoof 0.50 mm", "9.8"), ("EcoRoof 0.50 mm", "7.5")),
)

PRODUCT_QUERY = """
SELECT p.id, p.specification_id, p.name, p.name_key, p.emissions, p.source,
       p.active, r.name AS retailer, s.category, s.description, s.unit
FROM products p
JOIN retailers r ON r.id = p.retailer_id
JOIN specifications s ON s.id = p.specification_id
"""


@dataclass(frozen=True)
class Product:
    id: int
    specification_id: str
    name: str
    name_key: str
    emissions: Decimal
    source: str
    active: bool
    retailer: str
    category: str
    description: str
    unit: str


@dataclass(frozen=True)
class Comparison:
    product: Product
    ranked: tuple[Product, ...]


def database_path() -> Path:
    return Path(os.environ.get("ECOBUILDER_DB", DEFAULT_DB))


def normalize_name(value: str) -> str:
    return " ".join(value.casefold().split())


@contextmanager
def connect(path: Path):
    db = sqlite3.connect(path)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        with db:
            yield db
    finally:
        db.close()


def initialize(path: Path) -> None:
    """Seed a new database without overwriting retailer edits on later runs."""
    with connect(path) as db:
        db.executescript("BEGIN IMMEDIATE;\n" + SCHEMA)
        if db.execute("SELECT 1 FROM retailers LIMIT 1").fetchone():
            return

        db.executemany("INSERT INTO retailers (username, name) VALUES (?, ?)", RETAILERS)
        retailer_ids = [row["id"] for row in db.execute("SELECT id FROM retailers ORDER BY id")]
        for specification_id, category, description, unit, *listings in SEED:
            db.execute(
                "INSERT INTO specifications VALUES (?, ?, ?, ?)",
                (specification_id, category, description, unit),
            )
            db.executemany(
                """INSERT INTO products
                   (retailer_id, specification_id, name, name_key, emissions, source)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (retailer_id, specification_id, name, normalize_name(name), factor, DEMO_SOURCE)
                    for retailer_id, (name, factor) in zip(retailer_ids, listings, strict=True)
                ],
            )


def specifications(path: Path) -> list[sqlite3.Row]:
    with connect(path) as db:
        return db.execute(
            "SELECT id, category, description, unit FROM specifications ORDER BY category"
        ).fetchall()


def products(path: Path, retailer_id: int | None = None) -> list[Product]:
    with connect(path) as db:
        if retailer_id is None:
            rows = db.execute(PRODUCT_QUERY + " WHERE p.active = 1 ORDER BY p.name_key, r.name")
        else:
            rows = db.execute(
                PRODUCT_QUERY + " WHERE p.retailer_id = ? ORDER BY p.name_key",
                (retailer_id,),
            )
        return [
            Product(**{**dict(row), "emissions": Decimal(row["emissions"]), "active": bool(row["active"])})
            for row in rows
        ]


def product_value(value: str | Decimal) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("Enter an emissions factor such as 238 or 0.71.") from error
    if not result.is_finite() or not 0 <= result <= 1_000_000_000:
        raise ValueError("Enter an emissions factor between 0 and 1,000,000,000.")
    rounded = result.quantize(Decimal("0.000000001"))
    if result != rounded:
        raise ValueError("Use at most nine decimal places for the emissions factor.")
    return rounded.normalize()


def save_product(
    path: Path,
    retailer_id: int,
    *,
    name: str,
    specification_id: str,
    emissions: str,
    source: str,
    product_id: int | None = None,
) -> None:
    name = " ".join(name.split())
    source = source.strip()
    if not name or not source:
        raise ValueError("Enter a product name and an emissions source.")
    factor = product_value(emissions)
    fields = (specification_id, name, normalize_name(name), str(factor), source)
    try:
        with connect(path) as db:
            if product_id is None:
                db.execute(
                    """INSERT INTO products
                       (specification_id, name, name_key, emissions, source, retailer_id)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (*fields, retailer_id),
                )
            else:
                result = db.execute(
                    """UPDATE products
                       SET specification_id = ?, name = ?, name_key = ?, emissions = ?, source = ?
                       WHERE id = ? AND retailer_id = ?""",
                    (*fields, product_id, retailer_id),
                )
                if result.rowcount != 1:
                    raise LookupError("That listing is unavailable to this retailer.")
    except sqlite3.IntegrityError as error:
        if error.sqlite_errorname == "SQLITE_CONSTRAINT_UNIQUE":
            raise ValueError("You already have a product with this name and specification.") from error
        if error.sqlite_errorname == "SQLITE_CONSTRAINT_FOREIGNKEY":
            raise ValueError("Choose an existing retailer and specification.") from error
        raise


def set_product_active(path: Path, retailer_id: int, product_id: int, active: bool) -> None:
    with connect(path) as db:
        result = db.execute(
            "UPDATE products SET active = ? WHERE id = ? AND retailer_id = ?",
            (active, product_id, retailer_id),
        )
        if result.rowcount != 1:
            raise LookupError("That listing is unavailable to this retailer.")


def resolve_product(
    catalog: list[Product], name: str, retailer: str = "", specification: str = "",
) -> tuple[Product | None, tuple[Product, ...]]:
    """Resolve exact names and offer possible matches for the user to confirm."""
    key = normalize_name(name)
    if not key:
        return None, ()

    retailer_key = normalize_name(retailer)
    retailer_catalog = [
        product for product in catalog if retailer_key in normalize_name(product.retailer)
    ]
    matches = [product for product in retailer_catalog if product.name_key == key]
    if matches and specification.strip():
        tag = normalize_name(specification).replace(" ", "")
        filtered = [
            product for product in matches
            if tag in normalize_name(f"{product.name} {product.description}").replace(" ", "")
        ]
        if not filtered:
            return None, tuple(matches)
        matches = filtered
    if len(matches) == 1:
        return matches[0], ()
    if matches:
        return None, tuple(matches)

    partial = [product for product in retailer_catalog if key in product.name_key]
    if partial:
        return None, tuple(partial[:5])
    close = get_close_matches(key, sorted({p.name_key for p in retailer_catalog}), n=5)
    return None, tuple(product for product in retailer_catalog if product.name_key in close)[:5]


def compare_product(product: Product, catalog: list[Product]) -> Comparison:
    comparable = (
        candidate for candidate in catalog if candidate.specification_id == product.specification_id
    )
    ranked = sorted(
        comparable,
        key=lambda candidate: (
            candidate.emissions, candidate.name_key, normalize_name(candidate.retailer), candidate.id,
        ),
    )
    return Comparison(product, tuple(ranked))


def password_digest(password: str, salt: bytes) -> bytes:
    return pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ROUNDS)


def set_password(path: Path, username: str, password: str) -> None:
    if not 12 <= len(password) <= 256:
        raise ValueError("Choose a password between 12 and 256 characters.")
    salt = token_bytes(16)
    digest = password_digest(password, salt)
    with connect(path) as db:
        result = db.execute(
            "UPDATE retailers SET password_salt = ?, password_hash = ? WHERE username = ?",
            (salt, digest, normalize_name(username)),
        )
        if result.rowcount != 1:
            raise ValueError("Unknown retailer username.")


def authenticate(path: Path, username: str, password: str) -> tuple[int, str] | None:
    with connect(path) as db:
        row = db.execute(
            "SELECT id, name, password_salt, password_hash FROM retailers WHERE username = ?",
            (normalize_name(username),),
        ).fetchone()

    configured = row is not None and row["password_hash"] is not None
    salt = row["password_salt"] if configured else bytes(16)
    expected = row["password_hash"] if configured else bytes(32)
    valid = compare_digest(password_digest(password, salt), expected)
    if configured and valid:
        return row["id"], row["name"]
    return None


def load_data():
    """Read the original workbook for the legacy report."""
    import pandas as pd

    workbook = Path(__file__).with_name("prototype_dataset1.xlsx")
    frame = pd.read_excel(workbook, header=1).dropna(axis=1, how="all")
    frame.columns = frame.columns.astype(str).str.strip()
    return frame


def calculate_results():
    frame = load_data()
    frame["Total Value"] = frame["Quantity"] * frame["Price"]
    return frame, frame["Quantity"].sum(), frame["Total Value"].sum(), frame["Price"].mean()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db", help="Create and seed the database")
    password_command = commands.add_parser("set-password", help="Set a retailer login password")
    password_command.add_argument("username", choices=[username for username, _ in RETAILERS])
    args = parser.parse_args()

    path = database_path()
    initialize(path)
    if args.command == "init-db":
        print(f"Catalog ready at {path}")
        return

    password = getpass("New password: ")
    if password != getpass("Repeat password: "):
        parser.error("The passwords did not match.")
    try:
        set_password(path, args.username, password)
    except ValueError as error:
        parser.error(str(error))
    print(f"Password saved for {args.username}.")


if __name__ == "__main__":
    main()
