"""Synthetic merchant catalog (Phase 1; obviously fake data, no real merchants)."""

from datetime import UTC, datetime

from razormesh_api.domain.ids import MerchantId, ProductId
from razormesh_api.persistence.db import create_db_engine, create_session_factory
from razormesh_api.persistence.models import Merchant, Product
from razormesh_api.persistence.repositories import Repositories

CATALOG_MERCHANTS: list[Merchant] = []
PRODUCTS: list[Product] = []

_MERCHANT_DEFS = [
    ("SYNTH-AUDIO", "SynthAudio Emporium", "Curated audio gear (synthetic demo)"),
    ("SYNTH-HOME", "SynthHome Living", "Smart-home essentials (synthetic demo)"),
    ("SYNTH-BOOKS", "SynthBooks & Media", "Books and media (synthetic demo)"),
    ("SYNTH-OUTDOOR", "SynthOutdoor Co", "Outdoor and fitness (synthetic demo)"),
    ("SYNTH-GAMING", "SynthGaming Hub", "Gaming peripherals (synthetic demo)"),
]

_AUDIO = [
    ("Sony WH-1000XM5 Wireless Headphones", "Sony", 479900, "audio", "new", False),
    ("Bose QuietComfort Earbuds", "Bose", 189900, "audio", "new", False),
    ("JBL Flip 6 Bluetooth Speaker", "JBL", 99900, "audio", "refurbished", False),
    ("Audio-Technica AT2020 Mic", "Audio-Technica", 119900, "audio", "new", False),
    ("Sennheiser HD 600 Headphones", "Sennheiser", 329990, "audio", "new", True),
    ("Anker Soundcore Mini", "Anker", 29900, "audio", "used", False),
    ("Marshall Emberton Speaker", "Marshall", 179900, "audio", "new", False),
    ("Sony WH-CH720N Headphones", "Sony", 149900, "audio", "new", False),
    ("Bose SoundLink Revolve", "Bose", 209900, "audio", "refurbished", False),
    ("JBL Tune 760NC", "JBL", 79900, "audio", "new", False),
]

_HOME = [
    ("Philips Hue Starter Kit", "Philips", 129900, "smarthome", "new", True),
    ("Mi Smart LED Bulb", "Xiaomi", 99900, "smarthome", "new", False),
    ("Dyson V15 Detect Vacuum", "Dyson", 599900, "smarthome", "new", False),
    ("Echo Dot 5th Gen", "Amazon", 54900, "smarthome", "new", True),
    ("Roborock S8 Robot Vacuum", "Roborock", 499900, "smarthome", "new", False),
    ("TP-Link Smart Plug (4-pack)", "TP-Link", 34900, "smarthome", "new", False),
    ("Nest Learning Thermostat", "Google", 229900, "smarthome", "new", True),
    ("Sonoff Zigbee Hub", "Sonoff", 44900, "smarthome", "new", False),
    ("Realme Smart Watch", "Realme", 39990, "smarthome", "new", True),
    ("Orient Electric Fan", "Orient", 29990, "smarthome", "used", False),
]

_BOOKS = [
    ("Clean Code (Paperback)", "Prentice Hall", 59900, "books", "new", False),
    ("The Pragmatic Programmer", "Addison-Wesley", 79900, "books", "new", False),
    ("Designing Data-Intensive Apps", "O'Reilly", 89900, "books", "new", False),
    ("Atomic Habits (Hardcover)", "Penguin", 49900, "books", "new", False),
    ("Sapiens (Paperback)", "Harper", 44900, "books", "new", False),
    ("Refactoring (2nd Ed)", "Addison-Wesley", 69900, "books", "new", False),
    ("Kafka on the Shore (Used)", "Random House", 29900, "books", "used", False),
    ("The Lean Startup", "Crown", 39900, "books", "new", False),
    ("Deep Learning (Hardcover)", "MIT Press", 119900, "books", "new", True),
    ("Mythical Man-Month", "Addison-Wesley", 54900, "books", "new", False),
]

_OUTDOOR = [
    ("Decathlon Trek 100 Tent (2P)", "Decathlon", 89900, "outdoor", "new", False),
    ("CamelBak Hydration Pack", "CamelBak", 59900, "outdoor", "new", False),
    ("Wildcraft 65L Rucksack", "Wildcraft", 74900, "outdoor", "new", False),
    ("Nike Running Shoes Air Zoom", "Nike", 119900, "outdoor", "new", False),
    ("Yoga Mat Premium 6mm", "FitKit", 29900, "outdoor", "new", False),
    ("Decathlon MTB Helmet", "Decathlon", 39900, "outdoor", "refurbished", False),
    ("Garmin Forerunner 265", "Garmin", 429900, "outdoor", "new", True),
    ("Adidas Training Tee", "Adidas", 19990, "outdoor", "new", False),
    ("Speedo Swim Goggles", "Speedo", 14990, "outdoor", "new", False),
    ("Coleman Camp Stove", "Coleman", 64900, "outdoor", "new", False),
]

_GAMING = [
    ("Logitech G502 X Mouse", "Logitech", 89900, "gaming", "new", False),
    ("Razer BlackWidow V4 Keyboard", "Razer", 139900, "gaming", "new", False),
    ("Sony DualSense Controller", "Sony", 59900, "gaming", "new", False),
    ('LG 27" Ultragear Monitor', "LG", 249900, "gaming", "new", False),
    ("SteelSeries Arctis 7 Headset", "SteelSeries", 109900, "gaming", "new", False),
    ("NVIDIA Shield TV Pro", "NVIDIA", 199900, "gaming", "new", True),
    ("8BitDo Pro 2 Controller", "8BitDo", 49900, "gaming", "new", False),
    ("Corsair 16GB RAM DDR5", "Corsair", 72900, "gaming", "new", False),
    ("Seagate 2TB SSD", "Seagate", 149900, "gaming", "new", False),
    ("Razer Mousepad XXL", "Razer", 24900, "gaming", "used", False),
]


def _build_catalog() -> tuple[list[Merchant], list[Product]]:
    now = datetime.now(UTC)
    merchants: list[Merchant] = []
    products: list[Product] = []
    for _slug, name, desc in _MERCHANT_DEFS:
        mid = MerchantId.generate()
        merchants.append(
            Merchant(
                id=str(mid),
                name=name,
                display_name=name,
                description=desc,
                created_at=now,
                updated_at=now,
            )
        )
    groups = [_AUDIO, _HOME, _BOOKS, _OUTDOOR, _GAMING]
    merchant_ids = [m.id for m in merchants]
    for mid_str, (slug, _name, _desc), group in zip(
        merchant_ids, _MERCHANT_DEFS, groups, strict=True
    ):
        mid = MerchantId(mid_str)
        for title, brand, price, category, condition, recurring in group:
            p = Product(
                id=str(ProductId.generate()),
                merchant_id=str(mid),
                title=title,
                description=(
                    f"{title} - synthetic catalog entry for Phase-1 demo (not a real offer)."
                ),
                brand=brand,
                category=category,
                condition=condition,
                price_minor=price,
                currency="INR",
                shipping_minor=49900 if price < 200000 else 0,
                tax_minor=0,
                fees_minor=0,
                recurring=recurring,
                recurring_frequency="monthly" if recurring else None,
                image_url=f"https://example.invalid/synth/{slug}/{brand}.png",
                created_at=now,
                updated_at=now,
            )
            products.append(p)
    return merchants, products


def seed_catalog(repos: Repositories) -> int:
    """Idempotent seed: skip if catalog already present; atomic single transaction."""
    existing = repos.merchants.list(limit=1)
    if existing:
        return 0
    merchants, products = _build_catalog()
    with repos.transaction() as session:
        session.add_all(merchants)
        session.add_all(products)
    return len(products)


if __name__ == "__main__":
    from razormesh_api.settings import get_settings

    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    repos = Repositories(create_session_factory(engine))
    count = seed_catalog(repos)
    print(f"seeded {count} synthetic products")
