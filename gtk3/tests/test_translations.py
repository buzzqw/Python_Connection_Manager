"""
Test che verifica che tutte le chiavi di traduzione e tooltip usate nel codice
siano presenti nel file translations.py e abbiano tutte e 5 le lingue.
"""
import os
import ast
import re
import pytest

# Trova il percorso base
HERE = os.path.dirname(os.path.abspath(__file__))
GTK3 = os.path.dirname(HERE) if HERE.endswith('tests') else HERE
if 'tests' in HERE:
    GTK3 = os.path.dirname(HERE)

TRANSLATIONS_FILE = os.path.join(GTK3, 'translations.py')
PY_FILES = [os.path.join(GTK3, f) for f in os.listdir(GTK3)
            if f.endswith('.py') and f != 'translations.py'
            and not f.startswith('test_') and not f.startswith('_')]


def _load_translation_keys(translations_file: str) -> dict:
    """Carica le chiavi di traduzione dal file translations.py."""
    with open(translations_file, 'r') as f:
        source = f.read()

    tree = ast.parse(source)

    class TranslationVisitor(ast.NodeVisitor):
        def __init__(self):
            self.keys = {}  # key -> set of languages

        def visit_Dict(self, node):
            for i in range(0, len(node.keys), 1):
                key_node = node.keys[i]
                value_node = node.values[i]
                if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                    if isinstance(value_node, ast.Dict):
                        langs = set()
                        for vk, vv in zip(value_node.keys, value_node.values):
                            if isinstance(vk, ast.Constant):
                                langs.add(vk.value)
                        self.keys[key_node.value] = langs
            self.generic_visit(node)

    visitor = TranslationVisitor()
    visitor.visit(tree)
    return visitor.keys


def _extract_t_calls(py_file: str) -> list[str]:
    """Estrae tutte le chiavi usate nelle chiamate t('...') e t(\"...\")."""
    with open(py_file, 'r') as f:
        content = f.read()

    keys = []
    # Pattern: t("key") o t('key')
    for match in re.finditer(r'\bt\s*\(\s*["\']([^"\']+)["\']', content):
        key = match.group(1)
        # Salta chiavi con formattazione (contengono {})
        if '{' not in key or '}' not in key:
            keys.append(key)
        else:
            # Chiavi come t("key", name=x) - estrai la parte senza {}
            base = key.split('{')[0].rstrip()
            if base and not base.endswith('_'):
                keys.append(key)

    return keys


@pytest.fixture(scope="module")
def translation_keys():
    return _load_translation_keys(TRANSLATIONS_FILE)


@pytest.fixture(scope="module")
def used_keys():
    all_keys = set()
    for py_file in PY_FILES:
        keys = _extract_t_calls(py_file)
        for k in keys:
            # Normalizza chiavi con format: "key.{name}" -> "key...."
            # Le teniamo così come sono, il test verificherà quali mancano
            all_keys.add(k)
    return all_keys


class TestTranslationCompleteness:
    """Verifica che tutte le chiavi usate abbiano traduzioni in 5 lingue."""

    REQUIRED_LANGUAGES = {'it', 'en', 'de', 'fr', 'es'}

    def test_all_used_keys_have_translations(self, translation_keys, used_keys):
        """Ogni chiave t() usata nel codice deve esistere in translations.py."""
        missing = []
        for key in sorted(used_keys):
            # Salta chiavi ovviamente dinamiche
            if any(c in key for c in '{}') and '_' not in key.split('{')[0]:
                continue
            # Salta chiavi di formato noto che hanno {name} o {n}
            base_key = key
            if '{' in key:
                base_key = key.split('{')[0].rstrip('. ')
                if not base_key:
                    continue

            # Cerca corrispondenza esatta o basata sul prefisso
            found = base_key in translation_keys
            if not found:
                # Prova match parziale per chiavi con formattazione
                for tk in translation_keys:
                    if tk == key or (key.startswith(tk) and tk.endswith('_')):
                        found = True
                        break

            if not found:
                missing.append(key)

        if missing:
            msg = "Chiavi di traduzione mancanti in translations.py:\n"
            for k in sorted(set(missing)):
                msg += f"  - \"{k}\"\n"
            msg += f"\nTotale: {len(set(missing))} chiavi mancanti"
            pytest.fail(msg)

    def test_new_specific_keys_exist(self, translation_keys):
        """Verifica che le nuove chiavi aggiunte siano presenti."""
        required = [
            'sd.totp_secret',
            'sd.tags',
            'sd.template.label',
            'sd.template.none',
            'sd.template.checkbox',
            'sidebar.tag_filter_all',
            'tt.totp_secret',
            'tt.tags',
            'tt.template',
            'tt.template_checkbox',
        ]
        missing = [k for k in required if k not in translation_keys]
        if missing:
            pytest.fail(f"Nuove chiavi mancanti: {missing}")

    def test_all_keys_have_5_languages(self, translation_keys):
        """Ogni chiave deve avere traduzioni in tutte e 5 le lingue."""
        incomplete = []
        for key, langs in translation_keys.items():
            missing_langs = self.REQUIRED_LANGUAGES - langs
            if missing_langs:
                incomplete.append(f"  {key}: manca {sorted(missing_langs)}")
        if incomplete:
            msg = "Chiavi con lingue mancanti:\n" + "\n".join(sorted(incomplete)[:30])
            if len(incomplete) > 30:
                msg += f"\n  ... e altre {len(incomplete) - 30}"
            pytest.fail(msg)

    def test_tooltip_keys_exist(self, translation_keys):
        """Verifica che tutte le chiavi tt.* usate nel codice abbiano traduzione."""
        tt_keys_in_code = set()
        for py_file in PY_FILES:
            with open(py_file, 'r') as f:
                content = f.read()
            for match in re.finditer(r't\s*\(\s*"tt\.([^"]+)"', content):
                tt_keys_in_code.add(f"tt.{match.group(1)}")
            for match in re.finditer(r"t\s*\(\s*'tt\.([^']+)'", content):
                tt_keys_in_code.add(f"tt.{match.group(1)}")

        missing = [k for k in sorted(tt_keys_in_code) if k not in translation_keys]
        if missing:
            msg = "Tooltip (tt.*) mancanti in translations.py:\n"
            for k in missing:
                msg += f"  - \"{k}\"\n"
            pytest.fail(msg)

    def test_sidebar_keys_exist(self, translation_keys):
        """Verifica che tutte le chiavi sidebar.* usate abbiano traduzione."""
        sb_keys_in_code = set()
        for py_file in PY_FILES:
            with open(py_file, 'r') as f:
                content = f.read()
            for match in re.finditer(r't\s*\(\s*"sidebar\.([^"]+)"', content):
                sb_keys_in_code.add(f"sidebar.{match.group(1)}")
            for match in re.finditer(r"t\s*\(\s*'sidebar\.([^']+)'", content):
                sb_keys_in_code.add(f"sidebar.{match.group(1)}")

        missing = [k for k in sorted(sb_keys_in_code) if k not in translation_keys]
        if missing:
            msg = "Sidebar keys mancanti in translations.py:\n"
            for k in missing:
                msg += f"  - \"{k}\"\n"
            pytest.fail(msg)

    def test_sd_keys_exist(self, translation_keys):
        """Verifica che tutte le chiavi sd.* (session dialog) usate abbiano traduzione."""
        sd_keys_in_code = set()
        for py_file in PY_FILES:
            with open(py_file, 'r') as f:
                content = f.read()
            for match in re.finditer(r't\s*\(\s*"sd\.([^"]+)"', content):
                sd_keys_in_code.add(f"sd.{match.group(1)}")
            for match in re.finditer(r"t\s*\(\s*'sd\.([^']+)'", content):
                sd_keys_in_code.add(f"sd.{match.group(1)}")

        missing = [k for k in sorted(sd_keys_in_code) if k not in translation_keys]
        if missing:
            msg = "Session dialog (sd.*) keys mancanti in translations.py:\n"
            for k in missing:
                msg += f"  - \"{k}\"\n"
            pytest.fail(msg)
