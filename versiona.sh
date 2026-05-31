#!/bin/bash
# versiona.sh — Automazione release per PCM (Python Connection Manager)
#
# Flusso completo:
#   1. Genera note di rilascio (Claude AI o fallback)
#   2. Crea commit "chore: release N" + tag vN + push
#   3. Crea la release GitHub con le note AI  ← versiona.sh possiede questo
#   4. Builda AppImage localmente              ← sempre, senza chiedere
#   5. Carica AppImage sulla release
#   GitHub Actions (triggerato dal tag) builda deb/tar.gz/zip e li carica
#   sulla release già esistente — non crea release proprie per i tag.
#
# Uso: bash versiona.sh [--dry-run]
# Opzionale: ANTHROPIC_API_KEY per note generate con AI.

set -e

# ── Colori ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
info() { echo -e "${CYAN}ℹ ${RESET}$*"; }
ok()   { echo -e "${GREEN}✔ ${RESET}$*"; }
warn() { echo -e "${YELLOW}⚠ ${RESET}$*" >&2; }
err()  { echo -e "${RED}✘ ${RESET}$*" >&2; exit 1; }
sep()  { echo -e "${BOLD}──────────────────────────────────────────────${RESET}"; }

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

# ── Prerequisiti ──────────────────────────────────────────────────────────────
git rev-parse --git-dir &>/dev/null || err "Non sei in un repository git."
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

command -v gh &>/dev/null || err "GitHub CLI (gh) non trovata. Installa con: sudo pacman -S github-cli"

PROJECT_NAME="PCM"

# ── Branch e piattaforma ──────────────────────────────────────────────────────
detect_main_branch() {
    local ref
    ref=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|.*/||' || true)
    [[ -n "$ref" ]] && echo "$ref" && return
    for b in main master; do
        git show-ref --verify --quiet "refs/heads/$b" && echo "$b" && return
    done
    git rev-parse --abbrev-ref HEAD
}
MAIN_BRANCH=$(detect_main_branch)

# ── Versione = numero di commit dopo il commit di release ─────────────────────
COMMIT_COUNT=$(git rev-list --count HEAD 2>/dev/null) || err "Impossibile contare i commit."
VERSION=$(( COMMIT_COUNT + 1 ))
TAG_VERSION="v${VERSION}"

# ── Raccolta commit dall'ultimo tag ───────────────────────────────────────────
LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
if [[ -z "$LATEST_TAG" ]]; then
    RAW_COMMITS=$(git log --pretty=tformat:"---commit---%n%B" --no-merges || true)
else
    RAW_COMMITS=$(git log "${LATEST_TAG}..HEAD" --pretty=tformat:"---commit---%n%B" --no-merges || true)
fi
FILTERED_COMMITS=$(echo "$RAW_COMMITS" | grep -Eiv "^chore: (release|bump|version) " || true)

# ── Genera note di rilascio ───────────────────────────────────────────────────
generate_release_notes() {
    local commits="$1" version="$2"
    local prompt="Trasforma i seguenti commit message git in note di rilascio professionali per ${PROJECT_NAME} build ${version}.

Istruzioni:
- Scrivi in italiano
- Raggruppa per categoria con questi titoli (includi solo quelle presenti):
  ## 🆕 Nuove funzionalità
  ## ⚡ Miglioramenti
  ## 🐛 Correzioni di bug
  ## 🔧 Manutenzione
- Ogni voce come elenco puntato con •
- Linguaggio chiaro, orientato all'utente finale
- Ometti commit di tipo 'chore: release', 'chore: bump', 'chore: version'
- Massimo 2 righe per voce, inizia direttamente con le categorie

Commit:
${commits}"

    if command -v curl &>/dev/null && command -v jq &>/dev/null && [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
        info "Generazione note con Claude AI..." >&2
        local payload result
        payload=$(jq -n --arg txt "$prompt" '{
            model: "claude-haiku-4-5-20251001",
            max_tokens: 2048,
            messages: [{"role": "user", "content": $txt}]
        }')
        result=$(curl -sf --max-time 30 -X POST "https://api.anthropic.com/v1/messages" \
            -H "x-api-key: $ANTHROPIC_API_KEY" \
            -H "anthropic-version: 2023-06-01" \
            -H "content-type: application/json" \
            -d "$payload" | jq -r '.content[0].text' 2>/dev/null || true)
        if [[ -n "$result" && "$result" != "null" ]]; then
            ok "Note generate con AI." >&2
            echo "$result"; return 0
        fi
        warn "Claude API non raggiungibile o chiave non valida; uso formattazione base." >&2
    else
        warn "AI non disponibile (curl/jq mancanti o ANTHROPIC_API_KEY non impostata); uso formattazione base." >&2
    fi

    # Fallback: raggruppa per tipo conventional commit
    local feat="" fix="" perf="" other=""
    while IFS= read -r subj; do
        local clean
        clean=$(printf '%s' "$subj" | sed -E 's/^[a-z]+(\([^)]+\))?: //')
        if   [[ "$subj" =~ ^feat ]]; then feat+="• $clean"$'\n'
        elif [[ "$subj" =~ ^fix  ]]; then fix+="• $clean"$'\n'
        elif [[ "$subj" =~ ^perf ]]; then perf+="• $clean"$'\n'
        else                              other+="• $clean"$'\n'
        fi
    done < <(
        echo "$commits" \
            | awk '/^---commit---/ { if (s != "") print s; s = ""; next }
                   /^[[:space:]]*$/ { next }
                   s == ""          { s = $0 }
                   END              { if (s != "") print s }' \
            | grep -Eiv "^chore: (release|bump|version)" || true
    )
    local out=""
    [[ -n "$feat"  ]] && out+=$'## 🆕 Nuove funzionalità\n'"$feat"$'\n'
    [[ -n "$perf"  ]] && out+=$'## ⚡ Miglioramenti\n'"$perf"$'\n'
    [[ -n "$fix"   ]] && out+=$'## 🐛 Correzioni di bug\n'"$fix"$'\n'
    [[ -n "$other" ]] && out+=$'## 🔧 Manutenzione\n'"$other"$'\n'
    echo "${out%$'\n'}"
}

# ═════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}=== Release: ${PROJECT_NAME} === branch: ${MAIN_BRANCH} ===${RESET}"
$DRY_RUN && echo -e "${YELLOW}[DRY RUN — nessuna modifica verrà applicata]${RESET}"
echo ""
info "Versione build: ${BOLD}${VERSION}${RESET}  →  tag ${BOLD}${TAG_VERSION}${RESET}"
info "Commit analizzati dal tag: ${BOLD}${LATEST_TAG:-inizio repo}${RESET}"
echo ""

# ── Genera note ───────────────────────────────────────────────────────────────
if [[ -z "${FILTERED_COMMITS// }" ]]; then
    CHANGELOG="• nessun commit trovato"
else
    CHANGELOG=$(generate_release_notes "$FILTERED_COMMITS" "$VERSION")
fi

# ── Anteprima e conferma ──────────────────────────────────────────────────────
while true; do
    echo ""
    sep
    echo -e "${BOLD}Note di rilascio — ${PROJECT_NAME} build ${VERSION}:${RESET}"
    sep
    echo ""
    echo "$CHANGELOG"
    echo ""
    sep
    echo ""
    read -rp "$(echo -e "Continuare con build ${BOLD}${VERSION}${RESET}? [s(i)/N(o)/e(dita note)] ")" CONFIRM
    CONFIRM=${CONFIRM:-N}
    case "${CONFIRM,,}" in
        s) break ;;
        n) warn "Release annullata."; exit 0 ;;
        e)
            TMP_EDIT=$(mktemp /tmp/versiona_edit_XXXX.md)
            echo "$CHANGELOG" > "$TMP_EDIT"
            ${EDITOR:-nano} "$TMP_EDIT"
            CHANGELOG=$(cat "$TMP_EDIT")
            rm -f "$TMP_EDIT"
            info "Note modificate." ;;
        *) echo -e "${YELLOW}Scelta non valida: s, n o e.${RESET}" ;;
    esac
done

$DRY_RUN && { ok "[DRY RUN] Uscita senza modifiche."; exit 0; }

# ── Commit + tag ──────────────────────────────────────────────────────────────
info "Creazione commit di release..."
git commit -m "chore: release ${VERSION}" --allow-empty
ok "Commit creato (commit #$(git rev-list --count HEAD))."

info "Creazione tag ${TAG_VERSION}..."
git tag -a "$TAG_VERSION" -m "$(printf '%s build %s\n\n%s' "$PROJECT_NAME" "$VERSION" "$CHANGELOG")"
ok "Tag ${TAG_VERSION} creato."

# ── Push branch ───────────────────────────────────────────────────────────────
info "Push branch ${MAIN_BRANCH}..."
git push origin "$MAIN_BRANCH"
ok "Branch pushato."

# ── Crea release GitHub con note AI ──────────────────────────────────────────
# gh release create pusha il tag su GitHub E crea la release atomicamente.
# Così quando Actions riceve il push del tag la release esiste già
# e può fare gh release upload senza race condition.
echo ""
info "Creazione release GitHub ${TAG_VERSION} (pusha anche il tag)..."
NOTES_FILE=$(mktemp /tmp/release_notes_XXXX.md)
printf '%s\n' "$CHANGELOG" > "$NOTES_FILE"
gh release create "$TAG_VERSION" \
    --title "${PROJECT_NAME} build ${VERSION}" \
    --notes-file "$NOTES_FILE"
rm -f "$NOTES_FILE"
ok "Release ${TAG_VERSION} creata — tag pushato su GitHub, Actions avviato."

# ── Build AppImage + upload ───────────────────────────────────────────────────
# Eseguito sempre; GitHub Actions non builda AppImage (richiede FUSE locale).
echo ""
sep
info "Build AppImage (versione ${VERSION})..."
info "GitHub Actions sta buildando deb/tar.gz/zip in parallelo."
echo ""

bash packaging/appimage/build-appimage.sh "$VERSION" --skip-deps 2>/dev/null || \
    bash packaging/appimage/build-appimage.sh "$VERSION"

APPIMAGE_FILE=$(ls dist/PCM-${VERSION}-*.AppImage 2>/dev/null | head -1 || true)

if [[ -z "$APPIMAGE_FILE" ]]; then
    warn "AppImage non trovata in dist/ — upload saltato."
    warn "Per caricarla manualmente: gh release upload ${TAG_VERSION} dist/PCM-${VERSION}-*.AppImage --clobber"
else
    ok "AppImage pronta: ${APPIMAGE_FILE} ($(du -sh "${APPIMAGE_FILE}" | cut -f1))"
    info "Upload AppImage nella release ${TAG_VERSION}..."
    gh release upload "$TAG_VERSION" "$APPIMAGE_FILE" --clobber
    ok "AppImage caricata nella release ${TAG_VERSION}."
fi

# ── Pulizia ───────────────────────────────────────────────────────────────────
echo ""
sep
info "Pulizia artefatti di build locali..."
rm -rf "$REPO_ROOT/build/" "$REPO_ROOT/.venv-build/" \
       "$REPO_ROOT/gtk3/__pycache__/" "$REPO_ROOT/__pycache__/"
ok "Pulizia completata."

echo ""
echo -e "${GREEN}${BOLD}=== ✔  ${PROJECT_NAME} build ${VERSION} rilasciato! ===${RESET}"
echo ""
info "GitHub Actions sta completando il caricamento di deb/tar.gz/zip."
info "Controlla: $(gh browse --no-browser 2>/dev/null && echo '' || git remote get-url origin | sed 's|git@github.com:|https://github.com/|;s|\.git$||')/releases/tag/${TAG_VERSION}"
echo ""
