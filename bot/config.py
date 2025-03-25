from dotenv import load_dotenv
import os

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
URL = os.getenv("URL")

# config_data.py

PRODUCT_BUTTONS = {
    "PRV": {"DEV": "cs-eng-proryv-dev", "STAND": "cs-eng-proryv-dev-prv", "PROD": "cs-eng-proryv-proryv_prod",
            "POM": "POM"},
    "TMIK": {"DEV": "cs-eng-tmik-dev", "STAND": "cs-eng-tmik-stand_tmik", "PROD": "cs-eng-tmik-prod_tmik",
             "POM": "POM"},
    "ECPS": {"DEV": "cs-eng-ecps-dev", "STAND": "cs-eng-ecps-dev_ecps", "PROD": "cs-eng-ecps-prod-ecps", "POM": "POM"},
    "CM": {"DEV": "cs-eng-cm-dev", "STAND": "cs-eng-dust3-dev", "PROD": "версия отсутствует", "POM": "POM"},
    "ITG": {"DEV": "cs-eng-itg", "STAND": "версия отсутствует", "PROD": "версия отсутствует", "POM": "POM"},
    "tyazhmash": {"DEV": "версия отсутствует", "STAND": "cs-eng-tyazhmash-dev-tyazhmash",
                  "PROD": "cs-eng-tyazhmash-tyazhmash_prod", "POM": "POM"},
    "OSK": {"DEV": "версия отсутствует", "STAND": "cs-eng-osk-osk", "PROD": "версия отсутствует", "POM": "POM"},
}

POM_MODULES = {
    "PRV": ["engbe", "glo", "itg", "dms", "dpd", "cm", "ped"],
    "tyazhmash": ["engbe", "glo", "dms", "dpd"],
    "OSK": ["engbe", "glo", "dms", "dpd", "cm", "ped", "pm"],
    "CM": ["engbe", "glo", "dms", "dpd"],
    "TMIK": ["engbe", "glo", "dms", "dpd", "ped", "cfg"],
}

POM_BUILD_MODULES = {
    "PRV": {
        "CORE": [
            "engdb.engrestapi",
            "engdb.cli",
            "engdb.conv",
            "engdb.front",
            "engdb.help.branch"
        ],
        "MODULES": [
            "engdb.glo",
            "engdb.cfg",
            "engdb.itg",
            "engdb.dms",
            "engdb.dpd",
            "engdb.cm",
            "engdb.ped",
            "engdb.proryv",
            "engdb.bdrk"
        ]
    },
    "tyazhmash": {
        "CORE": [
            "engdb.engrestapi",
            "engdb.cli",
            "engdb.conv",
            "engdb.front",
            "engdb.help.branch"
        ],
        "MODULES": [
            "engdb.glo",
            "engdb.dms",
            "engdb.dpd",
            "engdb.tyazhmash"
        ]
    },
    "OSK": {
        "CORE": [
            "engdb.engrestapi",
            "engdb.cli",
            "engdb.conv",
            "engdb.front",
            "engdb.help.branch"
        ],
        "MODULES": [
            "engdb.glo",
            "engdb.dms",
            "engdb.dpd",
            "engdb.cm",
            "engdb.ped",
            "engdb.pm"
        ]
    },
    "CM": {
        "CORE": [
            "engdb.engrestapi",
            "engdb.cli",
            "engdb.conv",
            "engdb.front",
            "engdb.help.branch"
        ],
        "MODULES": [
            "engdb.glo",
            "engdb.dms",
            "engdb.dpd",
            "engdb.ped",
            "engdb.cm",
            "engdb.pm"
        ]
    },
    "TMIK": {
        "CORE": [
            "engdb.engrestapi",
            "engdb.cli",
            "engdb.conv",
            "engdb.front",
            "engdb.help.branch"
        ],
        "MODULES": [
            "engdb.glo",
            "engdb.dms",
            "engdb.dpd",
            "engdb.ped",
            "engdb.cfg",
            "engdb.tmik",
            "engdb.cm",
        ]
    }
}

UNIFIED_POM_URLS = {
    "engbe": "https://mvn.cstechnology.ru/#/releases/ru/cs/engbe",
    "glo": "https://mvn.cstechnology.ru/#/releases/ru/cs/cs-glo",
    "itg": "https://mvn.cstechnology.ru/#/releases/ru/cs/cs-itg",
    "dms": "https://mvn.cstechnology.ru/#/releases/ru/cs/cs-dms",
    "dpd": "https://mvn.cstechnology.ru/#/releases/ru/cs/cs-dpd",
    "cm": "https://mvn.cstechnology.ru/#/releases/ru/cs/cs-cm",
    "ped": "https://mvn.cstechnology.ru/#/releases/ru/cs/cs-ped",
    "engrestapi": "https://mvn.cstechnology.ru/#/releases/ru/cs/engrestapi",
    "cli": "https://mvn.cstechnology.ru/#/releases/ru/cs/engdbcli",
    "conv": "https://mvn.cstechnology.ru/#/releases/ru/cs/engconv",
    "front": "https://mvn.cstechnology.ru/#/releases/ru/cs/engfront",
    "cfg": "https://mvn.cstechnology.ru/#/releases/ru/cs/cs-cfg",
    "proryv": "https://mvn.cstechnology.ru/#/releases/ru/cs/cs-proryv",
    "bdrk": "https://mvn.cstechnology.ru/#/releases/ru/cs/cs-bdrk",
    "tmik": "https://mvn.cstechnology.ru/#/releases/ru/cs/cs-tmik",
    "pm": "https://mvn.cstechnology.ru/#/releases/ru/cs/cs-pm",
    "tyazhmash": "https://mvn.cstechnology.ru/#/releases/ru/cs/cs-tyazhmash",
}
